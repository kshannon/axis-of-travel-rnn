"""
Pass, warn or fail for one session, on the lab's read dicts before converting and on the converted rows after.
"""

import numpy as np

from .convert import KEYS, KIND_END, KIND_START, STAMPS_OK, TAGS
from .readers import COLUMNS, DVT_COLUMNS, TRACKING_REQUIRED

# The lab's sample rate and interpolation limit (tables.md 1.1), a warn when a file differs.
RATE_HZ = 60
MAX_GAP = 30

# How far the stored heading may sit from the angle between the lights, and a painted label from its run's ends.
HEADING_TOLERANCE_RAD = 1e-3
PAINTED_TOLERANCE_FRAMES = 2

# The checks on converted rows that fail a session, every other check only warns.
FAILS = ("keys_unique", "rows_conserved")

# The provenance variable a file may lack without a warn, and the x and y the lab stores for a light it left unfilled.
OPTIONAL_PROVENANCE = "nRealLights"
UNFILLED_XY = 1


def add_result(results, name, status, detail):
    """
    Add one check's status (pass, warn or fail) and its detail dict to the results.
    """
    results[name] = {"status": status, "detail": detail}


def failed(results):
    """
    The sorted names of the checks that failed.
    """
    return sorted(name for name, result in results.items() if result["status"] == "fail")


def warnings(results):
    """
    The sorted names of the checks that warned.
    """
    return sorted(name for name, result in results.items() if result["status"] == "warn")


def _count(mask):
    """
    How many true values, as a plain int.
    """
    return int(np.count_nonzero(mask))


def _col(dvt, name):
    """
    One named column of processedDVT.
    """
    return dvt[:, DVT_COLUMNS[name]]


def check_inputs(record):
    """
    The record with the provenance warn and the fail checks on its read dicts, stopping early at a missing variable.
    """
    trk = record.trk
    results = {}
    missing = sorted(name for name, value in record.provenance().items()
                     if value is None and name != OPTIONAL_PROVENANCE)
    add_result(results, "provenance", "warn" if missing else "pass", {"missing": missing})
    missing = [name for name in TRACKING_REQUIRED if name not in trk]
    add_result(results, "variables_present", "fail" if missing else "pass", {"missing": missing})
    if missing:
        return record.with_results(results)
    dvt = trk["processedDVT"]
    n = dvt.shape[0] if dvt.ndim else 0
    wanted = {"processedDVT": (n, COLUMNS["processedDVT"]), "HDRadians": (n,),
              "samplesFilled": (n, COLUMNS["samplesFilled"]), "samplesUnfilled": (n, COLUMNS["samplesUnfilled"])}
    mismatched = {name: list(trk[name].shape) for name, shape in wanted.items() if trk[name].shape != shape}
    add_result(results, "tracking_lengths", "fail" if mismatched or n == 0 else "pass",
               {"n_frames": n, "mismatched": mismatched})
    if "processedDVT" not in mismatched:
        bad = np.flatnonzero(_col(dvt, "frame") != np.arange(1, n + 1))
        first = int(bad[0]) + 1 if bad.size else None
        add_result(results, "frames_contiguous", "fail" if bad.size else "pass",
                   {"n_bad": int(bad.size), "first_bad_row": first})
    return record.with_results(results)


def _painted_near(painted, frame, label, tolerance):
    """
    Whether the painted column holds the label at some frame within the tolerance of a 1-based frame.
    """
    return bool((painted[max(frame - 1 - tolerance, 0):frame + tolerance] == label).any())


def _keys_unique(record):
    """
    Duplicate keys per table of rows.
    """
    detail = {}
    for name, table_rows in record.rows.items():
        keys = [tuple(row[column] for column in KEYS[name]) for row in table_rows]
        detail[name] = len(keys) - len(set(keys))
    return any(detail.values()), detail


def _rows_conserved(record):
    """
    The frames table has N rows and the event rows equal spiral_events in order, as the file holds them.
    """
    events = record.ana.get("spiral_events", np.empty((0, COLUMNS["spiral_events"])))
    expected = [(frame, label) for frame, _, label in events]
    got = [(event["frame"], event["label"]) for event in record.rows["events"]]
    detail = {
        "frames_short": len(record.trk["processedDVT"]) - record.facts["frame_rows"],
        "events_short": len(expected) - len(got),
        "events_changed": sum(a != b for a, b in zip(expected, got)),
    }
    return any(detail.values()), detail


def _flags_agree(record):
    """
    The (1, 1) sentinels of each light, the average and the mashup agree with the unfilled flags.
    """
    trk = record.trk
    dvt, filled, unfilled = trk["processedDVT"], trk["samplesFilled"], trk["samplesUnfilled"]
    detail = {}
    for k, light in enumerate(("front", "back")):
        sentinel = (_col(dvt, f"{light}_x") == UNFILLED_XY) & (_col(dvt, f"{light}_y") == UNFILLED_XY)
        detail[f"{light}_unflagged_sentinel"] = _count(sentinel & ~unfilled[:, k])
        detail[f"{light}_flagged_not_sentinel"] = _count(unfilled[:, k] & ~sentinel)
    detail["both_flags"] = _count((filled & unfilled).any(axis=1))
    avg = (_col(dvt, "avg_x") == UNFILLED_XY) & (_col(dvt, "avg_y") == UNFILLED_XY)
    mashup = (_col(dvt, "mashup_x") == UNFILLED_XY) & (_col(dvt, "mashup_y") == UNFILLED_XY)
    detail["avg_mismatch"] = _count(avg != unfilled.any(axis=1))
    detail["mashup_mismatch"] = _count(mashup != unfilled.all(axis=1))
    return any(detail.values()), detail


def _heading_nan_matches(record):
    """
    The stored heading is NaN exactly where either light is unfilled.
    """
    nan, gone = np.isnan(record.trk["HDRadians"]), record.trk["samplesUnfilled"].any(axis=1)
    detail = {"nan_where_tracked": _count(nan & ~gone), "value_where_unfilled": _count(~nan & gone)}
    return any(detail.values()), detail


def _heading_matches_lights(record):
    """
    The stored heading equals the angle from the back light to the front light on rows where both are tracked.
    """
    trk = record.trk
    dvt = trk["processedDVT"]
    angle = np.arctan2(_col(dvt, "front_y") - _col(dvt, "back_y"),
                       _col(dvt, "front_x") - _col(dvt, "back_x"))
    wrapped = np.abs((trk["HDRadians"] - angle + np.pi) % (2 * np.pi) - np.pi)[~trk["samplesUnfilled"].any(axis=1)]
    wrapped = wrapped[~np.isnan(wrapped)]  # a NaN heading is counted by heading_nan_matches
    over = _count(wrapped > HEADING_TOLERANCE_RAD)
    return over > 0, {"over_tolerance": over, "max_rad": float(wrapped.max()) if wrapped.size else 0.0}


def _pauses(record):
    """
    The pauses found in t, each as a frame and the seconds skipped.
    """
    found = [{"frame": frame, "seconds": seconds} for frame, seconds in record.facts["pauses"]]
    return bool(found), {"n": len(found), "pauses": found}


def _stamps_usable(record):
    """
    The timeStamps status from the epoch builder and how many entries the file holds.
    """
    stamps = record.facts["stamps"]
    return stamps != STAMPS_OK, {"status": stamps, "count": len(record.ana.get("timeStamps", ()))}


def _tag_known(record):
    """
    The file's variant tag is in the tag lookup, or there is none.
    """
    tag = record.facts["tag"]
    return (tag.lower() if tag else None) not in TAGS, {"tag": tag}


def _events_paired(record):
    """
    Start and end rows in no pair, counted separately, leaving out the rows at frame 0.
    """
    alone = [event["kind"] for event in record.rows["events"] if event["frame"] != 0 and event["run"] is None]
    detail = {"starts_without_end": alone.count(KIND_START), "ends_without_start": alone.count(KIND_END)}
    return any(detail.values()), detail


def _events_in_tracking(record):
    """
    Event rows at frame 0, and beyond the tracking: below frame 0 or after the last tracking frame.
    """
    n, events = len(record.trk["processedDVT"]), record.rows["events"]
    detail = {
        "at_row_0": sum(event["frame"] == 0 for event in events),
        "beyond": sum(event["frame"] < 0 or event["frame"] > n for event in events),
    }
    return any(detail.values()), detail


def _lab_counts_match(record):
    """
    The lab's nRuns and run markers per path equal the clean pairs, the markers compared sorted.
    """
    ana = record.ana
    clean = {}
    for run in record.rows["runs"]:
        if run["clean"]:
            clean.setdefault(run["path_id"], []).append((run["frame_start"], run["frame_end"]))
    paths = [int(path) for path in ana.get("pathList", [])]
    counts = dict(zip(paths, ana.get("nRuns", [])))
    markers = dict(zip(paths, ana.get("runPosMarkers", [])))
    nruns_differ, markers_differ = [], []
    for path in sorted(set(paths) | set(clean)):
        pairs = sorted(clean.get(path, []))
        starts, ends = markers.get(path, ([], []))
        if int(counts.get(path, 0)) != len(pairs):
            nruns_differ.append(path)
        if sorted(zip(map(int, starts), map(int, ends))) != pairs:
            markers_differ.append(path)
    return bool(nruns_differ or markers_differ), {"nruns_differ": nruns_differ, "markers_differ": markers_differ}


def _painted_aligned(record):
    """
    pixelDvt is aligned with the tracking.
    """
    aligned = record.aligned_pixel() is not None
    return not aligned, {"aligned": aligned}


def _painted_matches_runs(record):
    """
    Each clean run inside the tracking has its start label painted near its first and last frame.
    """
    pixel = record.aligned_pixel()
    if pixel is None:  # painted_label is blank then and painted_aligned has warned
        return False, {"mismatched_runs": []}
    n, painted = len(pixel), pixel[:, -1]
    mismatched = [
        run["run"] for run in record.rows["runs"]
        if run["clean"] and 1 <= run["frame_start"] <= n and 1 <= run["frame_end"] <= n
        and not all(_painted_near(painted, frame, run["path_id"], PAINTED_TOLERANCE_FRAMES)
                    for frame in (run["frame_start"], run["frame_end"]))
    ]
    return bool(mismatched), {"mismatched_runs": mismatched}


def _rate_matches(record):
    """
    The sample rate and the interpolation limit are RATE_HZ and MAX_GAP.
    """
    rate, gap = record.trk["sampleRate"], record.trk["maxGap"]
    # JSON has no NaN
    detail = {"sample_rate": rate if np.isfinite(rate) else None, "max_gap": gap if np.isfinite(gap) else None}
    return rate != RATE_HZ or gap != MAX_GAP, detail


def _events_present(record):
    """
    The analysis file has spiral_events.
    """
    present = "spiral_events" in record.ana
    return not present, {"present": present}


CHECKS = {
    "keys_unique": _keys_unique,
    "rows_conserved": _rows_conserved,
    "flags_agree": _flags_agree,
    "heading_nan_matches": _heading_nan_matches,
    "heading_matches_lights": _heading_matches_lights,
    "pauses": _pauses,
    "stamps_usable": _stamps_usable,
    "tag_known": _tag_known,
    "events_paired": _events_paired,
    "events_in_tracking": _events_in_tracking,
    "lab_counts_match": _lab_counts_match,
    "painted_aligned": _painted_aligned,
    "painted_matches_runs": _painted_matches_runs,
    "rate_matches": _rate_matches,
    "events_present": _events_present,
}


def check_converted(record):
    """
    The record with the checks on its converted rows, each in its own try: a crash is a warn, or a fail for the two.
    """
    results = {}
    for name, check in CHECKS.items():
        try:
            bad, detail = check(record)
            level = "fail" if name in FAILS else "warn"
            add_result(results, name, level if bad else "pass", detail)
        except Exception as error:
            add_result(results, name, "fail" if name in FAILS else "warn",
                       {"error": f"check error: {type(error).__name__}: {error}"})
    return record.with_results(results)
