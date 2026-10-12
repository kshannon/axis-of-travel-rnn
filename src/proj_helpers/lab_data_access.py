"""
Plumbing for lab data EDA notebooks
"""

import re
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import scipy.io as sio
from proj_helpers.paths import local_config


def lab_root():
    """
    The lab data folder from configs/local.yaml (the LAB_DATA key), or stop with a message.
    """
    lab = local_config().get("LAB_DATA")
    if not lab:
        raise SystemExit("LAB_DATA is not set in configs/local.yaml")
    root = Path(lab).expanduser()
    if not root.is_dir():
        raise SystemExit(f"LAB_DATA is not a folder: {root}")
    return root


# ---------- reader ----------
# MATLAB writes two kinds of .mat file. Classic ones scipy reads directly.
# Version 7.3 ones are HDF5: arrays are stored transposed (so we reverse the axes).
# Characters are integer codes, and a cell is a table of references.

H5_CLASSES = {"cell", "char", "logical", "double", "single",
              "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64"}


def squeeze(a):
    """
    Drop length-one axes, and return a Python scalar for a single value, as loadmat(squeeze_me=True) does.
    """
    a = np.squeeze(a)
    return a.item() if a.ndim == 0 else a


def h5_value(f, node):
    """
    One MATLAB v7.3 variable as numpy: arrays transposed back, characters decoded, cells dereferenced.
    """
    cls = node.attrs.get("MATLAB_class", b"").decode()
    if isinstance(node, h5py.Group) or cls not in H5_CLASSES:
        kind = "group" if isinstance(node, h5py.Group) else "dataset"
        raise NotImplementedError(f"{node.name}: {kind} of MATLAB class {cls!r} is not handled")
    if "MATLAB_empty" in node.attrs:
        return "" if cls == "char" else np.array([], dtype=object if cls == "cell" else float)
    data = node[()].T                                   # column-major on disk, so reverse the axes
    if cls == "cell":
        cells = np.empty(data.shape, dtype=object)
        for i in np.ndindex(data.shape):
            cells[i] = h5_value(f, f[data[i]])          # cell contents live under #refs#
        return squeeze(cells)
    if cls == "char":
        rows = ["".join(map(chr, r)) for r in np.atleast_2d(data)]
        return rows[0] if len(rows) == 1 else np.array(rows)
    return squeeze(data)                                # logical stays uint8, as loadmat gives it


def load_mat(path, variables=None):
    """
    The named variables of a MATLAB file (all of them when None), classic or v7.3; absent ones are left out.
    """
    if not h5py.is_hdf5(path):
        return sio.loadmat(path, squeeze_me=True, struct_as_record=False, variable_names=variables)
    with h5py.File(path, "r") as f:
        keep = [k for k in f if not k.startswith("#") and (variables is None or k in variables)]
        return {k: h5_value(f, f[k]) for k in keep}


# ---------- catalog ----------
# File names are the only index the lab left: <subject>_rec<N>_<MMDDYY><sss>[_tags]<kind>.mat

NAME = re.compile(
    r"^(?P<subject>[A-Za-z]+\d+)_rec(?P<rec>\d+)_(?P<stamp>\d{6})(?P<session>\d{3})_?(?P<rest>.+)\.mat$"
)


def catalog(root):
    """
    Sessions by id: group, tracking file, analysis file and the analysis file's name pattern.
    """
    sessions = {}
    for path in sorted(Path(root).rglob("*.mat")):
        m = NAME.match(path.name)
        if m is None:
            continue
        i = m.groupdict()
        date = datetime.strptime(i["stamp"], "%m%d%y").strftime("%Y%m%d")
        entry = sessions.setdefault(f"{i['subject']}_rec{i['rec']}_{date}_{i['session']}", {"group": path.parent.name})
        if i["rest"] == "ProcessedDVT":
            entry["dvt"] = path
        elif "rmaps" in i["rest"].lower().split("_"):
            entry["analysis"], entry["pattern"] = path, i["rest"]
    return sessions


# ---------- selection ----------

def find(sessions, prefix):
    """
    The one session id that starts with e.g. 'NS14_rec15', so the notebooks need not spell the date.
    """
    hits = [sid for sid in sessions if sid.startswith(prefix + "_")]
    if len(hits) != 1:
        raise KeyError(f"{prefix}: {len(hits)} sessions match {hits}")
    return hits[0]


def pick_scope(sessions, run_all, per_group=3):
    """
    All the sessions when run_all, else the first few of each group: a quick look before the slow full pass.
    """
    if run_all:
        return sessions
    taken, scope = {}, {}
    for sid, s in sessions.items():
        if taken.get(s["group"], 0) < per_group:
            taken[s["group"]] = taken.get(s["group"], 0) + 1
            scope[sid] = s
    return scope
