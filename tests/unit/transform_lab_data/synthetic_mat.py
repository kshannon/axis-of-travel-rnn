"""
One small synthetic session as a dict of the lab's variables, written as a classic or v7.3 MATLAB file pair.
"""

from pathlib import Path

import h5py
import numpy as np
import scipy.io as sio

from transform_lab_data.transform_helpers.readers import TRACKING_PROVENANCE, TRACKING_REQUIRED


def session_names(subject, rec, mmddyy, session, tag=None, tag_first=False):
    """
    The tracking and analysis file names of one session, the variant tag after rmaps or, with tag_first, before it.
    """
    base = f"{subject}_rec{rec}_{mmddyy}{session}"
    if tag is None:
        rmaps = f"{base}_tt_rmaps.mat"
    elif tag_first:
        rmaps = f"{base}_tt_{tag}_rmaps.mat"
    else:
        rmaps = f"{base}_tt_rmaps_{tag}.mat"
    return f"{base}ProcessedDVT.mat", rmaps


def example_session(tag=None):
    """
    The lab's variables for one 900-frame session with three pauses, unfilled lights and three runs.
    """
    n = 900
    rng = np.random.default_rng(20261010)
    frame = np.arange(1, n + 1, dtype=float)

    # time: 1/60 s per frame, plus three pauses
    paused = np.zeros(n)
    paused[frame >= 300] = 120.0
    paused[frame >= 450] = 150.0
    paused[frame >= 600] = 157.5
    t = frame / 60 + paused

    # two lights on a random walk, whole pixels well inside 640 by 480
    heading = np.cumsum(rng.normal(0, 0.05, n))
    centre_x = np.clip(320 + np.cumsum(rng.normal(0, 2, n)), 60, 580)
    centre_y = np.clip(240 + np.cumsum(rng.normal(0, 2, n)), 60, 420)
    front_x = np.round(centre_x + 10 * np.cos(heading))
    front_y = np.round(centre_y + 10 * np.sin(heading))
    back_x = np.round(centre_x - 10 * np.cos(heading))
    back_y = np.round(centre_y - 10 * np.sin(heading))

    # flags per light, column 0 the front light (LED1), column 1 the back light (LED2)
    filled = np.zeros((n, 2), dtype=np.uint8)
    unfilled = np.zeros((n, 2), dtype=np.uint8)
    filled[99:104, 0] = 1                       # frames 100 to 104
    unfilled[49:59, 0] = 1                      # frames 50 to 59
    unfilled[54:69, 1] = 1                      # frames 55 to 69, both lights in 55 to 59
    front_gone = unfilled[:, 0] == 1
    back_gone = unfilled[:, 1] == 1

    heading_rad = np.arctan2(front_y - back_y, front_x - back_x)
    heading_rad[front_gone | back_gone] = np.nan

    avg_x = np.round((front_x + back_x) / 2)
    avg_y = np.round((front_y + back_y) / 2)
    mashup_x = np.where(front_gone, back_x, np.where(back_gone, front_x, avg_x))
    mashup_y = np.where(front_gone, back_y, np.where(back_gone, front_y, avg_y))

    # the lab's sentinel (1, 1) where a light, the average or the mashup has nothing
    front_x[front_gone] = front_y[front_gone] = 1
    back_x[back_gone] = back_y[back_gone] = 1
    avg_x[front_gone | back_gone] = avg_y[front_gone | back_gone] = 1
    mashup_x[front_gone & back_gone] = mashup_y[front_gone & back_gone] = 1

    dvt = np.column_stack([frame, t, front_x, front_y, back_x, back_y, avg_x, avg_y, mashup_x, mashup_y])

    # (frame, label) in click order, and the runs they make as (start, end, signed start label)
    clicks = [
        (200, 1), (215, 0), (230, 101),         # a clean run on path 1 with an indecision inside
        (240, -3), (250, 777), (265, -103),     # a dirty run on path 3 with a reward inside
        (440, 2), (470, 102),                   # a clean run on path 2 across the second pause
    ]
    events = np.array([[row, t[row - 1], label] for row, label in clicks], dtype=float)
    pairs = [(200, 230, 1), (240, 265, -3), (440, 470, 2)]
    path_list = [1, 2]
    markers = [[np.array([s for s, _, label in pairs if label == path], dtype=float),
                np.array([e for _, e, label in pairs if label == path], dtype=float)] for path in path_list]

    painted = np.full(n, 99.0)
    for start, end, label in pairs:
        painted[start - 1:end] = label

    return {
        "processedDVT": dvt,
        "HDRadians": heading_rad,
        "samplesFilled": filled,
        "samplesUnfilled": unfilled,
        "sampleRate": 60.0,
        "maxGap": 30.0,
        "dvtFileName": "synthetic001.dvt",
        "dvtPathName": "C:/synthetic/",
        "velSmoothWinSecs": 0.1,
        "velSmoothWinSamples": 6.0,
        "nRealLights": 2.0,
        "timeStamps": np.array([21, 150, 161, 700] if tag is None else [21, 150, 161, 700, 711, 880], dtype=float),
        "spiral_events": events,
        "pixelDvt": np.column_stack([dvt, painted]),
        "nRuns": np.array([len(m[0]) for m in markers], dtype=float),
        "pathList": np.array(path_list, dtype=float),
        "runPosMarkers": markers,
        "runsFileName": "synthetic001_runs.mat",
        "runsPathName": "C:/synthetic/",
    }


def _h5_write(f, group, name, value):
    """
    One variable as MATLAB v7.3 writes it: transposed, cells into #refs#, an empty as its dims marked MATLAB_empty.
    """
    if isinstance(value, list):
        refs = np.empty((len(value), len(value[0])), dtype=h5py.ref_dtype)
        for i, row in enumerate(value):
            for j, item in enumerate(row):
                refs[i, j] = _h5_write(f, f.require_group("#refs#"), f"{name}_{i}_{j}", item).ref
        data, cls = refs, "cell"
    elif isinstance(value, str):
        data, cls = np.array([[ord(c) for c in value]], dtype=np.uint16), "char"
    elif np.size(value) == 0:
        data, cls = np.zeros(2, dtype=np.uint64), "double"
    elif np.asarray(value).dtype == np.uint8:
        data, cls = np.atleast_2d(value), "logical"
    else:
        data, cls = np.atleast_2d(np.asarray(value, dtype=float)), "double"
    dataset = group.create_dataset(name, data=data.T)
    dataset.attrs["MATLAB_class"] = np.bytes_(cls)
    if cls != "cell" and np.size(value) == 0:
        dataset.attrs["MATLAB_empty"] = np.uint8(1)
    return dataset


def write_session(folder, variables, names, fmt):
    """
    Write the tracking variables to names[0] and the rest to names[1] in folder, fmt "classic" or "v7.3".
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tracking = set(TRACKING_REQUIRED) | set(TRACKING_PROVENANCE)
    parts = [{k: v for k, v in variables.items() if k in tracking},
             {k: v for k, v in variables.items() if k not in tracking}]
    for name, part in zip(names, parts):
        if fmt == "v7.3":
            with h5py.File(folder / name, "w") as f:
                for key, value in part.items():
                    _h5_write(f, f, key, value)
            continue
        out = {}
        for key, value in part.items():
            if isinstance(value, list):
                cell = np.empty((len(value), len(value[0])), dtype=object)
                for i, row in enumerate(value):
                    for j, item in enumerate(row):
                        cell[i, j] = item
                value = cell
            elif isinstance(value, np.ndarray) and value.dtype == np.uint8:
                value = value.astype(bool)
            out[key] = value
        sio.savemat(folder / name, out, oned_as="row")
