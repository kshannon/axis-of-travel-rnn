"""
ReviewManager: the sessions index, a session loaded for the replay, the blocks some edits make, a session's blocks saved and built, and a session excluded or included by the person.
"""

import getpass
import json

from ..engines.trajectory import RULES, VERSION
from ..utilities import clock
from ..utilities.errors import Invalid, NotFound

# What the browser gets of a session, an epoch and a run, of the engine's session (the keys the Replay page draws), and the arrays it plays.
SESSION_KEYS = ("session_id", "subject_id", "group", "protocol", "rate_hz", "max_gap")
EPOCH_KEYS = ("epoch", "environment", "condition", "frame_start", "frame_end", "duration_s")
RUN_KEYS = ("run", "epoch", "path_id", "clean", "frame_start", "frame_end")
DRAWN_KEYS = ("frame", "heading_spans", "cut_points", "margins", "stretches", "occupancy", "stops")
ARRAY_KEYS = ("t", "x", "y", "x_smooth", "y_smooth", "heading", "speed", "turn_rate", "motion", "n_lights")

# The statuses of a block: the two a build keeps, a block no one has looked at, and a removed block, and the keys of a review's block.
CONFIRMED, AUTO, DROPPED = "confirmed", "auto", "dropped"
KEPT = (CONFIRMED, "edited")
BLOCK_KEYS = ("block_id", "epoch", "environment", "frame_start", "frame_end", "status", "note")

# The epoch kind whose environment has a start site, and the review's key for the start offset the person tuned (none means the yaml's).
TRACK = "track"
START_OFFSET = "start_offset_m"

# What the manager says: a save refused (the edit as a person counts it, from 1, or because the person excluded the session), a session the
# funnel leaves out (no frames, no epoch of the rules), a build that failed, the warnings of a review made under other rules or whose
# blocks today's rules do not give, and the version of a build.
STILL_AUTO = "some blocks are still auto: confirm, edit or remove them before saving"
EXCLUDED = "session {sid} is excluded, include it first"
REFUSED = "edit {number} ({what}): {reason}"
AT_FRAME, AT_FRAMES = "{op} at frame {frame}", "{op} at frames {frame_start} to {frame_end}"
NOT_IN_DATASET = "session {sid} is not in the dataset: {reason}"
BUILD_ERROR = "{kind}: {text}"
OTHER_RULES = "reviewed under other rules"
SAVED_DIFFER = "saved blocks differ from the blocks today's rules give"
CODE_VERSION = "trajectory {} {}"


def picked(row, keys):
    """
    The row with only these keys.
    """
    return {key: row[key] for key in keys}


def nothing_built(error=None):
    """
    The outcome of a build that wrote no block: none built, none failed, and the error that stopped it when one did.
    """
    return {"built": 0, "failed": [], "build_error": error}


def review_facts(review, kinds, rate_hz):
    """
    What the index shows of a review: whether a person has reviewed the session (it is excluded, or has edits, or a block no longer auto), when and by whom, the blocks kept and their seconds per epoch kind, the notes.
    """
    review = review or {}
    kept = [b for b in review.get("blocks", []) if b["status"] in KEPT]
    touched = review.get("excluded", False) or bool(review.get("edits")) or any(b["status"] != AUTO for b in review.get("blocks", []))
    return {"reviewed": touched, "reviewed_at": review.get("reviewed_at"), "reviewed_by": review.get("reviewed_by"),
            "excluded": review.get("excluded", False), "excluded_by": review.get("excluded_by"), "excluded_at": review.get("excluded_at"),
            "n_confirmed": len(kept), "notes": review.get("notes", ""),
            "confirmed_s": {kind: sum((b["frame_end"] - b["frame_start"] + 1) / rate_hz for b in kept if b["epoch"] == kind) for kind in kinds}}


def described(edit):
    """
    The edit as a person reads it: its op and, when it has one, the frame or frames it lies at.
    """
    if "frame" in edit:
        return AT_FRAME.format(**edit)
    return AT_FRAMES.format(**edit) if "frame_start" in edit else edit["op"]


def shaped(blocks):
    """
    The blocks as compared with the saved ones: the review's keys only, an empty note being no note as the old files wrote it.
    """
    return [{**picked(b, BLOCK_KEYS), "note": b["note"] or None} for b in blocks]


def offset_applied(review, requested):
    """
    The start offset a session is loaded or played with: the one requested when it is not none, else the one the saved review holds, else none for the yaml's. A query cannot carry null, so absent means the review's.
    """
    return requested if requested is not None else (review or {}).get(START_OFFSET)


def warnings_of(found, review):
    """
    The session's warnings, with one more when its review was saved under rules other than today's (the saved rules went through json, so today's do too).
    """
    other = review is not None and review["rules"] != json.loads(json.dumps(RULES))
    return found["warnings"] + ([OTHER_RULES] if other else [])


class ReviewManager:
    """
    Stateless: the engine and the accesses it works with, handed in at the composition root.
    """

    def __init__(self, trajectory, transformed, processed, environment, code_version):
        self.trajectory, self.transformed, self.processed, self.environment = trajectory, transformed, processed, environment
        self.code_version = code_version

    def index(self):
        """
        Every session with an arena or track epoch, the dataset's sessions first, then unreviewed, then the oldest review first.
        """
        tables = self.transformed.sessions()
        funnel, built = self.trajectory.funnel(tables, RULES), [row["session_id"] for row in self.processed.blocks()]
        rows = []
        for session in tables["sessions"]:
            sid = session["session_id"]
            epochs = [e for e in tables["epochs"] if e["session_id"] == sid]
            if not any(e["epoch"] in RULES["epochs"] for e in epochs):
                continue
            runs = [r for r in tables["runs"] if r["session_id"] == sid]
            rows.append({**session, "date": str(session["date"]), "epochs": [picked(e, EPOCH_KEYS) for e in epochs],
                         "n_runs": len(runs), "n_clean_runs": sum(1 for r in runs if r["clean"]),
                         "in_dataset": funnel[sid]["in_dataset"], "reason": funnel[sid]["reason"],
                         "annotated_exclude": funnel[sid]["annotated_exclude"], "built": built.count(sid),
                         **review_facts(self.processed.review(sid), RULES["epochs"], session["rate_hz"])})
        return sorted(rows, key=lambda s: (not s["in_dataset"], s["reviewed"], s["reviewed_at"] or ""))

    def load(self, sid, settings, start_offset_m=None):
        """
        A session for the replay as a header: its facts, epochs, runs, whether the rules keep it, the geometry of its environments by name built with the start offset that applies (the request's, else the review's, else the yaml's, which the header gives as start_offset_default_m), what the engine draws, its review and its blocks with their window counts.
        """
        review = self.processed.review(sid)
        offset = offset_applied(review, start_offset_m)
        arrays, environments, found = self._session(sid, offset)
        made = self._made(arrays, environments, found, [] if review is None else review["edits"], settings)
        warnings = warnings_of(found, review)
        if review is not None and shaped(made["blocks"]) != shaped(review["blocks"]):
            warnings.append(SAVED_DIFFER)
        row, funnel = arrays["session"], self._funnel(sid)
        return {**picked(row, SESSION_KEYS), "date": str(row["date"]), "n_frames": found["n_frames"], "in_dataset": funnel["in_dataset"],
                "reason": funnel["reason"], "annotated_exclude": funnel["annotated_exclude"], "excluded": review is not None and review["excluded"],
                "epochs": [picked(e, EPOCH_KEYS) for e in arrays["epochs"]],
                "runs": [picked(r, RUN_KEYS) for r in arrays["runs"]], "selected_epochs": [e["epoch"] for e in found["epochs"]],
                "n_initial_blocks": len(found["initial_blocks"]), "environments": environments, "rules": found["rules"], **picked(found, DRAWN_KEYS), "warnings": warnings,
                "start_offset_m": offset, "start_offset_default_m": self._yaml_offset(arrays), "review": review, **made}

    def arrays(self, sid, start_offset_m=None):
        """
        A session's arrays over every frame in metres, registered with the start offset that applies, what the page plays, without the blocks and their windows.
        """
        offset = offset_applied(self.processed.review(sid), start_offset_m)
        return picked(self._session(sid, offset)[2]["kinematics"], ARRAY_KEYS)

    def preview(self, sid, edits, settings, start_offset_m=None):
        """
        The blocks the whole edit list makes of the initial blocks with their window counts, the edits refused, the cuts and the flagged runs, registered with this start offset as given, none being the yaml's and not the review's, nothing written.
        """
        arrays, environments, found = self._session(sid, start_offset_m)
        return self._made(arrays, environments, found, edits, settings)

    def save_blocks(self, sid, edits, notes, settings, start_offset_m=None):
        """
        Apply the edits and write the review whole with this start offset exactly as given (none is the yaml's and clears a saved one), refused with its reason when an edit is illegal or a block is still auto, then build the session's blocks from it, a failure of the build coming back as build_error, the review's file named in the result.
        """
        self._require_in_dataset(sid)
        previous = self.processed.review(sid) or {}
        if previous.get("excluded"):
            raise Invalid(EXCLUDED.format(sid=sid))
        arrays, _, found = self._session(sid, start_offset_m)
        applied = self.trajectory.apply(found["initial_blocks"], edits, found)
        if applied["refusals"]:
            first = applied["refusals"][0]
            raise Invalid(REFUSED.format(number=first["index"] + 1, what=described(edits[first["index"]]), reason=first["reason"]))
        if any(block["status"] == AUTO for block in applied["blocks"]):
            raise Invalid(STILL_AUTO)
        review = {"session_id": sid, "reviewed_by": getpass.getuser(), "reviewed_at": clock.iso_now(), "converter_manifest_timestamp": arrays["stamp"],
                  "rules": found["rules"], "blocks": applied["blocks"], "cuts": applied["cuts"], "flagged_runs": applied["flagged_runs"],
                  "notes": notes, "edits": edits, "excluded": False, "excluded_by": previous.get("excluded_by"), "excluded_at": previous.get("excluded_at"),
                  START_OFFSET: start_offset_m}
        written = self.processed.write_review(sid, review)
        return {"review": review, "replaced": written["replaced"], "file": written["file"], **self._built(sid, settings)}

    def exclude(self, sid, excluded, note, settings):
        """
        Record that the person excluded the session or took it back, in its review rewritten whole with the flag, who and when it was set and the note appended to the notes, or in a new review of the initial blocks as they are when it had none (none when the funnel leaves the session out). Excluding then builds the session empty at once, so its blocks leave the build. Including writes the review only, unless the review was only the exclusion's (never reviewed, no edits, every block auto), which goes with the session's build, leaving the session as before.
        """
        review = self.processed.review(sid) or self._exclusion_review(sid)
        review = {**review, "excluded": excluded, "notes": "\n".join(text for text in (review["notes"], note) if text)}
        if excluded:
            review = {**review, "excluded_by": getpass.getuser(), "excluded_at": clock.iso_now()}
        elif review["reviewed_at"] is None and not review["edits"] and all(b["status"] == AUTO for b in review["blocks"]):
            gone = self.processed.delete_review(sid)
            return {"review": None, "replaced": False, "file": gone["file"], "deleted": True, **self._unbuilt(sid)}
        written = self.processed.write_review(sid, review)
        return {"review": review, "replaced": written["replaced"], "file": written["file"], "deleted": False, **(self._built(sid, settings) if excluded else nothing_built())}

    def rebuild_all(self, settings):
        """
        Build the blocks of every reviewed session again, each with its built, failed and build_error. An excluded session is written with no blocks, which removes its stale ones, and listed with its notes. A review of a session the funnel leaves out (no frames, no epoch of the rules) is not built and listed with the funnel's reason. The totals count them all.
        """
        funnel = self.trajectory.funnel(self.transformed.sessions(), RULES)
        reviews, results, skipped = {sid: self.processed.review(sid) for sid in self.processed.reviews()}, {}, {}
        for sid, review in reviews.items():
            if not review["excluded"] and sid in funnel and not funnel[sid]["in_dataset"]:
                skipped[sid] = funnel[sid]["reason"]
            else:
                results[sid] = self._built(sid, settings)
        excluded = {sid: review["notes"] for sid, review in reviews.items() if review["excluded"]}
        return {"sessions": results, "skipped": skipped, "excluded": excluded,
                "totals": {"sessions": len(results), "built": sum(r["built"] for r in results.values()),
                           "failed": sum(len(r["failed"]) for r in results.values()),
                           "errors": sum(r["build_error"] is not None for r in results.values()), "skipped": len(skipped), "excluded": len(excluded)}}

    def _funnel(self, sid):
        """
        Whether the rules keep the session in the dataset and the reason when not, NotFound when the transformed folder has no such session.
        """
        funnel = self.trajectory.funnel(self.transformed.sessions(), RULES)
        if sid not in funnel:
            raise NotFound(f"no session {sid}")
        return funnel[sid]

    def _exclusion_review(self, sid):
        """
        The review an exclusion writes for a session with none: the initial blocks as they are, no edits, never reviewed, none when the funnel leaves the session out. NotFound when the session is not in the transformed folder or has no frames.
        """
        arrays, environments = self._frames(sid)
        blocks, rules = [], RULES
        if self._funnel(sid)["in_dataset"]:
            found = self.trajectory.session(arrays, environments, RULES)
            blocks, rules = self.trajectory.apply(found["initial_blocks"], [], found)["blocks"], found["rules"]
        return {"session_id": sid, "reviewed_by": None, "reviewed_at": None, "converter_manifest_timestamp": arrays["stamp"], "rules": rules, "blocks": blocks,
                "cuts": [], "flagged_runs": [], "notes": "", "edits": [], "excluded": False, "excluded_by": None, "excluded_at": None, START_OFFSET: None}

    def _unbuilt(self, sid):
        """
        Remove the session's blocks and metadata, an I/O failure coming back as build_error like a build's.
        """
        try:
            self.processed.delete_build(sid)
            return nothing_built()
        except OSError as error:
            return nothing_built(BUILD_ERROR.format(kind=type(error).__name__, text=error))

    def _require_in_dataset(self, sid):
        """
        Invalid with the funnel's reason when the funnel leaves the session out (no frames, no epoch of the rules), since only a session in the dataset is saved and built.
        """
        funnel = self._funnel(sid)
        if not funnel["in_dataset"]:
            raise Invalid(NOT_IN_DATASET.format(sid=sid, reason=funnel["reason"]))

    def _frames(self, sid, start_offset_m=None):
        """
        The session as TransformedAccess gives it and the geometry by name of the environments of its epochs of the rules' kinds, built with this start offset when one is given, so a session the rules leave out can be viewed too.
        """
        arrays = self.transformed.session(sid)
        return arrays, {e["environment"]: self.environment.environment(e["environment"], start_offset_m) for e in arrays["epochs"] if e["epoch"] in RULES["epochs"]}

    def _session(self, sid, start_offset_m=None):
        """
        The session, its environments built with this start offset and the engine's session over them.
        """
        arrays, environments = self._frames(sid, start_offset_m)
        return arrays, environments, self.trajectory.session(arrays, environments, RULES)

    def _yaml_offset(self, arrays):
        """
        The start offset the yaml of the session's track environment sets, 0.0 when it sets none or the session has no track epoch.
        """
        names = [e["environment"] for e in arrays["epochs"] if e["epoch"] == TRACK]
        return self.environment.environment(names[0])["params"].get("start_offset", 0.0) if names else 0.0

    def _windows(self, block, settings):
        """
        The window count and the verdict of a built block at the settings.
        """
        found = self.trajectory.windows(block, settings, RULES)
        return {"count": found["count"], "verdict": found["verdict"]}

    def _made(self, arrays, environments, found, edits, settings):
        """
        The blocks the edits make of the initial blocks, each kept one with its window count and verdict and the problems of the block as built, a dropped one with neither, with the edits refused, the cuts and the flagged runs.
        """
        applied = self.trajectory.apply(found["initial_blocks"], edits, found)
        # The blocks are built as a review that confirms every block not dropped, only their windows are read.
        kept = [{**b, "status": CONFIRMED} for b in applied["blocks"] if b["status"] != DROPPED]
        built = self.trajectory.blocks(arrays, {"blocks": kept, "flagged_runs": applied["flagged_runs"], "reviewed_by": None}, environments, RULES)
        by_id = {b["row"]["block_id"]: b for b in built["blocks"]}
        blocks = [{**b, "windows": self._windows(by_id[b["block_id"]], settings) if b["block_id"] in by_id else None,
                   "problems": by_id[b["block_id"]]["problems"] if b["block_id"] in by_id else []} for b in applied["blocks"]]
        return {"blocks": blocks, "refusals": applied["refusals"], "cuts": applied["cuts"], "flagged_runs": applied["flagged_runs"]}

    def _built(self, sid, settings):
        """
        Build the session's blocks and say how many were written and which failed, a file or validation failure of the build as build_error and nothing written, any other error left to crash.
        """
        try:
            return {**self._build(sid, settings), "build_error": None}
        except (OSError, Invalid, NotFound) as error:
            return nothing_built(BUILD_ERROR.format(kind=type(error).__name__, text=error))

    def _build(self, sid, settings):
        """
        Write the session's blocks and metadata from the review on disk, the one build step of a save and a rebuild. An excluded session is written with no blocks and metadata saying so.
        """
        review = self.processed.review(sid)
        offset = review.get(START_OFFSET)
        if review["excluded"]:
            made = {"blocks": [], "frame": None, "warnings": []}
        else:
            self._require_in_dataset(sid)
            arrays, environments = self._frames(sid, offset)
            made = self.trajectory.blocks(arrays, review, environments, RULES)
        kept, failed, windows = [], [], {}
        for block in made["blocks"]:
            block_id = block["row"]["block_id"]
            # The processor's policy for now: a block with a problem is listed in failed and not written. Flip the test to write it anyway.
            if block["problems"]:
                failed.append({"block_id": block_id, "problems": block["problems"]})
                continue
            kept.append({"row": block["row"], "arrays": block["arrays"]})
            windows[block_id] = self._windows(block, settings)
        stamp = {key: review[key] for key in ("reviewed_at", "converter_manifest_timestamp")}
        metadata = {"rules": RULES, START_OFFSET: offset, "settings": settings, "review_stamp": stamp, "code_version": CODE_VERSION.format(VERSION, self.code_version),
                    "built_at": clock.iso_now(), "windows": windows, "frame": made["frame"], "excluded": review["excluded"],
                    "warnings": warnings_of(made, review), "failed": failed}
        self.processed.write_blocks(sid, kept, metadata)
        return {"built": len(kept), "failed": failed}
