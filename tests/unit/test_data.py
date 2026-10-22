"""
Reading a built folder for training: the split keeps sessions whole and is deterministic, and the guard refuses the data.
"""

import numpy as np
import pytest

from axis_of_travel_rnn import data
from axis_of_travel_rnn.config import REPO_ROOT

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


def test_the_guard_refuses_a_data_root_and_the_repository(tmp_path):
    config = {"PROCESSED_LAB_DATA": str(tmp_path / "processed"), "LAB_DATA": str(tmp_path / "lab")}
    assert data.guard(tmp_path / "runs", config) == tmp_path / "runs"
    for path in (tmp_path / "processed" / "blocks_v1" / "runs", tmp_path, REPO_ROOT / "runs"):
        with pytest.raises(data.LabDataError):
            data.guard(path, config)

