"""
Every setting of the lab runs as plain named values: the worlds, the split sizes, the field layout and the presets.
"""

from pilot.config import PILOT, SMOKE

WORLDS = ("arena", "track")  # the blocks' kind, the epoch they come from
DIETS = (WORLDS, ("arena",))  # the worlds a trained network sees; the first is the main one, as in the pilot
RATE_HZ = 60  # the lab's camera, and so every block's frame rate
RESAMPLE = 3  # every third frame, so a step is the pilot's dt of 0.05 s
OCCUPANCY_BIN = 0.02  # m, the side of the bins place centres are drawn from

# Machine-local paths, from configs/local.yaml. The three data roots are read-only to this package: the runs folder
# may not be equal to, inside or contain any of them.
PROCESSED_KEY = "PROCESSED_LAB_DATA"
RUNS_KEY = "LAB_RNN_RUNS"
DATA_ROOT_KEYS = (PROCESSED_KEY, "TRANSFORMED_LAB_DATA", "LAB_DATA")

LAB = {
    **PILOT,
    "name": "lab",
    "worlds": WORLDS,
    "diets": DIETS,
    # sessions, not blocks, in date order: the first n_train train, the next n_val validate, the next n_test test
    "n_train": 6,
    "n_val": 1,
    "n_test": 2,
    "resample": RESAMPLE,
    "layout_seed": {"arena": 2000, "track": 2001},  # fixed per world, never varied
    "hd_n": 0,  # no head direction input: the lab's heading never reaches a network
    "checkpoints": True,  # one per epoch and one before the first (authors, 2026-10-19)
    # training windows start every 25 steps (1.25 s) in the arena, every stride steps on the track; evaluation keeps
    # stride everywhere (authors, 2026-10-19, plan Open 1)
    "train_stride": {"arena": 25, "track": PILOT["stride"]},
}

LAB_SMOKE = {
    **LAB,
    "name": "lab_smoke",
    "n_train": 2,
    "n_val": 1,
    "n_test": 1,
    **{key: SMOKE[key] for key in ("horizons", "window", "batch_size", "max_epochs", "trained_seeds",
                                   "untrained_seeds")},
}

# The preset keys that change the sessions. With the bytes of blocks.csv and of every block used they make the data
# id (blocks.data_id), so a changed block or setting never reuses old session copies or runs.
DATA_KEYS = ("dt", "worlds", "n_train", "n_val", "n_test", "resample", "layout_seed", "place_n", "place_width")
