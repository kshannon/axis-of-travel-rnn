"""
A few training steps on a tiny dataset: rows per epoch, checkpoints, the persistence baseline and whole block hidden states.
"""

import numpy as np

from axis_of_travel_rnn import data
from axis_of_travel_rnn.dataset import DEFAULT_INPUTS, WindowDataset, fit_scaler, make_windows
from axis_of_travel_rnn.train import CHECKPOINT, Trainer, hidden_states, make_model, model_loss, persistence_loss

from .handmade import TRAINING_RATE_HZ, wandering

SETTINGS = {"window_s": 4.0, "stride_s": 2.0, "burn_in_s": 1.0, "horizon_s": 0.5, "min_heading_measured": 0.0,
            "min_complete_trips": 0}
HIDDEN, EPOCHS = 8, 2


def test_two_epochs_give_rows_checkpoints_and_hidden_states_of_whole_blocks(tmp_path):
    found = [data.resample(wandering(1801, seed), TRAINING_RATE_HZ) for seed in (0, 1)]
    found[1]["arrays"]["x"][50] = np.nan  # a frame without position: no window holds it, the hidden state skips it
    windows, _ = make_windows(found, SETTINGS)
    dataset = WindowDataset(found, windows, DEFAULT_INPUTS, fit_scaler(found[:1], DEFAULT_INPUTS))
    model = make_model("rnn", 2, 2, HIDDEN, seed=0)
    trainer = Trainer(model, learning_rate=1e-3, batch_size=4, epochs=EPOCHS, patience=5, checkpoint_dir=tmp_path, seed=0)
    rows = trainer.fit(dataset, dataset)
    assert [row["epoch"] for row in rows] == [1, 2]
    assert sorted(p.name for p in tmp_path.iterdir()) == [CHECKPOINT.format(e) for e in range(EPOCHS + 1)]
    assert np.isfinite(model_loss(model, dataset)) and persistence_loss(dataset) > 0
    states = hidden_states(model, dataset)
    assert [len(h) for h in states] == [len(b["arrays"]["t"]) for b in found]
    assert np.isnan(states[1][50]).all() and np.isfinite(states[1][51]).all() and np.isfinite(states[0]).all()
