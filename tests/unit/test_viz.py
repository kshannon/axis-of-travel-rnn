"""
Every figure carries its title on top and its caption with the data id below.
"""

import numpy as np

from axis_of_travel_rnn import analysis, viz
from axis_of_travel_rnn.blocks.geometry import geometry

TITLE, CAPTION, DATA_ID = "A title", "How to read it and what it shows.", "0123abcd"
FRAMES, UNITS = 200, 4


def test_every_figure_carries_its_title_caption_and_data_id():
    rng = np.random.default_rng(0)
    h, pos = rng.uniform(0, 1, (FRAMES, UNITS)), rng.uniform(0.2, 1.6, (FRAMES, 2))
    heading, direction = rng.uniform(-np.pi, np.pi, FRAMES), rng.integers(-1, 4, FRAMES)
    rows = [{"epoch": e, "train_loss": 1 / e, "val_loss": 1.2 / e} for e in (1, 2, 3)]
    labels = (TITLE, CAPTION, DATA_ID)
    figures = [
        viz.loss_figure(rows, *labels, persistence=0.5),
        viz.rate_map_figure(h, pos, [0, 1], geometry("triple_t"), *labels),
        viz.heading_tuning_figure(h, heading, direction // 2, direction >= 0, [0, 1], *labels),
        viz.cell_heatmap_figure(h[:UNITS, :4], np.zeros((UNITS, 2), bool), np.ones((UNITS, 2), bool), *labels),
        viz.pca_figure(analysis.pca_scores(h, np.ones(FRAMES, bool)), heading, direction, *labels),
    ]
    for fig in figures:
        caption = " ".join(t.get_text() for t in fig.texts)
        assert fig.get_suptitle() == TITLE and CAPTION in caption and DATA_ID in caption
        fig.canvas.draw()  # it renders
