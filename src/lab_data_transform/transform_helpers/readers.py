"""
The lab's sessions found by file name, and their tracking and analysis files in either MATLAB format read into numpy.
"""

import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

import h5py
import numpy as np
import scipy.io as sio

# <subject>_rec<N>_<MMDDYY><sss>[_tags]<kind>.mat, the tags and the kind are split further in parse_name
NAME = re.compile(
    r"^(?P<subject>[A-Za-z]+\d+)_rec(?P<rec>\d+)_(?P<stamp>\d{6})(?P<session>\d{3})(?!\d)_?(?P<rest>.+)\.mat$"
)

# The variables read from each file (tables.md 1.1 and 1.2): a tracking file without a required one fails its
# session, and the provenance variables are only recorded in the manifest.
TRACKING_REQUIRED = ("processedDVT", "HDRadians", "samplesFilled", "samplesUnfilled", "sampleRate", "maxGap")
TRACKING_PROVENANCE = ("dvtFileName", "dvtPathName", "velSmoothWinSecs", "velSmoothWinSamples", "nRealLights")
ANALYSIS_VARIABLES = ("timeStamps", "spiral_events", "pixelDvt", "nRuns", "pathList", "runPosMarkers")
ANALYSIS_PROVENANCE = ("runsFileName", "runsPathName")

# How each named variable is shaped once read: text, a number, a vector, or a matrix with this many columns.
TEXT = ("dvtFileName", "dvtPathName", "runsFileName", "runsPathName")
SCALARS = ("sampleRate", "maxGap", "velSmoothWinSecs", "velSmoothWinSamples", "nRealLights")
VECTORS = ("HDRadians", "timeStamps", "nRuns", "pathList")
FLAGS = ("samplesFilled", "samplesUnfilled")
COLUMNS = {"processedDVT": 10, "pixelDvt": 11, "spiral_events": 3, "samplesFilled": 2, "samplesUnfilled": 2}
# The column of each value in processedDVT.
DVT_COLUMNS = {
    "frame": 0, "t": 1, "front_x": 2, "front_y": 3, "back_x": 4, "back_y": 5, "avg_x": 6, "avg_y": 7, "mashup_x": 8,
    "mashup_y": 9,
}


# Finding: the lab's file names are the only index, so this section lists and parses names and opens no file.

@dataclass(frozen=True)
class Session:
    """
    One recording: its names and dates, the variant tag, and the paths of its two files.
    """

    session_id: str
    subject_id: str
    group: str
    session: str
    rec: int
    date: date
    tag: str | None
    tag_raw: str | None
    dvt_path: Path
    rmaps_path: Path


def parse_name(name):
    """
    The fields of a tracking or analysis file name, or None when it is neither (a second variant tag included).
    """
    m = NAME.match(name)
    if m is None:
        return None
    try:
        day = datetime.strptime(m["stamp"], "%m%d%y").date()
    except ValueError:
        return None
    tokens = m["rest"].split("_")
    if "" in tokens:
        return None
    if m["rest"] == "ProcessedDVT":
        kind, tags = "ProcessedDVT", []
    elif [t.lower() for t in tokens].count("rmaps") == 1:
        kind, tags = "rmaps", [t for t in tokens if t.lower() not in ("rmaps", "tt")]
    else:
        return None
    if len(tags) > 1:
        return None
    tag_raw = tags[0] if tags else None
    return {
        "subject_id": m["subject"],
        "rec": int(m["rec"]),
        "date": day,
        "session": m["session"],
        "kind": kind,
        "tag": tag_raw.lower() if tag_raw else None,
        "tag_raw": tag_raw,
    }


def order_key(session):
    """
    The recording order: subject, then recording number as an integer (rec2 before rec10), date, session.
    """
    return (session.subject_id, session.rec, session.date, session.session)


def catalog(root):
    """
    The sessions under root sorted by order_key, and the skipped files as (name, reason).
    """
    found = {}  # session id -> {kind: [(path, parsed name)]}
    skipped = []
    for path in sorted(Path(root).rglob("*.mat")):
        info = parse_name(path.name)
        if info is None:
            skipped.append((path.name, "does not parse"))
            continue
        sid = f"{info['subject_id']}_rec{info['rec']}_{info['date']:%Y%m%d}_{info['session']}"
        found.setdefault(sid, {"ProcessedDVT": [], "rmaps": []})[info["kind"]].append((path, info))

    sessions = []
    for sid, files in found.items():
        dvt, rmaps = files["ProcessedDVT"], files["rmaps"]
        if len(dvt) == 1 and len(rmaps) == 1:
            (dvt_path, _), (rmaps_path, info) = dvt[0], rmaps[0]
            sessions.append(Session(
                session_id=sid,
                subject_id=info["subject_id"],
                group=dvt_path.parent.name,
                session=info["session"],
                rec=info["rec"],
                date=info["date"],
                tag=info["tag"],
                tag_raw=info["tag_raw"],
                dvt_path=dvt_path,
                rmaps_path=rmaps_path,
            ))
            continue
        reason = "doubled file" if len(dvt) > 1 or len(rmaps) > 1 else "no twin"
        skipped.extend((path.name, reason) for path, _ in dvt + rmaps)
    return sorted(sessions, key=order_key), sorted(skipped)


def select(sessions, only, sample):
    """
    The sessions (in recording order) whose id is PREFIX or continues it after `_`, then the first N per subject.
    """
    chosen = sessions
    if only is not None:
        chosen = [s for s in chosen if s.session_id == only or s.session_id.startswith(only + "_")]
    if sample is not None:
        taken, kept = {}, []
        for s in chosen:
            if taken.get(s.subject_id, 0) < sample:
                taken[s.subject_id] = taken.get(s.subject_id, 0) + 1
                kept.append(s)
        chosen = kept
    return chosen


# Reading: the two files of a session in either MATLAB format, read into numpy values with their shapes normalised.

def _squeeze(a):
    """
    Drop length-one axes and return a Python scalar for a single value, as loadmat(squeeze_me=True) does.
    """
    a = np.squeeze(a)
    return a.item() if a.ndim == 0 else a


def _h5_value(f, node):
    """
    One variable of a v7.3 file as numpy: arrays transposed back, characters decoded, cells dereferenced.
    """
    cls = node.attrs.get("MATLAB_class", b"").decode()
    if "MATLAB_empty" in node.attrs:
        return "" if cls == "char" else np.array([], dtype=object if cls == "cell" else float)
    data = node[()].T  # column-major on disk, so reverse the axes
    if cls == "cell":
        cells = np.empty(data.shape, dtype=object)
        for i in np.ndindex(data.shape):
            cells[i] = _h5_value(f, f[data[i]])  # the contents live under #refs#
        return _squeeze(cells)
    if cls == "char":
        rows = ["".join(map(chr, r)) for r in np.atleast_2d(data)]
        return rows[0] if len(rows) == 1 else np.array(rows)
    return _squeeze(data)


def load_mat(path, variables):
    """
    The named variables of a MATLAB file in either format, as loaded, leaving out absent names and the file header.
    """
    if h5py.is_hdf5(path):
        with h5py.File(path, "r") as f:
            raw = {name: _h5_value(f, f[name]) for name in variables if name in f}
    else:
        raw = sio.loadmat(path, squeeze_me=True, struct_as_record=False, variable_names=list(variables))
    return {name: ("" if isinstance(value, np.ndarray) and value.dtype.kind == "U" and value.size == 0 else value)
            for name, value in raw.items() if not name.startswith("__")}


def _shaped(name, value):
    """
    One loaded value in the shape and type tables.md gives it, undoing what the raw read squeezed away.
    """
    if name in TEXT:
        return str(value)
    if name in SCALARS:
        return float(value) if np.size(value) else None
    if name == "runPosMarkers":
        cells = np.asarray(value, dtype=object).reshape(-1, 2)
        return [tuple(np.atleast_1d(np.array(x, dtype=float)) for x in pair) for pair in cells]
    array = np.array(value) != 0 if name in FLAGS else np.array(value, dtype=float)
    if name in VECTORS:
        return np.atleast_1d(array)
    if array.size == 0 or (array.ndim < 2 and array.size == COLUMNS[name]):
        return array.reshape(-1, COLUMNS[name])
    return array


def _read(path, names):
    """
    The named variables of one file with their shapes normalised, absent names left out.
    """
    return {name: _shaped(name, value) for name, value in load_mat(path, names).items()}


def read(record):
    """
    The record with its session's tracking and analysis files read.
    """
    trk = _read(record.session.dvt_path, TRACKING_REQUIRED + TRACKING_PROVENANCE)
    ana = _read(record.session.rmaps_path, ANALYSIS_VARIABLES + ANALYSIS_PROVENANCE)
    return replace(record, trk=trk, ana=ana)
