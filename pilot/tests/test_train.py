"""
The pilot's training: the masked loss, the persistence baseline, run folders and their seeds, caching, interrupted and
failed runs, the sweep, and the untrained network's closed-form readout.
"""

import re

import numpy as np
import pytest
import torch

from pilot import train
from pilot.analysis import load_thresholds
from pilot.config import SMOKE
from pilot.dataset import PilotDataset, fit_scaler, make_feature_layout, select_sessions
from pilot.worlds import WORLDS, load_sessions, make_layouts

CFG = SMOKE
SESSIONS = load_sessions(CFG, make_layouts(CFG))  # the cached SMOKE sessions
THR = load_thresholds()
TRAINED = train.ArmSpec("place_only", WORLDS, "trained")
TRAINED_OPEN = train.ArmSpec("place_only", ("open_field",), "trained")
UNTRAINED = train.ArmSpec("place_only", WORLDS, "untrained")
SPLIT_INDEX = {"train": (0, 1), "val": (2,), "test": (3,)}  # SMOKE: 2 train, 1 val, 1 test session per world


@pytest.fixture(autouse=True)
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(train, "RUNS_DIR", tmp_path)  # runs never go into datasets/pilot
    return tmp_path


def stop(epoch, model, history):
    raise KeyboardInterrupt


def fail(epoch, model, history):
    raise RuntimeError("boom")


def never(epoch, model, history):
    raise AssertionError("trained again")


def test_loss_ignores_the_steps_without_weight():
    batch = {"y": torch.zeros(2, 5, 3), "loss_weight": torch.tensor([[0.0, 0.0, 1.0, 1.0, 1.0]] * 2)}
    prediction = torch.cat([torch.full((2, 2, 3), 100.0), torch.full((2, 3, 3), 0.5)], dim=1)
    sse, weight = train.window_sse(prediction, batch)
    assert torch.allclose(sse / weight, torch.full((2,), 0.25)) and (weight == 3).all()


def test_persistence_loss_matches_a_direct_calculation():
    persistence = train.persistence_losses(CFG, SESSIONS)
    horizon, window, skip = CFG["horizon"], CFG["window"], CFG["no_loss_steps"]
    errors = [((s.place[a:a + window] - s.place[a + horizon:a + window + horizon]) ** 2).mean(1)[skip:]
              for s in select_sessions(SESSIONS, CFG, "test", WORLDS)
              for a in range(0, len(s.t) - window - horizon + 1, CFG["stride"])]
    assert persistence["clean"][str(horizon)]["all"] == pytest.approx(np.concatenate(errors).mean(), rel=1e-3)
    assert persistence["noisy"][str(horizon)]["all"] > persistence["clean"][str(horizon)]["all"]


def test_trained_run_writes_its_folder_is_cached_and_follows_its_seed(runs_dir, monkeypatch):
    path = train.run_arm(TRAINED, 0, CFG, SESSIONS)
    assert sorted(p.name for p in path.iterdir()) == ["manifest.json", "metrics.json", "weights.pt"]
    manifest, metrics = train.load_run(path).values()
    assert manifest["status"] == "complete" and manifest["seed"] == 0 and manifest["cfg"]["name"] == "smoke"
    assert {"commit", "dirty", "lockfile_sha256", "torch"} <= set(manifest["environment"])
    assert metrics["epochs"] == len(metrics["train_loss"]) == CFG["max_epochs"]
    assert set(metrics["test_loss"]) == {str(h) for h in CFG["horizons"]} and "position" in metrics["decoder"]
    with monkeypatch.context() as m:
        m.setattr(train.Trainer, "fit", never)
        assert train.run_arm(TRAINED, 0, CFG, SESSIONS) == path  # a complete run is not trained again
    weights = train.load_model(path, CFG).state_dict()
    monkeypatch.setattr(train, "RUNS_DIR", runs_dir / "again")
    same = train.load_model(train.run_arm(TRAINED, 0, CFG, SESSIONS), CFG).state_dict()
    other = train.load_model(train.run_arm(TRAINED, 1, CFG, SESSIONS), CFG).state_dict()
    assert all(torch.equal(weights[key], same[key]) for key in weights)  # the same seed gives the same network
    assert not all(torch.equal(weights[key], other[key]) for key in weights)


def test_interrupted_and_failed_runs_are_kept_and_never_cached():
    path = train.run_arm(TRAINED, 0, CFG, SESSIONS, on_epoch=stop)
    metrics = train.load_run(path)["metrics"]
    assert train.status_of(path) == "interrupted" and metrics["epochs"] == 1 and "test_loss" not in metrics
    assert (path / "weights.pt").exists()
    with pytest.raises(RuntimeError):
        train.run_arm(TRAINED, 0, CFG, SESSIONS, on_epoch=fail)
    assert train.status_of(path) == "failed" and "boom" in train.load_run(path)["metrics"]["error"]
    assert train.status_of(train.run_arm(TRAINED, 0, CFG, SESSIONS)) == "complete"
    names = sorted(p.name for p in path.parent.iterdir())
    assert len(names) == 3 and any(".interrupted-" in n for n in names) and any(".failed-" in n for n in names)


def test_sweep_stops_at_an_interrupt_and_resumes_without_repeating_runs():
    assert train.run_sweep(CFG, SESSIONS, ("place_only",), on_epoch=stop) == {}
    assert len(list(train.RUNS_DIR.glob("*/*"))) == 1  # it stopped at the first run
    results = train.run_sweep(CFG, SESSIONS, ("place_only",))
    assert len(results) == len(train.sweep_jobs(CFG, ("place_only",))) == 4
    assert {arm.kind for arm, _ in results} == {"trained", "untrained", "memoryless"}
    assert train.run_sweep(CFG, SESSIONS, ("place_only",), on_epoch=never).keys() == results.keys()


def test_untrained_net_keeps_its_random_weights_and_gets_a_least_squares_readout():
    path = train.run_arm(UNTRAINED, 3, CFG, SESSIONS)
    model, fresh = train.load_model(path, CFG), train.make_model(UNTRAINED, CFG, 3)
    assert all(torch.equal(a, b) for a, b in zip(model.rnn.parameters(), fresh.rnn.parameters()))
    assert not torch.equal(model.readout.weight, fresh.readout.weight)
    assert train.load_run(path)["metrics"]["epochs"] == 0
    layout = make_feature_layout("place_only", CFG)
    sessions = select_sessions(SESSIONS, CFG, "train", WORLDS)
    data = PilotDataset(sessions, layout, CFG, CFG["horizon"], fit_scaler(sessions), train.EPOCH_STRIDE * 3)

    def loss(net):
        return train.mean_losses(train.window_errors(data, lambda batch: train.predict(net, batch["x"])))["all"]

    nudged = train.load_model(path, CFG)
    nudge = 0.01 * torch.randn(nudged.readout.weight.shape, generator=torch.Generator().manual_seed(0))
    with torch.no_grad():
        nudged.readout.weight += nudge
    assert loss(model) < loss(nudged)  # the fitted readout is the minimum, so any nudge makes the training loss worse


def sessions_in(split, worlds):
    return [s for world in worlds for i, s in enumerate(SESSIONS[world]) if i in SPLIT_INDEX[split]]


def test_each_part_of_a_run_uses_the_sessions_of_its_job(monkeypatch):
    """
    Open-field-only arm: scaler, training and early stopping on its diet, decoders fitted on val and scored on test.
    """
    seen = {}
    fit_scaler_, fit, decode_position = train.fit_scaler, train.Trainer.fit, train.decode_position

    def scaler_spy(sessions):
        seen["scaler"] = [s.seed for s in sessions]
        return fit_scaler_(sessions)

    def fit_spy(self, train_ds, val_ds, on_epoch=None):
        seen["train"], seen["val"] = ([s.seed for s in ds.sessions] for ds in (train_ds, val_ds))
        return fit(self, train_ds, val_ds, on_epoch)

    def decoder_spy(h_fit, pos_fit, h_test, pos_test):
        seen.setdefault("decoder", (pos_fit, pos_test))  # the first call pools all the sessions
        return decode_position(h_fit, pos_fit, h_test, pos_test)

    monkeypatch.setattr(train, "fit_scaler", scaler_spy)
    monkeypatch.setattr(train.Trainer, "fit", fit_spy)
    monkeypatch.setattr(train, "decode_position", decoder_spy)
    path = train.run_arm(TRAINED_OPEN, 0, CFG, SESSIONS)
    seeds = lambda split, worlds: [s.seed for s in sessions_in(split, worlds)]
    assert seen["scaler"] == seen["train"] == seeds("train", ("open_field",))
    assert seen["val"] == seeds("val", ("open_field",))
    positions = lambda split: np.concatenate([s.pos for s in sessions_in(split, WORLDS)])
    pos_fit, pos_test = seen["decoder"]
    assert np.array_equal(pos_fit, positions("val")) and np.array_equal(pos_test, positions("test"))
    used = train.load_run(path)["manifest"]["dataset"]
    assert {job: used[job] for job in ("train", "val", "decoder_fit", "test")} == {
        "train": seeds("train", ("open_field",)), "val": seeds("val", ("open_field",)),
        "decoder_fit": seeds("val", WORLDS), "test": seeds("test", WORLDS)}


def test_seeds_give_different_random_networks_and_one_seed_gives_one_network():
    a, b, c = (train.make_model(UNTRAINED, CFG, seed).rnn for seed in (0, 1, 0))
    assert not torch.equal(a.weight_ih_l0, b.weight_ih_l0) and not torch.equal(a.weight_hh_l0, b.weight_hh_l0)
    assert torch.equal(a.weight_hh_l0, c.weight_hh_l0)


def test_test_loss_is_scored_at_each_horizon():
    cfg = {**CFG, "horizons": (1, 10)}
    layout = make_feature_layout("place_only", cfg)
    scaler = fit_scaler(select_sessions(SESSIONS, cfg, "train", WORLDS))
    test = select_sessions(SESSIONS, cfg, "test", WORLDS)
    losses = train.losses_on_test(torch.nn.Identity(), layout, scaler, cfg, test)  # predicts its noisy input
    noisy = train.persistence_losses(cfg, SESSIONS)["noisy"]
    assert all(losses[h]["all"] == pytest.approx(noisy[h]["all"], rel=1e-4) for h in ("1", "10"))
    assert losses["1"]["all"] < losses["10"]["all"]


CFG3 = {**CFG, "trained_seeds": (0, 1, 2)}
PERSISTENCE = {"clean": {"1": {"all": 0.0001}, "10": {"all": 0.01}},
               "noisy": {"1": {"all": 0.0046}, "10": {"all": 0.02}}}
TRAINED_ARM, MEMORYLESS_ARM = train.arms_for("place_only")[:2]
BEATS_PERSISTENCE = "place_only: trained beats persistence at horizon 10"
BEATS_MEMORYLESS = "place_only: trained beats memoryless at horizon 10"
DECODABLE = "place_only: position decodable from hidden state"


def fake_results(trained=(0.005, 0.006, 0.0055), memoryless=0.01, r2=(0.9, 0.8, 0.7)):
    """
    Results of the place_only trained and memoryless arms: test loss at horizon 10 per seed and position R2 per seed.
    """
    results = {(TRAINED_ARM, seed): {"metrics": {"test_loss": {"10": {"all": loss}},
                                                 "decoder": {"position": {"all": r}}}}
               for seed, (loss, r) in enumerate(zip(trained, r2))}
    results[(MEMORYLESS_ARM, 0)] = {"metrics": {"test_loss": {"10": {"all": memoryless}}}}
    return results


def failed_checks(results):
    checks = train.section_2_checks(CFG3, results, PERSISTENCE, ("place_only",), THR)
    return [name for name, passed, _ in checks if not passed]


def test_section_2_checks_fail_on_the_worst_seed_the_weakest_decoder_and_missing_runs():
    assert failed_checks(fake_results()) == []
    # one seed over 0.8 x persistence (0.008); the mean (0.0065) is under it
    assert failed_checks(fake_results(trained=(0.005, 0.0085, 0.006))) == [BEATS_PERSISTENCE]
    # worst seed 0.0075 is over 0.9 x memoryless (0.0072); the mean (0.0062) is under it
    assert failed_checks(fake_results(trained=(0.005, 0.0075, 0.006), memoryless=0.008)) == [BEATS_MEMORYLESS]
    assert failed_checks(fake_results(r2=(0.9, 0.4, 0.8))) == [DECODABLE]
    results = fake_results()
    del results[(TRAINED_ARM, 2)]
    assert failed_checks(results) == ["place_only: trained runs"]
    results = fake_results()
    del results[(MEMORYLESS_ARM, 0)]
    assert failed_checks(results) == [BEATS_MEMORYLESS]


def cells(line):
    return re.split(r" {2,}", line.strip())


def test_tables_put_each_number_under_its_arm_horizon_and_world():
    cfg = {**CFG3, "horizons": (1, 10)}
    arms = train.arms_for("place_only")  # trained both, memoryless, untrained, trained open field
    scale = {"1": 0.1, "10": 1.0}
    seed_losses = {0: (0.010, 0.012, 0.014), 1: (0.02,), 2: (0.03,), 3: (0.04, 0.04, 0.04)}
    results = {}
    for k, arm in enumerate(arms):
        for seed, loss in enumerate(seed_losses[k]):
            decoder = {t: {g: 0.1 * (k + 1) + 0.01 * (3 * i + j) for j, g in enumerate(("all", *WORLDS))}
                       for i, t in enumerate(("position", "heading"))}
            results[(arm, seed)] = {"metrics": {"test_loss": {h: {"all": loss * f} for h, f in scale.items()},
                                                "decoder": decoder}}
    header, h1, h10 = (cells(line) for line in train.loss_table(cfg, results, PERSISTENCE, ("place_only",)))
    assert header[2:] == ["persistence", "persistence (noisy)", "trained_both", "memoryless_both", "untrained_both",
                          "trained_open_field"]
    assert h1 == ["place_only", "1", "0.00010", "0.00460", "0.00120 (0.00016)", "0.00200", "0.00300",
                  "0.00400 (0.00000)"]
    assert h10 == ["place_only", "10", "0.01000", "0.02000", "0.01200 (0.00163)", "0.02000", "0.03000",
                   "0.04000 (0.00000)"]
    header, *rows = (cells(line) for line in train.decoder_table(cfg, results, ("place_only",)))
    assert header == ["input set", "arm", "position all", "position open_field", "position loop", "heading all",
                      "heading open_field", "heading loop"]
    assert [row[1] for row in rows] == ["trained_both", "untrained_both", "trained_open_field"]  # no memoryless row
    assert rows[2][2:] == [f"{0.4 + 0.01 * i:.3f}" for i in range(6)]
