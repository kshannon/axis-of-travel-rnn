"""
The pilot's dataset: shifted clean targets, input columns, splits, windows, noise, the leakage assert, world batches.
"""

from dataclasses import replace

import numpy as np
import pytest
import torch

from pilot.config import SMOKE
from pilot.dataset import (
    INPUT_SETS, EqualWorldBatches, PilotDataset, assert_no_leakage, fit_scaler, make_feature_layout, select_sessions,
    session_features,
)
from pilot.worlds import WORLDS, load_sessions, make_layouts

CFG = SMOKE
CLEAN = {**SMOKE, "input_noise_sd": 0.0}
WINDOW = SMOKE["window"]
SESSIONS = load_sessions(SMOKE, make_layouts(SMOKE))  # the cached SMOKE sessions
TRAIN = select_sessions(SESSIONS, SMOKE, "train", WORLDS)
SCALER = fit_scaler(TRAIN)


def make_dataset(input_set, cfg=CFG, sessions=TRAIN, horizon=SMOKE["horizon"], seed=0):
    return PilotDataset(sessions, make_feature_layout(input_set, cfg), cfg, horizon, SCALER, seed)


@pytest.mark.parametrize("horizon", [1, 10, 20])
def test_target_is_the_clean_place_vector_shifted_by_the_horizon(horizon):
    noisy, clean = make_dataset("place_only", horizon=horizon), make_dataset("place_only", CLEAN, horizon=horizon)
    for i in (0, len(noisy) // 2, len(noisy) - 1):
        item = noisy[i]
        place = TRAIN[item["session"]].place
        assert np.array_equal(item["y"].numpy(), place[item["start"] + horizon:item["start"] + horizon + WINDOW])
    item = clean[3]  # without noise the input at step t + horizon is the target at step t
    assert np.array_equal(item["y"][:-horizon].numpy(), item["x"][horizon:].numpy())
    weight = item["loss_weight"].numpy()
    assert (weight[:CFG["no_loss_steps"]] == 0).all() and (weight[CFG["no_loss_steps"]:] == 1).all()


def test_each_input_set_has_the_right_columns_in_the_right_order():
    n_pc, n_hd = CFG["place_n"], CFG["hd_n"]
    assert make_feature_layout("place_only", CFG).columns == {"place": slice(0, n_pc)}
    assert make_feature_layout("full", CFG).columns == {"place": slice(0, n_pc), "hd": slice(n_pc, n_pc + n_hd),
                                                        "turn_rate": slice(n_pc + n_hd, n_pc + n_hd + 1),
                                                        "speed": slice(n_pc + n_hd + 1, n_pc + n_hd + 2)}
    for input_set, blocks in INPUT_SETS.items():
        layout = make_feature_layout(input_set, CFG)
        assert tuple(layout.columns) == blocks and layout.n_out == n_pc
        item = make_dataset(input_set, CLEAN)[2]
        session, start = TRAIN[item["session"]], item["start"]
        rows = slice(start, start + WINDOW)
        x = item["x"].numpy()
        assert x.shape == (WINDOW, layout.n_in)
        assert np.array_equal(x[:, layout.columns["place"]], session.place[rows])
        if "hd" in blocks:
            assert np.array_equal(x[:, layout.columns["hd"]], session.hd[rows])
        if "turn_rate" in blocks:
            turn = np.clip(session.turn_rate[rows], SCALER["turn_rate_low"], SCALER["turn_rate_high"])
            turn_z = (turn - SCALER["turn_rate_mean"]) / SCALER["turn_rate_sd"]
            speed_z = (session.speed[rows] - SCALER["speed_mean"]) / SCALER["speed_sd"]
            assert np.allclose(x[:, layout.columns["turn_rate"]][:, 0], turn_z)
            assert np.allclose(x[:, layout.columns["speed"]][:, 0], speed_z)
    assert make_feature_layout("place_only", CFG).n_in == n_pc  # nothing but place cells
    layout = make_feature_layout("full", CFG)
    train_x = np.concatenate([session_features(s, layout, SCALER) for s in TRAIN])
    for name in ("turn_rate", "speed"):  # z-scored on the training sessions
        column = train_x[:, layout.columns[name]]
        assert abs(column.mean()) < 1e-4 and abs(column.std() - 1) < 1e-4
    top = (SCALER["turn_rate_high"] - SCALER["turn_rate_mean"]) / SCALER["turn_rate_sd"]
    assert train_x[:, layout.columns["turn_rate"]].max() <= top + 1e-4  # the spikes are clipped


def test_no_session_is_in_two_splits():
    splits = {split: select_sessions(SESSIONS, CFG, split, WORLDS) for split in ("train", "val", "test")}
    keys = [{(s.world, s.seed) for s in group} for group in splits.values()]
    n_sessions = sum(len(v) for v in SESSIONS.values())
    assert sum(len(group) for group in splits.values()) == n_sessions  # every session is in a split
    assert len(set.union(*keys)) == n_sessions  # and in only one
    assert {s.world for s in select_sessions(SESSIONS, CFG, "test", ("loop",))} == {"loop"}


@pytest.mark.parametrize("horizon", [1, 10, 20])
def test_windows_stay_inside_their_session(horizon):
    dataset = make_dataset("full", CLEAN, horizon=horizon)
    for k, session in enumerate(TRAIN):
        starts = [start for j, start in dataset.windows if j == k]
        last = starts[-1]
        assert starts[0] == 0 and last + WINDOW + horizon <= len(session.t) < last + CFG["stride"] + WINDOW + horizon
    for i in range(len(dataset)):  # slicing past the end of a session would silently give a short window
        item = dataset[i]
        assert item["x"].shape == (WINDOW, dataset.layout.n_in) and item["y"].shape == (WINDOW, CFG["place_n"])


def test_noise_is_deterministic_per_item_and_absent_from_targets():
    noisy, again, other, clean = (make_dataset("full"), make_dataset("full"), make_dataset("full", seed=1),
                                  make_dataset("full", CLEAN))
    i, columns = 5, noisy.layout.columns
    assert torch.equal(noisy[i]["x"], noisy[i]["x"]) and torch.equal(noisy[i]["x"], again[i]["x"])
    assert not torch.equal(noisy[i]["x"], other[i]["x"])
    assert torch.equal(noisy[i]["y"], clean[i]["y"])
    noise = (noisy[i]["x"] - clean[i]["x"]).numpy()
    for name in ("place", "hd"):
        assert abs(noise[:, columns[name]].mean()) < 0.01
        assert abs(noise[:, columns[name]].std() - CFG["input_noise_sd"]) < 0.01
    for name in ("turn_rate", "speed"):
        assert (noise[:, columns[name]] == 0).all()
    assert torch.equal(make_dataset("place_only")[i]["x"], noisy[i]["x"][:, columns["place"]])  # same noise, any set


def test_leakage_assert_fires_on_an_injected_folded_heading_column():
    session = TRAIN[0]
    folded = {"heading mod pi": np.mod(session.heading, np.pi), "cos 2h": np.cos(2 * session.heading),
              "sin 2h": np.sin(2 * session.heading)}
    for name, signal in folded.items():
        place = session.place.copy()
        place[:, 7] = 0.3 * signal + 0.2  # a place cell column that is really the folded heading
        with pytest.raises(AssertionError, match="folded heading"):
            make_dataset("place_only", sessions=[replace(session, place=place)])
    layout = make_feature_layout("place_only", CFG)
    x = session_features(session, layout, SCALER)
    assert_no_leakage(x, session.heading, layout, CFG)
    with pytest.raises(AssertionError):  # a column the input set does not imply
        assert_no_leakage(np.column_stack([x, folded["cos 2h"]]), session.heading, layout, CFG)
    for input_set in INPUT_SETS:  # the real sessions are clean
        make_dataset(input_set)


def test_equal_world_batches_mix_the_worlds():
    dataset = make_dataset("place_only")
    sampler = EqualWorldBatches(dataset, batch_size=8, seed=0)
    batches = list(torch.utils.data.DataLoader(dataset, batch_sampler=sampler))
    assert len(batches) == len(sampler) > 0
    for batch in batches:
        assert sorted(batch["world"]) == ["loop"] * 4 + ["open_field"] * 4
    first, second = list(sampler), list(sampler)
    assert first != second  # reshuffled each pass
    assert len({i for batch in first for i in batch}) == sum(len(batch) for batch in first)  # without replacement
    assert list(EqualWorldBatches(dataset, batch_size=8, seed=0)) == list(EqualWorldBatches(dataset, 8, 0))
    one_world = make_dataset("place_only", sessions=select_sessions(SESSIONS, CFG, "train", ("loop",)))
    assert all(len(batch) == 8 for batch in EqualWorldBatches(one_world, batch_size=8, seed=0))
