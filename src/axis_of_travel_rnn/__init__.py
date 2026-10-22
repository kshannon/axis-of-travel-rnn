"""
Axis-of-travel emergence in a position-predicting vanilla RNN. The notebook surface: load_config, then load_blocks, make_windows, make_dataset, train, evaluate, measures, figures, save_results.
"""

__version__ = "0.2.0"

from pathlib import Path

import numpy as np
from tqdm.auto import tqdm

from proj_helpers.paths import local_config, repo_root

from . import viz
from .analysis import axis_selectivity, frame_directions, load_thresholds, pca_scores, scale
from .analysis import measures as run_measures
from .blocks.geometry import geometry
from .config import ExperimentConfig, load_config, resolved
from .data import SPLITS, block_rows, built_folder, data_id, guard, read_block, resample, split_by_date
from .dataset import TARGETS, WindowDataset, fit_scaler
from .dataset import make_windows as windows_of
from .training import Trainer, hidden_states, make_model, model_loss, persistence_loss

__all__ = ["ExperimentConfig", "load_config", "resolved", "load_blocks", "make_windows", "make_dataset", "train",
           "evaluate", "measures", "figures", "save_results"]

FIGURE_UNITS = 4  # the units drawn in the rate maps and tuning curves, the most axis selective
TRACK_ENVIRONMENT = "triple_t"


def thresholds_path(analysis):
    """
    The thresholds yaml of the analysis section, relative to the repository unless absolute.
    """
    path = Path(analysis.thresholds)
    return path if path.is_absolute() else repo_root() / path


def load_blocks(data, folder=None, config=None):
    """
    The blocks of the data section's built folder (or an explicit folder) at its training rate, split whole by recording date, with the folder and its data id.
    """
    folder = built_folder(data.blueprint, config) if folder is None else Path(folder)
    rows = block_rows(folder)
    split = split_by_date(rows, data.split, data.seed)
    blocks = {name: [] for name in SPLITS}
    for row in tqdm(rows, desc="blocks"):
        blocks[split[row["session_id"]]].append(resample(read_block(folder, row), data.rate_hz))
    return {"folder": folder, "data_id": data_id(folder), "split": split, "blocks": blocks}


def make_windows(loaded, windows):
    """
    The windows of each split's blocks at the windows section's settings, and the verdict of every block by id.
    """
    found = {name: windows_of(blocks, windows.model_dump()) for name, blocks in loaded["blocks"].items()}
    return {"windows": {name: rows for name, (rows, _) in found.items()},
            "verdicts": {block_id: verdict for _, verdicts in found.values() for block_id, verdict in verdicts.items()}}


def make_dataset(loaded, windowed, inputs):
    """
    A WindowDataset per split of the inputs section's columns, scaled by the scaler fitted on the train blocks only, and that scaler.
    """
    columns = tuple(dict.fromkeys(inputs.columns + TARGETS))
    scaler = fit_scaler(loaded["blocks"]["train"], columns)
    return {"scaler": scaler, **{name: WindowDataset(loaded["blocks"][name], windowed["windows"][name], inputs.columns, scaler)
                                 for name in SPLITS}}


def train(datasets, model, training, seed, checkpoint_dir=None, config=None):
    """
    A network of the model section trained on the train split with early stopping on the validation split, and its rows per epoch, checkpoints written outside git and the data when a folder is given.
    """
    if checkpoint_dir is not None:
        guard(checkpoint_dir, local_config() if config is None else config)
    net = make_model(model.kind, len(datasets["train"].columns), len(TARGETS), model.hidden_size, seed)
    trainer = Trainer(net, training.learning_rate, training.batch_size, training.epochs, training.patience, training.device,
                      checkpoint_dir, seed)
    return net, trainer.fit(datasets["train"], datasets["validation"])


def evaluate(net, datasets, device="cpu"):
    """
    The masked mean squared error of the network and of the persistence baseline on each split.
    """
    return {name: {"loss": model_loss(net, datasets[name], device), "persistence": persistence_loss(datasets[name])}
            for name in SPLITS}


def measures(net, datasets, analysis, seed, device="cpu"):
    """
    The analysis section's measures of an rnn's hidden states on the test blocks, decoders fitted on the validation blocks, with those test blocks and their hidden states.
    """
    with_hidden = {name: [{**block, "hidden": h} for block, h in zip(datasets[name].blocks, hidden_states(net, datasets[name], device))]
                   for name in ("validation", "test")}
    found = run_measures(with_hidden["test"], with_hidden["validation"], load_thresholds(thresholds_path(analysis)), seed,
                         analysis.measures)
    return {**found, "blocks": with_hidden["test"]}


def figures(config, loaded, rows, evaluation, found):
    """
    The loss curves, rate maps, heading tuning, direction heatmap and PCA of a run, each titled and captioned with the data that made it.
    """
    thr = load_thresholds(thresholds_path(config.analysis))
    track = [b for b in found["blocks"] if b["row"]["kind"] == "track"]
    h = scale(np.concatenate([b["hidden"] for b in track]), found["scaling"])
    pos = np.concatenate([np.column_stack([b["arrays"]["x"], b["arrays"]["y"]]) for b in track])
    heading = np.concatenate([b["arrays"]["heading"] for b in track])
    direction = frame_directions(track, thr)
    units = np.argsort(-np.abs(axis_selectivity(found["direction_means"])[:, 0]))[:FIGURE_UNITS]
    sessions = sorted({b["row"]["session_id"] for b in track})
    data = (f"{config.data.blueprint}, data id {loaded['data_id'][:12]}, the test split's track blocks of sessions "
            f"{', '.join(sessions)}, seed {config.seed}")
    return {
        "loss": viz.loss_figure(
            rows, "Training and validation loss", "Masked mean squared error of the predicted position per epoch, solid "
            "train and dashed validation, the dotted line the persistence baseline on validation. Lower is better.",
            f"{config.data.blueprint}, data id {loaded['data_id'][:12]}, train and validation splits, seed {config.seed}",
            persistence=evaluation["validation"]["persistence"]),
        "rate_maps": viz.rate_map_figure(
            h, pos, units, geometry(TRACK_ENVIRONMENT), "Rate maps of the most axis selective units",
            "Mean scaled activity by position on the track, the walls of the yaml's triple-T drawn over it, grey where "
            "the rat never was. Activity confined to corridors of one axis is what an axis unit shows.", data),
        "heading_tuning": viz.heading_tuning_figure(
            h, heading, np.where(direction >= 0, direction // 2, -1), direction >= 0, units,
            "Heading tuning of the most axis selective units", "Mean scaled activity by head direction on running frames "
            "in passes along east-west corridors (left) and north-south corridors (right), a row per unit. Heading is "
            "analysis only and never reaches the network.", data),
        "heatmap": viz.cell_heatmap_figure(
            found["direction_means"], found["direction"], found["axis"], "Activity by direction of travel",
            "Mean scaled activity of every unit in each direction of travel, units sorted by east-west selectivity, the "
            "right panel marking units that pass the direction and axis tests.", data),
        "pca": viz.pca_figure(
            pca_scores(h, direction >= 0), heading, direction, "Hidden state PCA on running frames",
            "The first three principal components of the hidden states on frames in a pass, coloured by head direction "
            "(top) and by direction of travel (bottom). Opposite directions of one axis overlapping is the axis "
            "signature.", data),
    }


def save_results():
    """
    A stub: writing an experiment's summary, metrics and figures arrives with step 16 of docs/restructure/tasks.md.
    """
    raise NotImplementedError("save_results arrives with step 16 of docs/restructure/tasks.md")
