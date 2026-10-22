"""
Every setting of the pilot as plain named values: the worlds, the loop agent's steering, the presets and check limits.
"""

from proj_helpers.paths import repo_root

DATA_DIR = repo_root() / "datasets" / "pilot"
RUNS_DIR = DATA_DIR / "runs"  # one folder per preset and data hash, then one per arm and seed (train.run_dir)

# The two worlds share one room, ROOM; the loop has a central hole that leaves a ring corridor CORRIDOR wide.
WORLDS = ("open_field", "loop")
ROOM = (1.0, 1.0)  # m, the x and y extent of the room, the same for both worlds
CORRIDOR = 0.25  # m, so the hole is the room less CORRIDOR on every side; a corner of the ring is CORRIDOR by CORRIDOR

# The loop agent is steered round the corridor centre line; the open field agent keeps stock RatInABox motion.
# CORRIDOR and DRIFT_RATIO were chosen by the sweep in sweep.py (rule and table in the notebook appendix); the steering
# did the work. The sweep's last tie-break picked a 2.0 by 1.0 m room, but 1.0 by 1.0 m passes every criterion with the
# same numbers and keeps the two axes and the open field balanced, so ROOM was reverted to the brief's square (pilot.md
# Appendix C, issues 17 and 20; open for the authors).
DRIFT_RATIO = 2  # RatInABox drift_to_random_strength_ratio: the pull to the target has time constant 0.7 s / this
REPEL_FRACTION = 1 / 3  # the loop agent's wall_repel_distance is this times CORRIDOR (RatInABox default 0.1 m)
WAYPOINT_RADIUS = 0.05  # m, the target moves on to the next corner when the agent is this close to it
MEAN_LAPS = 2  # laps between flips of the direction round the loop, drawn from a geometric distribution with this mean
STEER_SPEED = 0.15  # m/s, the speed of the velocity the agent is pulled towards

# Stage 2 training. The threshold file is pre-registered (pilot.md Appendix C, issue 23): the notebook hashes it and
# compares with this value, and a builder never edits the file.
THRESHOLDS_SHA256 = "b154c2ed5f6eebcd5ca36bb2c79022dc66cd2ebf3f360ac221d1fa3aad500d22"
NUM_THREADS = 4  # torch threads for training and evaluation
DIETS = (WORLDS, ("open_field",))  # the worlds a trained network sees; the first is the main one

# Analysis (notebook sections 3 and 4) and the figures of viz.py.
ANALYSIS_SEED = 0  # seeds the rng of the permutation and shift nulls of every run, so all runs are analysed alike
FIGURES_DIR = DATA_DIR / "figures"  # the animation; git-ignored with the rest of datasets/
ANIMATION_STEPS = 1200  # steps from the start of a session that the animation shows (60 s at dt 0.05)
ANIMATION_EVERY = 4  # steps between frames, so 300 frames
ANIMATION_FPS = 20
ANIMATION_DPI = 60
ANIMATION_UNITS = 6  # the units with the largest axis selectivity, drawn as bars

PILOT = {
    "name": "pilot",
    # Stage 1, the toy data
    "dt": 0.05,
    "session_s": 600.0,
    "burn_in_s": 5.0,  # simulated first and dropped, so a saved session is exactly session_s long
    "n_train": 14,  # sessions per world, split by session index: the first n_train train,
    "n_val": 2,  # the next n_val validate,
    "n_test": 4,  # and the last n_test test
    "session_seed_base": {"open_field": 0, "loop": 100},  # session i of a world has seed base + i
    "layout_seed": {"open_field": 1000, "loop": 1001},  # fixed per world, never varied
    "wall_geometry": {"open_field": "euclidean", "loop": "line_of_sight"},
    "speed_mean": 0.15,  # m/s, the Rayleigh mean; RatInABox is given the matching Rayleigh scale
    "place_n": 100,
    "place_width": 0.10,  # m, the Gaussian sd of a place field
    "hd_n": 30,
    "hd_spread_deg": 45.0,  # the sd of the von Mises tuning of a head direction cell
    # Stage 2, used from dataset.py on
    "horizon": 10,  # steps
    "horizons": (1, 10, 20),  # steps, for the test loss table
    "window": 400,  # steps
    "stride": 100,  # steps
    "no_loss_steps": 20,  # the first steps of a window carry no loss
    "input_noise_sd": 0.10,  # on place and HD inputs, in training and evaluation; targets stay clean
    "n_hidden": 128,
    "rnn_type": "vanilla",
    "learning_rate": 1e-3,
    "batch_size": 64,
    "grad_clip": 1.0,
    "patience": 10,  # epochs without a better validation loss before stopping
    "max_epochs": 100,
    "trained_seeds": (0, 1, 2, 3, 4),
    "untrained_seeds": tuple(range(20)),
    "memoryless_seeds": (0,),
}

SMOKE = {
    **PILOT,
    "name": "smoke",
    "session_s": 120.0,
    "n_train": 2,
    "n_val": 1,
    "n_test": 1,
    "horizons": (10,),
    "window": 200,
    "batch_size": 16,  # a world has only 44 training windows here, so 64 would leave an open-field-only epoch with none
    "max_epochs": 2,
    "trained_seeds": (0,),
    "untrained_seeds": (0,),
}

# The preset keys that change a session. With the room and steering values above they are hashed into the name of the
# session folder (worlds.data_hash), so a changed setting never reuses old sessions. A code change is not a setting.
DATA_KEYS = ("dt", "session_s", "burn_in_s", "session_seed_base", "layout_seed", "wall_geometry", "speed_mean",
             "place_n", "place_width", "hd_n", "hd_spread_deg")

# Limits for the section 1 data checks; the checks themselves are in worlds.py.
MOVING_SPEED = 0.03  # m/s, a step slower than this has no direction of travel
ALONG_DEG = 45.0  # heading this close to a corridor direction counts as travelling that way
MIN_DIRECTION_S = 5.0  # each of the 8 segment and direction pairs needs this much time
MAX_OPEN_RESULTANT = 0.1  # open field heading: resultant length of the angles and of the doubled angles
# The brief gives no number for "concentrated on two axes in the loop"; 0.8 is the builder's choice, for the authors.
MIN_ALONG_FRACTION = 0.8  # loop heading: share of moving steps in a segment that run along it
MAX_ACROSS_RATE = 1e-3  # largest rate of a place cell at a point whose line of sight crosses the hole
STALL_SPEED = 0.02  # m/s
MAX_STALL_S = 5.0  # longest time below STALL_SPEED
