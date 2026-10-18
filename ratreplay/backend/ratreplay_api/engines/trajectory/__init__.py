"""
TrajectoryEngine: the one contract for selecting, cutting, labelling and windowing trajectories, six operations over arrays with every rule a parameter.
"""

from . import build, funnel, session, windows
from .edits import apply_edits

# The engine's own version, bumped when a change alters what an operation returns for the same input. A build records it
# beside the rules and settings it used.
VERSION = 1

# The default of every rule, the constants the engine moved in from the lab data processor and the project's trajectory
# module under snake_case names. A caller passes its own dict to session and blocks. The tuples stay tuples here.
RULES = {
    # Which epochs are cut: the condition kept and the epoch kinds cut. No rule leaves a session out by a tag, the person excludes.
    "condition": "baseline",
    "epochs": ("arena", "track"),

    # Cut points: a step in t over this is a pause, the lights whose loss makes a tracking gap ("either" or "both"),
    # and the step in pixels that is a tracking jump.
    "pause_step_s": 0.1,
    "gap_lights": "both",
    "jump_px": 40.0,

    # Blocks: trimmed inward from a stretch edge beside a pause, a jump or an epoch bound, the shortest block kept, and
    # how close in seconds a moved edge snaps to a run's start or end.
    "pause_margin_s": 5.0,
    "min_block_s": 10.0,
    "snap_s": 1.0,

    # Heading: the longest gap filled along the shortest arc, and the speed under which the rat is still (held fill, pause label).
    "heading_fill_s": 3.0,
    "running_floor_m_per_s": 0.03,

    # Labels: the lab's path ids of the outbound and return runs, and the shortest stillness in a run that is a pause.
    "outbound_paths": (1, 2, 3, 4),
    "return_paths": (9, 10),
    "pause_min_s": 1.0,

    # Frame, the track scale from the running positions: histogram bin, peak smoothing, peak prominence, axis agreement.
    "histogram_bin_px": 2.0,
    "peak_smooth_bins": 5,
    "peak_prominence": 0.1,
    "axis_agree": 0.05,

    # Frame, the arena against the track: the heights behind the parallax ratio (camera - track) / (camera - arena), in metres.
    "camera_height_m": 2.6,
    "track_height_m": 0.2,
    "arena_height_m": 0.4,

    # Frame, the paper's LED separation used by the still floor, and the percentiles of the arena's moving positions.
    "nominal_led_separation_m": 0.05,
    "extent_percentiles": (1, 99),

    # Frame, the range in metres a kind's LED separation must fall in, else a warning.
    "led_separation_m": (0.04, 0.08),

    # Frame, motion: frames averaged for speed and direction, the speed in pixels per second that is running, and the
    # offset in degrees from a rat's median over which its LEDs are reported swapped.
    "speed_smooth_frames": 6,
    "running_px_per_s": 20.0,
    "offset_warn_deg": 30.0,

    # Checks, reported as problems of a block and never a reason to drop it: the most a step in t may differ from one frame.
    "t_step_tolerance_s": 1e-6,

    # Kinematics: the Savitzky-Golay window in seconds and order, and the version naming this derivation in a build.
    "smooth_window_s": 0.15,
    "smooth_order": 2,
    "kinematics_version": 1,
}

# The default window settings: a window, the stride between windows, the burn-in inside it, the future position
# predicted, the rate the RNN project resamples to, and the two block checks (measured heading share, complete trips).
# rate_hz is recorded in windows.json for that project and is unused by windows, which works at the rate of the block's row.
SETTINGS = {
    "window_s": 40.0,
    "stride_s": 10.0,
    "burn_in_s": 1.0,
    "horizon_s": 0.5,
    "rate_hz": 20,
    "min_heading_measured": 0.8,
    "min_complete_trips": 1,
}


class TrajectoryEngine:
    """
    Stateless: arrays in, arrays and plain data out, called by the managers alone.
    """

    def funnel(self, tables, rules):
        """
        Per session whether it is in the dataset and why not, and the epochs the rules select, from the sessions, epochs and annotations tables alone.
        """
        return funnel.funnel(tables, rules)

    def session(self, arrays, environment, rules):
        """
        Kinematics in metres, heading offset and fills, stops, cut points, spans, occupancy, the initial blocks and the rules used, from a session's arrays and the geometry of its environments by name, what the Replay page draws and what apply reads.
        """
        return session.build(arrays, environment, rules)

    def apply(self, blocks, edits, session):
        """
        The blocks, cuts and flagged runs the edits make of the blocks and the refusals with their reasons, under the edit legality rules the session carries.
        """
        return apply_edits(blocks, edits, session)

    def blocks(self, arrays, review, environment, rules):
        """
        The labelled blocks (trip, phase, frames in metres at the lab rate) of a session from the review's confirmed and edited blocks or the initial blocks, for real and generated arrays alike, as a dict of blocks (each a row and arrays for ProcessedAccess.write_blocks), frame (the registration) and warnings, so a manager never calls session as well.
        """
        return build.blocks(arrays, review, environment, rules)

    def windows(self, block, settings, rules):
        """
        The window rows of a block (its row and arrays) with the checks and first failing check of each, the verdict of the block as ok and its reasons, and the window count, under the settings and the rules the block was built with.
        """
        return windows.windows(block, settings, rules)

    def recipe(self, blocks):
        """
        The statistics the generator fits and the numbers real and synthetic blocks are compared on.
        """
        raise NotImplementedError("task E5")
