"""
Reading a built folder for training: the split keeps sessions whole and is deterministic, resampling keeps the time axis, the guard refuses the data.
"""

import json

import numpy as np
import pytest

from axis_of_travel_rnn import data
from proj_helpers.paths import repo_root

from .handmade import LAB_RATE_HZ, TRAINING_RATE_HZ, wandering

# Ten sessions over six dates, two blocks each, so a date can hold more than one session and a session more than one block.
ROWS = [{"block_id": f"S{s}_{b}", "session_id": f"S{s}", "date": f"2026-01-0{1 + s % 6}"} for s in range(10) for b in (1, 2)]
FRACTIONS = (0.6, 0.2, 0.2)


def test_the_split_is_deterministic_and_keeps_sessions_and_dates_whole():
    split = data.split_by_date(ROWS, FRACTIONS, seed=3)
    assert split == data.split_by_date(ROWS, FRACTIONS, seed=3)
    assert set(split) == {row["session_id"] for row in ROWS}
    by_date = {}
    for row in ROWS:
        by_date.setdefault(row["date"], set()).add(split[row["session_id"]])
    assert all(len(splits) == 1 for splits in by_date.values())  # every session of a date in one split
    assert sorted(set(split.values())) == sorted(data.SPLITS)
    with pytest.raises(data.LabDataError):
        data.split_by_date(ROWS[:2], FRACTIONS, seed=3)  # one date cannot fill three splits


def test_resampling_takes_every_third_frame_and_keeps_the_time_axis():
    block = wandering(601, seed=0)
    resampled = data.resample(block, TRAINING_RATE_HZ)
    assert np.allclose(resampled["arrays"]["t"], np.arange(201) / TRAINING_RATE_HZ)
    assert np.array_equal(resampled["arrays"]["x"], block["arrays"]["x"][::3])
    assert all(len(values) == 201 for values in resampled["arrays"].values())
    assert resampled["row"]["rate_hz"] == TRAINING_RATE_HZ and resampled["row"]["n_frames"] == 201
    assert block["row"]["rate_hz"] == LAB_RATE_HZ  # the block read is left as it was
    with pytest.raises(data.LabDataError):
        data.resample(block, 25)


def test_the_guard_refuses_a_data_root_and_the_repository(tmp_path):
    config = {"PROCESSED_LAB_DATA": str(tmp_path / "processed"), "LAB_DATA": str(tmp_path / "lab")}
    assert data.guard(tmp_path / "runs", config) == tmp_path / "runs"
    for path in (tmp_path / "processed" / "blocks_v1" / "runs", tmp_path, repo_root() / "runs"):
        with pytest.raises(data.LabDataError):
            data.guard(path, config)


def test_a_built_folder_is_found_by_name_with_its_data_id(tmp_path):
    config = {"PROCESSED_LAB_DATA": str(tmp_path)}
    with pytest.raises(data.LabDataError):
        data.built_folder("blocks_v1", config)
    (tmp_path / "blocks_v1").mkdir()
    (tmp_path / "blocks_v1" / data.MANIFEST).write_text(json.dumps({"data_id": "abc"}))
    folder = data.built_folder("blocks_v1", config)
    assert folder == tmp_path / "blocks_v1" and data.data_id(folder) == "abc"
