"""
ValidationManager: the health of the folders, the data format, the environments with the registration each built session was given, the readiness of the built blocks at window settings, a block for the player and its windows, and the window settings selected for export.
"""

import getpass
from itertools import groupby

from ..engines.trajectory import RULES, SETTINGS
from ..utilities import clock
from ..utilities.errors import Invalid

# The version of the format the pages render, the one dataset readiness is judged on until SyntheticAccess arrives, and what the manager refuses.
FORMAT_VERSION = 1
REAL = "real"
SYNTHETIC_LATER = "synthetic sets arrive with the synthetic slice"
NOTHING_BUILT = "nothing is built yet, no settings to select"

# What a session's registration row carries, as the build wrote it in the metadata's frame: per epoch kind the scale, LED separation, rotation,
# flip and offset, for the track also its scale along each room axis (named as the row names them) and its measured start offset (missing
# from a build made before it was recorded), and for the session the LED offset.
KIND_KEYS = ("scale_px_per_m", "led_separation_m", "rotation_rad", "flip", "offset_m")
AXIS_SCALES = {"scale_x": "scale_x_px_per_m", "scale_y": "scale_y_px_per_m"}
TRACK_KEYS = ("start_offset_measured_m",)
SESSION_KEYS = ("led_offset_rad", "led_offset_r", "led_offset_n")

# The columns of a built block the player gets. The phase is a string and travels as spans.
ARRAY_COLUMNS = ("frame", "t", "x", "y", "heading", "speed", "turn_rate", "n_lights", "trip")


def spans_of(values):
    """
    The (value, first, last) of every stretch of equal values, as indices into the values.
    """
    spans, first = [], 0
    for value, group in groupby(values):
        last = first + sum(1 for _ in group) - 1
        spans.append((value, first, last))
        first = last + 1
    return spans


def true_spans(mask):
    """
    The [first, last] index pairs of every stretch of True.
    """
    return [[first, last] for value, first, last in spans_of(mask.tolist()) if value]


def runs_of(arrays):
    """
    One span per run of the block with its path id and clean flag, a zero being no run.
    """
    return [{"run": run, "path_id": int(arrays["path_id"][first]), "clean": bool(arrays["clean"][first]), "first": first, "last": last}
            for run, first, last in spans_of(arrays["run"].tolist()) if run != 0]


def trips_of(arrays):
    """
    One span per trip of the block, numbered as the build numbers them, partial when the number is negative, a zero being no trip.
    """
    return [{"trip": abs(trip), "partial": trip < 0, "first": first, "last": last} for trip, first, last in spans_of(arrays["trip"].tolist()) if trip != 0]


def phases_of(arrays):
    """
    One span per stretch of a phase.
    """
    return [{"phase": phase, "first": first, "last": last} for phase, first, last in spans_of(arrays["phase"].tolist())]


def registrations_of(sid, made, epochs):
    """
    The registration a built session was given, as (environment name, row) per epoch kind of the build, the environment being the one the kind's selected epoch lies in. An excluded session has none.
    """
    frame = made["frame"]
    if frame is None:
        return []
    where = {epoch["epoch"]: epoch["environment"] for epoch in epochs}
    return [(where[kind], {"session_id": sid, "kind": kind, **{key: frame[kind][key] for key in KIND_KEYS},
                           **{name: frame[kind][key] for name, key in AXIS_SCALES.items() if key in frame[kind]},
                           **{key: frame[kind][key] for key in TRACK_KEYS if key in frame[kind]},
                           **{key: frame[key] for key in SESSION_KEYS}, "warnings": made["warnings"], "built_at": made["built_at"]})
            for kind in sorted(where) if kind in frame]


def summary_of(rows):
    """
    How many sessions an environment has and how many of them carry a warning, counts and nothing more, a scale or a rotation being summarised by the page.
    """
    return {"n_sessions": len({row["session_id"] for row in rows}), "n_warned": len({row["session_id"] for row in rows if row["warnings"]})}


class ValidationManager:
    """
    Stateless: the engine and the accesses it works with, handed in at the composition root.
    """

    def __init__(self, trajectory, transformed, processed, environment):
        self.trajectory, self.transformed, self.processed, self.environment = trajectory, transformed, processed, environment

    def health(self, config_path):
        """
        The three folders each as its access reports it and the config file they come from. A key the config lacks is a folder the composition root handed in as an access that says so.
        """
        # The synthetic folder joins here with SyntheticAccess.
        return {"transformed": self.transformed.health(), "processed": self.processed.health(), "environments": self.environment.health(),
                "config_path": str(config_path)}

    def format(self):
        """
        The schemas the accesses declare, the default window settings and the engine's rules, what the Incoming, Settings and Outgoing pages render.
        """
        return {"version": FORMAT_VERSION, "transformed": self.transformed.schema(), "processed": self.processed.schema(), "settings": SETTINGS, "rules": RULES}

    def environments(self):
        """
        Every environment of the folder with its kind, yaml parameters and geometry, and the built sessions registered against it, each with the registration its build recorded. Read only.
        """
        # The metadata holds the registration by epoch kind and not the environment each kind lay in, so the environment is read from the
        # session's epochs, the ones the engine's funnel selects under the rules the session was built with. Were an epochs.csv changed since the
        # build, the page would show the new environment. The metadata naming it per kind would end that (one line in ReviewManager._build).
        metadata = {sid: self.processed.metadata(sid) for sid in self.processed.built()}
        tables = self.transformed.sessions()
        found = {}
        for row in tables["sessions"]:
            sid = row["session_id"]
            if sid in metadata:
                epochs = self.trajectory.funnel({**tables, "sessions": [row]}, metadata[sid]["rules"])[sid]["epochs"]
                for name, registration in registrations_of(sid, metadata[sid], epochs):
                    found.setdefault(name, []).append(registration)
        environments = []
        for name in self.environment.environments():
            geometry = self.environment.environment(name)
            rows = sorted(found.get(name, []), key=lambda row: (row["session_id"], row["kind"]))
            environments.append({"name": name, "kind": geometry["kind"], "params": geometry["params"], "geometry": geometry,
                                 "sessions": rows, "summary": summary_of(rows)})
        return environments

    def readiness(self, which, settings):
        """
        Every built block of the dataset with its window count and verdict at the settings, judged under the rules its session was built with, the totals, and per built session the settings and the time its blocks were built at, whether it was built excluded and the blocks that failed with their problems.
        """
        if which != REAL:
            raise Invalid(SYNTHETIC_LATER)
        metadata = {sid: self.processed.metadata(sid) for sid in self.processed.built()}
        blocks = []
        for row in self.processed.blocks():
            found = self.trajectory.windows(self.processed.block(row["block_id"]), settings, metadata[row["session_id"]]["rules"])
            blocks.append({**row, "count": found["count"], "verdict": found["verdict"]})
        ok = [block for block in blocks if block["verdict"]["ok"]]
        totals = {"blocks": len(blocks), "ok": len(ok), "trouble": len(blocks) - len(ok), "windows": sum(block["count"] for block in blocks),
                  "windows_ok": sum(block["count"] for block in ok)}
        # A build made before exclusion was the person's decision has no excluded key until the next rebuild.
        built = {sid: {"settings": made["settings"], "built_at": made["built_at"], "excluded": made.get("excluded", False), "failed": made["failed"]}
                 for sid, made in metadata.items()}
        return {"which": which, "settings": settings, "blocks": blocks, "totals": totals, "built": built}

    def block(self, bid):
        """
        A built block for the player: its row and rate, the geometry of its environment and the spans of its runs, trips, phases and heading fills, as indices into the block's arrays.
        """
        found = self.processed.block(bid)
        row, arrays = found["row"], found["arrays"]
        return {"row": row, "rate_hz": row["rate_hz"], "geometry": self.environment.environment(row["environment"]), "runs": runs_of(arrays), "trips": trips_of(arrays),
                "phases": phases_of(arrays), "heading_filled": true_spans(arrays["heading_filled"]),
                "heading_held": true_spans(arrays["heading_held"]), "one_light": true_spans(arrays["n_lights"] == 1)}

    def arrays(self, bid):
        """
        A built block's arrays over its frames, in metres, what the player plays.
        """
        arrays = self.processed.block(bid)["arrays"]
        return {name: arrays[name] for name in ARRAY_COLUMNS}

    def windows(self, bid, settings):
        """
        The window rows of a built block at the settings with their checks, the verdict of the block and its window count, under the rules its session was built with.
        """
        block = self.processed.block(bid)
        return self.trajectory.windows(block, settings, self.processed.metadata(block["row"]["session_id"])["rules"])

    def selected(self):
        """
        The window settings selected for export with their totals, when and by whom, none when none were selected.
        """
        return {"selected": self.processed.window_settings()}

    def select_settings(self, settings):
        """
        Write the settings whole as the ones selected for export, with the readiness totals they give, by the current user, refused while nothing is built, and say which file and whether it replaced a selection.
        """
        totals = self.readiness(REAL, settings)["totals"]
        if totals["blocks"] == 0:
            raise Invalid(NOTHING_BUILT)
        return self.processed.write_window_settings({"settings": settings, "totals": totals, "selected_at": clock.iso_now(), "selected_by": getpass.getuser()})
