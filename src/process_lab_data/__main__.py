"""
Turn the converter's tables into labelled trajectory blocks in metres, run as pixi run process-lab-data.
"""

import argparse
import contextlib
import io
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from axis_of_travel_rnn import trajectory
from proj_helpers import paths
from proj_helpers.paths import repo_root

from . import frame, labels, output, select

# What a run writes under PROCESSED_LAB_DATA (spec Outputs): one blocks folder and one blocks csv per epoch kind, and
# the manifest, each rewritten whole on every run, the blocks folders removed first so the files on disk are exactly
# the blocks the csv files and the manifest list, after a review drops a block, a block fails or --only narrows the run
# as much as on a first run. The review files RatReplay saves live under REVIEW, one json per session, the one thing a
# run keeps, and a block of one is built when its status is one of KEPT_STATUSES, dropped otherwise, while an unreviewed
# session's blocks carry the status AUTOMATIC. The converter's manifest, whose timestamp the run records, sits beside
# its tables.
BLOCKS_DIR = "blocks"
BLOCKS_CSV = tuple(f"{kind}/blocks.csv" for kind in select.EPOCHS)
MANIFEST = "manifest.json"
REVIEW = "review"
KEPT_STATUSES = ("confirmed", "edited")
AUTOMATIC = "automatic"
CONVERTER_MANIFEST = "manifest.json"

# The checks (spec Checks). Per block, each a fail that skips writing it: no NaN position, every step in t within
# T_STEP_TOLERANCE_S of one frame, the block inside its epoch, run labels agreeing with runs.csv, no frame shared with
# another block of the session. Per session, each a warn: the track scale's two axis estimates within frame.AXIS_AGREE of
# their mean of each other and each kind's LED separation inside LED_SEPARATION_M, the implants' 6 to 7 cm. The LED
# offset swap warning (frame.offset_warnings) is made over the sessions of the run at its end.
T_STEP_TOLERANCE_S = 1e-6
LED_SEPARATION_M = (0.04, 0.08)
RULE_MODULES = {"select": select, "frame": frame, "labels": labels, "trajectory": trajectory}


def parse_args(argv):
    """
    The command line: --dry-run with --list, --frames and --report FILE, and --only PREFIX.
    """
    parser = argparse.ArgumentParser(
        prog="process_lab_data", description="Turn the converter's tables into trajectory blocks in metres.")
    parser.add_argument("--dry-run", action="store_true", help="print the funnel counts and what would be written, then stop")
    parser.add_argument("--only", metavar="PREFIX",
                        help="sessions whose id is PREFIX or continues it after an underscore")
    parser.add_argument("--list", action="store_true", help="with --dry-run, also print one line per block")
    parser.add_argument("--frames", action="store_true",
                        help="with --dry-run, also print the frame parameters per session and the LED offset warnings")
    parser.add_argument("--report", metavar="FILE",
                        help="with --dry-run, write the whole report (blocks, reviews, frames) to FILE as well")
    parser.add_argument("--confirmed-only", action="store_true",
                        help="build only the confirmed and edited blocks of reviewed sessions, nothing from unreviewed ones")
    return parser.parse_args(argv)


def refuse(message):
    """
    Print a configuration problem to stderr and exit 2.
    """
    print(f"process_lab_data: {message}", file=sys.stderr)
    raise SystemExit(2)


def roots(config):
    """
    The resolved transformed lab data folder and the resolved output folder, or exit 2 naming what is wrong.
    """
    for key in ("TRANSFORMED_LAB_DATA", "PROCESSED_LAB_DATA"):
        if not config.get(key):
            refuse(f"{paths.LOCAL_CONFIG} has no {key}")
    source = Path(str(config["TRANSFORMED_LAB_DATA"])).expanduser().resolve()
    root = Path(str(config["PROCESSED_LAB_DATA"])).expanduser().resolve()
    tables = [f"{name}.csv" for name in select.TABLES]
    if not all((source / name).is_file() for name in tables) or not (source / select.FRAMES).is_dir():
        refuse(f"TRANSFORMED_LAB_DATA {source} is not a folder holding {', '.join(tables)} and a {select.FRAMES} folder")
    if root == source or source in root.parents:
        refuse(f"PROCESSED_LAB_DATA {root} is the transformed lab data or inside it")
    if root in source.parents:
        refuse(f"PROCESSED_LAB_DATA {root} contains the transformed lab data {source}")
    repo = repo_root().resolve()
    if root == repo or repo in root.parents:
        refuse(f"PROCESSED_LAB_DATA {root} is the repository {repo} or inside it")
    return source, root


def print_counts(counts):
    """
    Print the funnel, one line per step in order.
    """
    print("funnel:")
    for step, count in counts:
        print(f"  {step}: {count}")


def review_path(root, session_id):
    """
    The session's review file under the output folder.
    """
    return root / REVIEW / f"{session_id}.json"


def read_review(root, session_id):
    """
    The session's review file as a dict, or None when the session was not reviewed.
    """
    path = review_path(root, session_id)
    return json.loads(path.read_text()) if path.is_file() else None


def dry_run(blocks, root, listing, session_ids):
    """
    Print the blocks that would be written per kind, their duration spread, the sessions with a review file, the files to write and, with --list, each block.
    """
    print(f"dry run, nothing is written (cut rules: {select.GAP_LIGHTS} lights unfilled over max_gap, a jump over "
          f"{select.JUMP_PX:g} px, {select.PAUSE_MARGIN_SEC:g} s margins at pauses, jumps and epoch bounds)")
    print("blocks per kind: count, total s, duration s at min, median, 90th percentile, max")
    for kind in select.EPOCHS:
        seconds = [b["duration_s"] for b in blocks if b["epoch"] == kind]
        if seconds:
            spread = ", ".join(f"{v:.0f}" for v in np.percentile(seconds, [0, 50, 90, 100]))
            print(f"  {kind}: {len(seconds)} blocks, {sum(seconds):.0f} s, durations {spread}")
    if listing:
        print(f"blocks ({len(blocks)}), per session with its review state:")
        for session_id in session_ids:
            print(f"  {session_id}: {review_detail(read_review(root, session_id))}")
            for b in blocks:
                if b["session_id"] == session_id:
                    print(f"    {b['block_id']}  {b['n_frames']} frames  {b['duration_s']:.1f} s")
    reviewed = sum(1 for s in session_ids if review_path(root, s).is_file())
    print(f"sessions with a review file: {reviewed} of {len(session_ids)}")
    print(f"files to write under {root}:")
    for name in BLOCKS_CSV + (MANIFEST,):
        print(f"  {name}")


def check_text(kind, parameters):
    """
    The kind's check on its scale: the track's two axis estimates, the arena's extent ratio.
    """
    if kind == frame.TRACK:
        return f"x {parameters['scale_x_px_per_m']:.0f}, y {parameters['scale_y_px_per_m']:.0f}"
    return f"extent {parameters['arena_extent_ratio']:.2f}"


def scale_text(parameters):
    """
    Each epoch kind's scale in px per m with its check and the LED separation it implies, as one piece of a session's line.
    """
    return "  ".join(f"{kind} {p['scale_px_per_m']:.0f} px/m ({check_text(kind, p)}, LEDs {100 * p['led_separation_m']:.1f} cm)"
                     for kind in select.EPOCHS if (p := parameters.get(kind)))


def rotation_text(parameters):
    """
    The track rotation in degrees with its concentration.
    """
    return f"rotation {np.degrees(parameters[frame.TRACK]['rotation_rad']):.1f} deg ({parameters[frame.TRACK]['rotation_concentration']:.2f})"


def offset_text(parameters):
    """
    The LED offset in degrees with its concentration and count.
    """
    return f"offset {np.degrees(parameters['led_offset_rad']):.1f} deg ({parameters['led_offset_r']:.2f}, n {parameters['led_offset_n']})"


def ignored_reviews(root, session_ids):
    """
    A warning per review file whose session is outside the funnel, so a saved review is never dropped in silence.
    """
    folder = root / REVIEW
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    return [f"review file for {path.stem} ignored, the session is outside the funnel" for path in files if path.stem not in session_ids]


def swap_warnings(offsets, subject_of):
    """
    One warning line per session whose LED offset lies over OFFSET_WARN_DEG from its rat's median.
    """
    return [f"{session_id} LED offset {degrees:+.0f} deg from its rat's median, over {frame.OFFSET_WARN_DEG:g}: LEDs swapped?"
            for session_id, degrees in frame.offset_warnings(offsets, subject_of)]


def print_frames(source, epochs, tables):
    """
    Print the frame parameters of every surviving session, reading its frames once, then the scale and LED offset warnings and each rat's median offset and LED separation.
    """
    subject_of = {s["session_id"]: s["subject_id"] for s in tables["sessions"]}
    offsets, tracks = {}, {}
    print("frame parameters: scale per kind (the track's x and y estimates, the arena's extent ratio, the LED separation each "
          "implies), track rotation (concentration), LED offset (concentration, n)")
    for session_id in dict.fromkeys(e["session_id"] for e in epochs):
        parameters = frame.frame_parameters(select.read_frames(source, session_id),
                                            [e for e in epochs if e["session_id"] == session_id],
                                            [r for r in tables["runs"] if r["session_id"] == session_id])
        offsets[session_id] = parameters["led_offset_rad"]
        tracks[session_id] = parameters[frame.TRACK]
        print(f"  {session_id}  {subject_of[session_id]}  {scale_text(parameters)}  {rotation_text(parameters)}  {offset_text(parameters)}")
    for session_id, track in tracks.items():
        if (apart := frame.axis_disagreement(track)) > frame.AXIS_AGREE:
            print(f"  warning: {session_id} track scale x and y differ by {100 * apart:.0f} percent, over {100 * frame.AXIS_AGREE:g}: "
                  "an outer corridor peak missed?")
    for warning in swap_warnings(offsets, subject_of):
        print(f"  warning: {warning}")
    print("median LED offset and LED separation per rat:")
    separation_of = frame.separation_medians({s: track["led_separation_m"] for s, track in tracks.items()}, subject_of)
    for subject, median in frame.offset_medians(offsets, subject_of).items():
        print(f"  {subject}  {np.degrees(median):.1f} deg  {100 * separation_of[subject]:.1f} cm")


def constants(module):
    """
    The module's named values, its uppercase module-level names.
    """
    return {name: value for name, value in vars(module).items() if name.isupper()}


def rules():
    """
    Every constant the blocks were built under, by module and name, the check thresholds included.
    """
    return {**{name: constants(module) for name, module in RULE_MODULES.items()},
            "checks": {"T_STEP_TOLERANCE_S": T_STEP_TOLERANCE_S, "AXIS_AGREE": frame.AXIS_AGREE, "LED_SEPARATION_M": LED_SEPARATION_M}}


def rules_differ(review):
    """
    The rules the review was saved under whose value is not select's constant of that name today, each with the saved and the current value.
    """
    return {name: {"saved": saved, "current": getattr(select, name)} for name, saved in review["rules"].items()
            if saved != getattr(select, name)}


def session_blocks(automatic, review, session_id, rate_hz, confirmed_only=False):
    """
    The blocks to build: the review's kept blocks when the session was reviewed, else the automatic ones as AUTOMATIC, or none under confirmed_only.
    """
    if review is None:
        return [] if confirmed_only else [{**b, "status": AUTOMATIC, "reviewed_by": None} for b in automatic]
    kept = [b for b in review["blocks"] if b["status"] in KEPT_STATUSES]
    return [{"block_id": b["block_id"], "session_id": session_id, "epoch": b["epoch"], "environment": b["environment"],
             "frame_start": b["frame_start"], "frame_end": b["frame_end"], "n_frames": b["frame_end"] - b["frame_start"] + 1,
             "duration_s": (b["frame_end"] - b["frame_start"] + 1) / rate_hz, "status": b["status"],
             "reviewed_by": review["reviewed_by"]} for b in kept]


def block_slice(frames, block):
    """
    The index slice of the block's frames in the session's contiguous frames.
    """
    first = int(np.searchsorted(frames["frame"], block["frame_start"]))
    return slice(first, first + block["n_frames"])


def block_columns(frames, at, parameters, kind, filled, fill_kind, runs, rate_hz):
    """
    The block's columns as arrays over its slice: the lab frame, t from the block start, position and heading in the room, speed and turn rate from the measured heading, the lights, the fills and the labels.
    """
    p = parameters[kind]
    x, y = frame.to_room(frames["mashup_x"][at], frames["mashup_y"][at], p["scale_px_per_m"], p["flip"], p["rotation_rad"], p["offset_m"])
    t = frames["t"][at] - frames["t"][at.start]
    measured = frame.heading_to_room(frames["head_dir"][at], parameters["led_offset_rad"], p["rotation_rad"])
    speed, turn_rate = trajectory.kinematics(t, x, y, measured, rate_hz)
    labelled = labels.label_frames({"frame": frames["frame"][at], "epoch": frames["epoch"][at], "speed": speed}, runs, rate_hz)
    return {"frame": frames["frame"][at], "t": t, "x": x, "y": y,
            "heading": frame.heading_to_room(filled[at], parameters["led_offset_rad"], p["rotation_rad"]),
            "speed": speed, "turn_rate": turn_rate,
            "n_lights": (2 - frames["unfilled_front"][at] - frames["unfilled_back"][at]).astype(np.int8),
            "heading_filled": fill_kind[at] == select.INTERPOLATED, "heading_held": fill_kind[at] == select.HELD,
            "filled_front": frames["filled_front"][at], "filled_back": frames["filled_back"][at], **labelled}


def result(bad, detail, level):
    """
    One check's result in the converter's shape: the level (fail or warn) when bad, else pass, with its detail dict.
    """
    return {"status": level if bad else "pass", "detail": detail}


def run_label_mismatches(frame_numbers, run, runs):
    """
    The run numbers whose labelled frames are not the lab's range clipped to the block less the frames of later runs, and the labelled numbers no run of the block has.
    """
    expected = {}
    for i, r in enumerate(runs):
        own = (frame_numbers >= r["frame_start"]) & (frame_numbers <= r["frame_end"])
        for later in runs[i + 1:]:
            own &= (frame_numbers < later["frame_start"]) | (frame_numbers > later["frame_end"])
        if own.any():
            expected[r["run"]] = own
    labelled = set(np.unique(run[run > 0]).tolist())
    return sorted([n for n, own in expected.items() if not np.array_equal(own, run == n)] + list(labelled - expected.keys()))


def block_checks(block, columns, epoch, runs, others, rate_hz):
    """
    The block's checks: a finite position, t steps of one frame, inside its epoch, run labels agreeing with runs.csv, no frame shared with another block, each pass or fail with its detail.
    """
    nan = int((np.isnan(columns["x"]) | np.isnan(columns["y"])).sum())
    bad_steps = int((np.abs(np.diff(columns["t"]) - 1 / rate_hz) > T_STEP_TOLERANCE_S).sum())
    outside = block["frame_start"] < epoch["frame_start"] or block["frame_end"] > epoch["frame_end"]
    mismatched = run_label_mismatches(columns["frame"], columns["run"], runs)
    overlapping = [b["block_id"] for b in others if b["frame_start"] <= block["frame_end"] and block["frame_start"] <= b["frame_end"]]
    return {"position_finite": result(nan, {"nan_frames": nan}, "fail"),
            "t_steps": result(bad_steps, {"bad_steps": bad_steps}, "fail"),
            "inside_epoch": result(outside, {"epoch": [epoch["frame_start"], epoch["frame_end"]]}, "fail"),
            "run_labels": result(mismatched, {"mismatched_runs": mismatched}, "fail"),
            "one_block": result(overlapping, {"overlapping": overlapping}, "fail")}


def session_checks(parameters):
    """
    The session's checks, each pass or warn: the track scale's axis estimates within frame.AXIS_AGREE of each other, each kind's LED separation inside LED_SEPARATION_M.
    """
    apart = frame.axis_disagreement(parameters[frame.TRACK])
    separations = {kind: parameters[kind]["led_separation_m"] for kind in select.EPOCHS if kind in parameters}
    outside = {kind: s for kind, s in separations.items() if not LED_SEPARATION_M[0] <= s <= LED_SEPARATION_M[1]}
    return {"scale_axes": result(apart > frame.AXIS_AGREE, {"disagreement": apart}, "warn"),
            "led_separation": result(outside, {"led_separation_m": separations}, "warn")}


def session_warnings(session_id, checks, review):
    """
    The session's warning lines: each warn check in words, and the review's rules differing from today's.
    """
    warnings = []
    if checks["scale_axes"]["status"] == "warn":
        warnings.append(f"{session_id} track scale x and y differ by {100 * checks['scale_axes']['detail']['disagreement']:.0f} percent, "
                        f"over {100 * frame.AXIS_AGREE:g}: an outer corridor peak missed?")
    for kind, s in checks["led_separation"]["detail"]["led_separation_m"].items():
        if not LED_SEPARATION_M[0] <= s <= LED_SEPARATION_M[1]:
            warnings.append(f"{session_id} {kind} LED separation {100 * s:.1f} cm outside {100 * LED_SEPARATION_M[0]:g} to {100 * LED_SEPARATION_M[1]:g}")
    if review is not None and (differing := rules_differ(review)):
        warnings.append(f"{session_id} reviewed under other rules: " + ", ".join(
            f"{name} {d['saved']} now {d['current']}" for name, d in differing.items()))
    return warnings


def block_row(block, session, parameters, columns):
    """
    One blocks csv row: the block, its session, its runs, trips and heading fill seconds, its status and reviewer, and the parameters it was built under.
    """
    rate_hz, run, trip, p = session["rate_hz"], columns["run"], columns["trip"], parameters[block["epoch"]]
    return {"block_id": block["block_id"], "session_id": session["session_id"], "subject_id": session["subject_id"],
            "date": str(session["date"]), "protocol": session["protocol"], "environment": block["environment"],
            "epoch": block["epoch"], "frame_start": block["frame_start"], "frame_end": block["frame_end"],
            "n_frames": block["n_frames"], "duration_s": block["duration_s"],
            "n_runs": len(np.unique(run[run > 0])), "n_clean_runs": len(np.unique(run[(run > 0) & columns["clean"]])),
            "n_trips": len(np.unique(np.abs(trip[trip != 0]))), "n_complete_trips": len(np.unique(trip[trip > 0])),
            "heading_lost_s": float(np.isnan(columns["heading"]).sum() / rate_hz),
            "heading_filled_s": float(columns["heading_filled"].sum() / rate_hz),
            "heading_held_s": float(columns["heading_held"].sum() / rate_hz),
            "status": block["status"], "reviewed_by": block["reviewed_by"],
            "scale_px_per_m": p["scale_px_per_m"], "rotation_rad": p["rotation_rad"],
            "led_offset_rad": parameters["led_offset_rad"], "kinematics_version": trajectory.KINEMATICS_VERSION}


def session_entry(parameters, checks, review, written, failed, dropped):
    """
    The session's manifest entry: its frame parameters and checks, how it was reviewed, and the blocks written, failed and dropped by the review.
    """
    return {"frame_parameters": parameters, "checks": checks, "reviewed": review is not None,
            "reviewed_by": review["reviewed_by"] if review else None, "reviewed_at": review["reviewed_at"] if review else None,
            "review_rules": review["rules"] if review else None, "rules_differ": bool(review and rules_differ(review)),
            "blocks_written": written, "blocks_failed": sorted(failed), "blocks_dropped_by_review": dropped}


def process_session(frames, root, session, epochs, runs, review, automatic, confirmed_only=False):
    """
    Build, check and write the session's blocks from its frames: the manifest entry, the csv rows, the block ids written, the failed blocks with their failed checks and the warnings.
    """
    session_id, rate_hz = session["session_id"], session["rate_hz"]
    parameters = frame.frame_parameters(frames, epochs, runs)
    filled, fill_kind = select.fill_heading(frames["head_dir"], frames["t"], frame.still(frames, epochs), rate_hz)
    flagged = set(review["flagged_runs"]) if review else set()
    labelled_runs = [r for r in runs if r["run"] not in flagged]
    blocks = session_blocks(automatic, review, session_id, rate_hz, confirmed_only)
    epoch_of = {e["epoch"]: e for e in epochs}
    rows, written, failed = [], [], {}
    for block in blocks:
        at = block_slice(frames, block)
        columns = block_columns(frames, at, parameters, block["epoch"], filled, fill_kind, labelled_runs, rate_hz)
        checks = block_checks(block, columns, epoch_of[block["epoch"]], labels.runs_in(columns["frame"], labelled_runs),
                              [b for b in blocks if b is not block], rate_hz)
        if failing := [name for name, r in checks.items() if r["status"] == "fail"]:
            failed[block["block_id"]] = {name: checks[name] for name in failing}
            continue
        output.write_block(output.block_table(columns), root / block["epoch"] / BLOCKS_DIR / f"{block['block_id']}.parquet")
        rows.append(block_row(block, session, parameters, columns))
        written.append(block["block_id"])
    checks = session_checks(parameters)
    dropped = [b["block_id"] for b in review["blocks"] if b["status"] not in KEPT_STATUSES] if review else []
    return {"entry": session_entry(parameters, checks, review, written, failed, dropped), "rows": rows, "written": written,
            "failed": failed, "warnings": session_warnings(session_id, checks, review)}


def review_text(review):
    """
    How a session was reviewed, for its line: by whom and when, or unreviewed.
    """
    return f"reviewed by {review['reviewed_by']} {review['reviewed_at']}" if review else "unreviewed"


def review_detail(review):
    """
    The dry run's line on a session's review: the blocks by status and the flagged runs, or that the automatic blocks are written.
    """
    if review is None:
        return "unreviewed, the automatic blocks are written"
    statuses = ", ".join(f"{n} {status}" for status, n in sorted(Counter(b["status"] for b in review["blocks"]).items()))
    return (f"{review_text(review)}: {statuses}, {len(review.get('flagged_runs', []))} runs flagged, "
            "the confirmed and edited blocks are written")


def ordered_sessions(sessions, epochs):
    """
    The sessions with a surviving epoch in recording order: by rat, date and id.
    """
    kept = {e["session_id"] for e in epochs}
    return sorted([s for s in sessions if s["session_id"] in kept], key=lambda s: (s["subject_id"], s["date"], s["session_id"]))


def manifest(counts, only, confirmed_only, source, written, failed, warnings, entries):
    """
    The manifest: the run (when, under which rules and converter output, the funnel, the selection, what was written, what failed and the warnings) and one entry per session.
    """
    return {"run": {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "converter_manifest_timestamp": json.loads((source / CONVERTER_MANIFEST).read_text())["run"]["timestamp"],
                    "rules": rules(), "funnel": dict(counts), "only": only, "confirmed_only": confirmed_only, "written": written, "failed": failed,
                    "warnings": warnings}, "sessions": entries}


def summarize(written, failed, entries, warnings):
    """
    Print how many blocks were written and failed, the failed ids with their checks, how many sessions were reviewed and the warnings.
    """
    reviewed = sum(1 for entry in entries.values() if entry["reviewed"])
    print(f"{len(written)} blocks written, {len(failed)} failed, {reviewed} of {len(entries)} sessions reviewed, {len(warnings)} warnings")
    for block_id, checks in failed.items():
        print(f"  failed: {block_id} ({', '.join(checks)})")
    for warning in warnings:
        print(f"  warning: {warning}")


def run(source, root, tables, epochs, only, counts, confirmed_only=False):
    """
    The real run: the blocks folders of an earlier run removed, each surviving session's blocks built, checked and written in recording order with one line printed, then the csv files and the manifest written whole, 0 when every block was written and 1 when any failed.
    """
    for kind in select.EPOCHS:
        output.remove_folder(root / kind / BLOCKS_DIR)
    rows = {kind: [] for kind in select.EPOCHS}
    entries, written, failed, warnings, automatic, tally, offsets = {}, [], {}, [], [], Counter(), {}
    sessions = ordered_sessions(tables["sessions"], epochs)
    for session in sessions:
        session_id = session["session_id"]
        session_epochs = [e for e in epochs if e["session_id"] == session_id]
        frames = select.read_frames(source, session_id)
        found, counted = select.blocks_in(frames, session, session_epochs)
        automatic += found
        tally += counted
        review = read_review(root, session_id)
        outcome = process_session(frames, root, session, session_epochs, [r for r in tables["runs"] if r["session_id"] == session_id],
                                  review, found, confirmed_only)
        entries[session_id] = outcome["entry"]
        offsets[session_id] = outcome["entry"]["frame_parameters"]["led_offset_rad"]
        written += outcome["written"]
        failed.update(outcome["failed"])
        warnings += outcome["warnings"]
        for row in outcome["rows"]:
            rows[row["epoch"]].append(row)
        print(f"{session_id}  {len(outcome['written'])} blocks written, {len(outcome['failed'])} failed, {review_text(review)}, "
              f"{len(outcome['warnings'])} warnings")
    warnings += swap_warnings(offsets, {s["session_id"]: s["subject_id"] for s in sessions})
    warnings += ignored_reviews(root, {s["session_id"] for s in sessions})
    block_counts = select.block_counts(automatic, tally) + [("blocks, written", len(written)), ("blocks, failed", len(failed))]
    for kind in select.EPOCHS:
        output.write_csv(rows[kind], root / kind / "blocks.csv")
    output.write_json(manifest(counts + block_counts, only, confirmed_only, source, written, failed, warnings, entries), root / MANIFEST)
    print_counts(block_counts)
    summarize(written, failed, entries, warnings)
    return 1 if failed else 0


def main(argv=None, config=None):
    """
    Run the funnel and the dry run, or the real run: 0 when every block was written, 1 when any failed a check, SystemExit 2 for a bad setup.
    """
    args = parse_args(argv)
    source, root = roots(paths.local_config() if config is None else config)
    tables = select.read_tables(source)
    epochs, counts = select.funnel(tables, args.only)
    if args.dry_run:
        blocks, block_counts = select.blocks_of(source, epochs, tables["sessions"])
        with contextlib.redirect_stdout(io.StringIO()) as report:
            print_counts(counts + block_counts)
            if args.confirmed_only:
                print("confirmed only: unreviewed sessions write nothing, reviewed ones their confirmed and edited blocks")
            dry_run(blocks, root, args.list or bool(args.report), list(dict.fromkeys(e["session_id"] for e in epochs)))
            if args.frames or args.report:
                print_frames(source, epochs, tables)
        print(report.getvalue(), end="")
        if args.report:
            Path(args.report).write_text(report.getvalue())
            print(f"report written to {args.report}")
        return 0
    print_counts(counts)
    return run(source, root, tables, epochs, args.only, counts, args.confirmed_only)


if __name__ == "__main__":
    sys.exit(main())
