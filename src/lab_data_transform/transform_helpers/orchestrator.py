"""
The converter's run: each session through the stages as a Record, its line printed, the tables and json files written.
"""

from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa

from . import checks, convert, readers
from .checks import HEADING_TOLERANCE_RAD, PAINTED_TOLERANCE_FRAMES
from .convert import CSV_TABLES, KEYS, PAUSE_STEP_S, table
from .output import write_csv, write_frames, write_json
from .readers import ANALYSIS_PROVENANCE, COLUMNS, DVT_COLUMNS, TRACKING_PROVENANCE

# The converter's settings, recorded in the manifest's run block.
PARAMETERS = {
    "dvt_columns": DVT_COLUMNS,
    "pause_step_s": PAUSE_STEP_S,
    "heading_tolerance_rad": HEADING_TOLERANCE_RAD,
    "painted_tolerance_frames": PAINTED_TOLERANCE_FRAMES,
}


@dataclass(frozen=True)
class Record:
    """
    One session: its Session from the readers, the lab's read dicts, the converted tables and the check results so far.
    """

    session: readers.Session | None = None
    trk: dict | None = None
    ana: dict | None = None
    frames: pa.Table | None = None
    rows: dict | None = None
    facts: dict | None = None
    results: dict = field(default_factory=dict)

    @property
    def failed(self):
        """
        Whether any check so far failed.
        """
        return any(result["status"] == "fail" for result in self.results.values())

    def provenance(self):
        """
        The provenance values the lab's files hold, None for each one absent.
        """
        values = {name: self.trk.get(name) for name in TRACKING_PROVENANCE}
        values.update({name: self.ana.get(name) for name in ANALYSIS_PROVENANCE})
        return values

    def aligned_pixel(self):
        """
        The pixelDvt array when its rows, frame and time match the tracking and it has one more column, else None.
        """
        pixel, dvt = self.ana.get("pixelDvt"), self.trk["processedDVT"]
        if (pixel is not None and len(pixel) == len(dvt) and pixel.shape[1] == COLUMNS["pixelDvt"]
                and np.array_equal(pixel[:, :2], dvt[:, :2])):
            return pixel
        return None

    def with_results(self, results):
        """
        A new record with these check results merged over the ones it holds.
        """
        return replace(self, results={**self.results, **results})


class Orchestrator:
    """
    The output root and the run over the selected sessions.
    """

    def __init__(self, root):
        self.root = Path(root)

    def planned_files(self, sessions):
        """
        The files a run would write, as names under the output root, in the order the dry run prints them.
        """
        return ([f"{name}.csv" for name in CSV_TABLES] + ["manifest.json", "checks.json"]
                + [f"frames/{session.session_id}.parquet" for session in sessions])

    def _process(self, session):
        """
        Read, check, convert, check and write one session's frames: the outcome, check results, tables and entry.
        """
        record = Record(session)
        try:
            for stage in (readers.read, checks.check_inputs, convert.convert, checks.check_converted):
                record = stage(record)
                if record.failed:
                    return "failed", record.results, None, None
            tables = {name: table(name, record.rows[name]) for name in CSV_TABLES}
            write_frames(record.frames, self.root / "frames" / f"{session.session_id}.parquet")
            entry = {
                "written_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "provenance": record.provenance(),
                "rows": {"frames": record.frames.num_rows, **{name: len(rows) for name, rows in record.rows.items()}},
            }
            return "written", record.results, tables, entry
        except Exception as error:
            results = {**record.results}
            checks.add_result(results, "exception", "fail", {"type": type(error).__name__, "message": str(error)})
            return "failed", results, None, None

    def run(self, sessions, skipped, selection):
        """
        Convert each session, then write checks.json, manifest.json and the CSV tables whole; each outcome by id.
        """
        outcomes, failed, counts = {}, {}, Counter()
        results_by_id, tables_by_id, entries = {}, {}, {}
        try:
            for session in sessions:
                session_id = session.session_id
                outcome, results, tables, entry = self._process(session)
                outcomes[session_id] = outcome
                results_by_id[session_id] = results
                if outcome == "written":
                    tables_by_id[session_id], entries[session_id] = tables, entry
                    counts.update(entry["rows"])
                    print(f"{session_id}  written, {len(checks.warnings(results))} warns")
                else:
                    failed[session_id] = {name: results[name] for name in checks.failed(results)}
                    print(f"{session_id}  failed: {', '.join(checks.failed(results))}")
        finally:
            write_json(results_by_id, self.root / "checks.json")
            write_json({"sessions": entries, "run": {
                "parameters": PARAMETERS,
                "only": selection["only"],
                "sample": selection["sample"],
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "written": [session_id for session_id, outcome in outcomes.items() if outcome == "written"],
                "failed": failed,
                "skipped": [{"name": name, "reason": reason} for name, reason in skipped],
                "row_counts": dict(counts),
            }}, self.root / "manifest.json")
            for name, schema in CSV_TABLES.items():
                merged = pa.concat_tables([tables[name] for tables in tables_by_id.values()] or [schema.empty_table()])
                keys = [(key, "ascending") for key in KEYS[name]]
                write_csv(merged.sort_by(keys), self.root / f"{name}.csv")
        return outcomes
