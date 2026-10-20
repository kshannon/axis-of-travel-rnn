"""
The processed folder: the reviews, the built blocks with their index and metadata, and the selected window settings.
"""

from ..utilities import paths, tables
from ..utilities.blocks import BLOCK_SCHEMA, BLOCKS_CSV, BLOCKS_CSV_SCHEMA, BLOCKS_DIR
from ..utilities.errors import Invalid, NotFound
from ..utilities.files import JSON, PARQUET, TEMP, columns_of, read_json, require, safe_stem, temp_of, write_json

# The layout (docs/architecture.md, Resources on disk). A file being written has the temporary suffix until it is renamed.
# The block files are the shared block format of utilities/blocks.py.
REVIEW_DIR = "review"
METADATA_DIR = "metadata"
WINDOWS = "windows.json"

# The review file: its keys, the value a key takes when a file written before the key existed lacks it, the keys and statuses of each
# of its blocks, and the fields each edit carries. A session is excluded when the person said so (excluded, a bool), and excluded_by
# and excluded_at record who set the flag and when, none until it was set. reviewed_by and reviewed_at stay the review's own.
# start_offset_m is the start offset in metres the person tuned for the session, none meaning the environment yaml's.
REVIEW_KEYS = ("session_id", "reviewed_by", "reviewed_at", "converter_manifest_timestamp", "rules", "blocks", "cuts",
               "flagged_runs", "notes", "edits", "excluded", "excluded_by", "excluded_at", "start_offset_m")
REVIEW_DEFAULTS = {"excluded": False, "excluded_by": None, "excluded_at": None, "start_offset_m": None}
BLOCK_KEYS = ("block_id", "epoch", "environment", "frame_start", "frame_end", "status", "note")
STATUSES = ("auto", "confirmed", "edited", "dropped")
EDIT_FIELDS = {"accept": (), "confirm": ("frame",), "move": ("frame", "edge", "at"), "split": ("frame",), "drop": ("frame",),
               "new": ("frame_start", "frame_end"), "cut": ("frame_start", "frame_end"), "flag": ("run",)}

# What a build records per session (windows is per block the count and verdict at the build's settings, informative, frame the
# registration it was built under, warnings the session's, failed the blocks not written, excluded whether the person excluded
# the session, which writes no blocks, and start_offset_m the start offset in metres it was built with, none for the yaml's), and
# what selecting the window settings records.
METADATA_KEYS = ("rules", "settings", "review_stamp", "code_version", "built_at", "windows", "frame", "warnings", "failed", "excluded",
                 "start_offset_m")
WINDOWS_KEYS = ("settings", "totals", "selected_at", "selected_by")


def check_review(sid, review):
    """
    Invalid naming the first way the review breaks its format or is not the session's.
    """
    require("review", REVIEW_KEYS, review)
    if not isinstance(review["excluded"], bool):
        raise Invalid("review excluded is not true or false")
    if review["session_id"] != sid:
        raise Invalid(f"review is of session {review['session_id']}, not {sid}")
    for number, block in enumerate(review["blocks"]):
        require(f"block {number}", BLOCK_KEYS, block)
        if block["status"] not in STATUSES:
            raise Invalid(f"block {block['block_id']} has status {block['status']}, expected one of {', '.join(STATUSES)}")


def check_block(sid, block):
    """
    Invalid unless the block's row holds every csv column, belongs to the session and names a safe file.
    """
    require("block row", BLOCKS_CSV_SCHEMA.names, block["row"])
    if block["row"]["session_id"] != sid:
        raise Invalid(f"block {block['row']['block_id']} is of session {block['row']['session_id']}, not {sid}")
    safe_stem(block["row"]["block_id"])


class ProcessedAccess:
    """
    The processed folder at root: the reviews, the built blocks and their sessions' metadata, and the window settings.
    """

    def __init__(self, root):
        self.root = root

    def schema(self):
        """
        The files, columns, keys and types the folder holds, as json. Every file is optional, the first save creates it.
        """
        review = {"keys": list(REVIEW_KEYS), "defaults": REVIEW_DEFAULTS, "block_keys": list(BLOCK_KEYS), "statuses": list(STATUSES),
                  "edits": {op: list(fields) for op, fields in EDIT_FIELDS.items()}}
        return {"files": [
            {"path": BLOCKS_CSV, "optional": True, "columns": columns_of(BLOCKS_CSV_SCHEMA)},
            {"path": f"{BLOCKS_DIR}/<block_id>{PARQUET}", "optional": True, "columns": columns_of(BLOCK_SCHEMA)},
            {"path": f"{REVIEW_DIR}/<session_id>{JSON}", "optional": True, **review},
            {"path": f"{METADATA_DIR}/<session_id>{JSON}", "optional": True, "keys": list(METADATA_KEYS)},
            {"path": WINDOWS, "optional": True, "keys": list(WINDOWS_KEYS)},
        ]}

    def health(self):
        """
        The folder's root, whether it exists, how it breaks the format, and when whole its counts and when it last changed.
        """
        problems = self._problems()
        health = {"root": str(self.root), "exists": self.root.is_dir(), "problems": problems, "counts": {}, "manifest": None}
        if problems:
            return health
        modified = paths.newest_mtime(self.root)
        counts = {"reviews": len(self.reviews()), "blocks": len(self.blocks()), "sessions": len(self._ids(METADATA_DIR))}
        return {**health, "counts": counts, "manifest": {"modified": modified} if modified else None}

    def reviews(self):
        """
        The ids of the reviewed sessions, sorted.
        """
        return self._ids(REVIEW_DIR)

    def review(self, sid):
        """
        The session's review, none when it was not reviewed, with the default of every key an older file lacks (excluded is false, the start offset none).
        """
        review = read_json(self._path(REVIEW_DIR, sid, JSON))
        return None if review is None else {**REVIEW_DEFAULTS, **review}

    def write_review(self, sid, review):
        """
        Write the review whole as the session's file after checking it, and say which file, relative to the root, and whether it replaced one.
        """
        check_review(sid, review)
        path = self._path(REVIEW_DIR, sid, JSON)
        replaced = path.is_file()
        write_json(review, temp_of(path))
        temp_of(path).replace(path)
        return {"replaced": replaced, "file": path.relative_to(self.root).as_posix()}

    def delete_review(self, sid):
        """
        Remove the session's review file and say which file, relative to the root, and whether there was one.
        """
        path = self._path(REVIEW_DIR, sid, JSON)
        existed = path.is_file()
        path.unlink(missing_ok=True)
        return {"deleted": existed, "file": path.relative_to(self.root).as_posix()}

    def blocks(self):
        """
        The rows of the blocks index, none when nothing was built.
        """
        path = self.root / BLOCKS_CSV
        return tables.read_csv(path, BLOCKS_CSV_SCHEMA) if path.is_file() else []

    def block(self, block_id):
        """
        One built block: its index row and its arrays, or NotFound.
        """
        row = next((row for row in self.blocks() if row["block_id"] == block_id), None)
        if row is None:
            raise NotFound(f"no block {block_id}")
        return {"row": row, "arrays": tables.read_parquet(self._path(BLOCKS_DIR, block_id, PARQUET))}

    def built(self):
        """
        The ids of the sessions with a build, sorted, a session whose blocks were all dropped among them.
        """
        return self._ids(METADATA_DIR)

    def metadata(self, sid):
        """
        What the session's build used, none when it was not built.
        """
        return read_json(self._path(METADATA_DIR, sid, JSON))

    def write_blocks(self, sid, blocks, metadata):
        """
        Replace the session's blocks, index rows and metadata whole: every file is written under a temporary name, then the old blocks go and the new files are renamed into place.
        """
        require("metadata", METADATA_KEYS, metadata)
        for block in blocks:
            check_block(sid, block)
        built = self.blocks()
        rows = [row for row in built if row["session_id"] != sid] + [block["row"] for block in blocks]
        parquets = [self._path(BLOCKS_DIR, block["row"]["block_id"], PARQUET) for block in blocks]
        meta_path, index = self._path(METADATA_DIR, sid, JSON), self.root / BLOCKS_CSV
        replaced = meta_path.is_file()
        try:
            for block, target in zip(blocks, parquets):
                tables.write_parquet(block["arrays"], temp_of(target), BLOCK_SCHEMA)
            write_json(metadata, temp_of(meta_path))
            tables.write_csv(sorted(rows, key=lambda row: row["session_id"]), temp_of(index), BLOCKS_CSV_SCHEMA)
        except Exception:
            for target in [*parquets, meta_path, index]:
                temp_of(target).unlink(missing_ok=True)
            raise
        for row in built:
            if row["session_id"] == sid:
                self._path(BLOCKS_DIR, row["block_id"], PARQUET).unlink(missing_ok=True)
        for target in [*parquets, meta_path, index]:
            temp_of(target).replace(target)
        return {"blocks": len(blocks), "replaced": replaced}

    def delete_build(self, sid):
        """
        Remove the session's blocks, index rows and metadata whole, the index staged under a temporary name and renamed after the files go (and removed when no row is left, as before the first build), and say how many blocks went.
        """
        rows = self.blocks()
        gone = [row for row in rows if row["session_id"] == sid]
        index, meta_path = self.root / BLOCKS_CSV, self._path(METADATA_DIR, sid, JSON)
        left = [row for row in rows if row["session_id"] != sid]
        if gone and left:
            try:
                tables.write_csv(left, temp_of(index), BLOCKS_CSV_SCHEMA)
            except Exception:
                temp_of(index).unlink(missing_ok=True)
                raise
        for row in gone:
            self._path(BLOCKS_DIR, row["block_id"], PARQUET).unlink(missing_ok=True)
        if gone and left:
            temp_of(index).replace(index)
        elif gone or (index.is_file() and not rows):
            index.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
        return {"blocks": len(gone)}

    def window_settings(self):
        """
        The selected window settings, none when none were selected.
        """
        return read_json(self.root / WINDOWS)

    def write_window_settings(self, settings):
        """
        Write the selected window settings whole after checking them, and say which file and whether it replaced one.
        """
        require("window settings", WINDOWS_KEYS, settings)
        path = self.root / WINDOWS
        replaced = path.is_file()
        write_json(settings, temp_of(path))
        temp_of(path).replace(path)
        return {"replaced": replaced, "file": WINDOWS}

    def _path(self, folder, stem, suffix):
        """
        The file of a safe stem inside one of the root's folders.
        """
        return self.root / folder / f"{safe_stem(stem)}{suffix}"

    def _ids(self, folder):
        """
        The stems of the json files in one of the root's folders, sorted.
        """
        return sorted(path.stem for path in (self.root / folder).glob(f"*{JSON}"))

    def _problems(self):
        """
        How the folder breaks its format: the index lacking columns or disagreeing with the block files, temporary files left by a crash, and any json file that does not parse.
        """
        problems, index = [], self.root / BLOCKS_CSV
        on_disk = {path.stem for path in (self.root / BLOCKS_DIR).glob(f"*{PARQUET}")}
        if index.is_file():
            missing = [name for name in BLOCKS_CSV_SCHEMA.names if name not in tables.csv_columns(index)]
            if missing:
                problems.append(f"{BLOCKS_CSV} lacks {', '.join(missing)}")
            else:
                named = [row["block_id"] for row in self.blocks()]
                absent = [block_id for block_id in named if block_id not in on_disk]
                if absent:
                    problems.append(f"{len(absent)} block files missing, the first is {absent[0]}")
                on_disk -= set(named)
        if on_disk:
            problems.append(f"{len(on_disk)} block files with no row in {BLOCKS_CSV}, the first is {sorted(on_disk)[0]}")
        stray = sorted(self.root.rglob(f"*{TEMP}")) if self.root.is_dir() else []
        if stray:
            problems.append(f"{len(stray)} temporary files left by an interrupted write, the first is {stray[0].relative_to(self.root)}")
        files = [*sorted((self.root / REVIEW_DIR).glob(f"*{JSON}")), *sorted((self.root / METADATA_DIR).glob(f"*{JSON}")), self.root / WINDOWS]
        for path in files:
            try:
                read_json(path)
            except ValueError:
                problems.append(f"{path.relative_to(self.root)} is not valid json")
        return problems
