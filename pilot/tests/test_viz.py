"""
The figures: each function draws from a trace of the cached SMOKE sessions, and the animation is a gif that plays.
"""

import numpy as np
import pytest
from matplotlib.figure import Figure
from PIL import Image

from pilot import analysis, train, viz
from pilot.config import SMOKE
from pilot.dataset import fit_scaler, make_feature_layout, select_sessions
from pilot.worlds import WORLDS, load_sessions, make_layouts

CFG = SMOKE
LAYOUTS = make_layouts(CFG)
SESSIONS = load_sessions(CFG, LAYOUTS)  # the cached SMOKE sessions
THR = analysis.load_thresholds()
ARM = train.ArmSpec("place_only", WORLDS, "untrained")  # random weights are enough to draw


@pytest.fixture(scope="module")
def traced():
    model = train.make_model(ARM, CFG, 0)
    layout = make_feature_layout(ARM.input_set, CFG)
    scaler = fit_scaler(select_sessions(SESSIONS, CFG, "train", ARM.diet))
    session = select_sessions(SESSIONS, CFG, "test", ("loop",))[0]
    trace = viz.session_trace(model, session, layout, scaler, CFG, train.NOISE_SEEDS["test"])
    fast = train.hidden_states(model, [session], layout, scaler, CFG, train.NOISE_SEEDS["test"])[0]
    assert np.allclose(trace["hidden"], fast, atol=1e-5)  # the same noise, and the trace path agrees with the fast one
    return model, session, analysis.scale(trace["hidden"], analysis.fit_scaling(trace["hidden"]))


def test_each_figure_function_returns_a_figure(traced):
    model, session, h = traced
    pos, heading, speed = session.pos, session.heading, session.speed
    means = analysis.cell_means(h, analysis.cell_masks(pos, heading, speed, THR))
    units = viz.most_axis_like(h, pos, heading, speed, THR, 3)[0]
    window = viz.fixed_window(ARM, CFG, SESSIONS)
    history = {"arm": ARM.name, "seed": 0, "train_loss": [0.03, 0.02], "val_loss": [0.03, 0.025], "best_epoch": 2}
    none = np.zeros(h.shape[1], dtype=bool)
    figures = [
        viz.loss_figure([[("a", [(history["train_loss"], history["val_loss"])])]], 0.01),
        viz.probe_figure(history, viz.window_trace(model, window), window, THR),
        viz.rate_map_figure(h, pos, units, "loop"),
        viz.heading_tuning_figure(h, pos, heading, speed, units, THR),
        viz.cell_heatmap_figure(means, none, none),
        viz.distance_figure(means),
        viz.pca_figure(h, pos, heading, speed, THR),
        viz.released_figure({"place_only": {"a": [0.1], "b": [0.0, 0.2]}}, 0.05, {"place_only": 0.1}),
    ]
    assert all(isinstance(fig, Figure) for fig in figures)


def test_world_figure_and_the_animation_is_a_gif_with_one_frame_per_step_group(traced, tmp_path):
    _, session, h = traced
    assert isinstance(viz.world_figure("loop", LAYOUTS["loop"], SESSIONS["loop"], CFG), Figure)
    path = viz.animate_session(tmp_path / "walk.gif", session.pos, session.heading, session.speed, h, THR,
                               n_steps=40, every=4)
    with Image.open(path) as gif:
        assert gif.n_frames == 10
