"""
The synthetic folder: generated sets, each a blocked synthetic session with its provenance and the guesses made against it.
"""

import shutil

from ..utilities import paths, tables
from ..utilities.blocks import BLOCK_SCHEMA, BLOCKS_CSV, BLOCKS_CSV_SCHEMA, BLOCKS_DIR
from ..utilities.errors import Invalid, NotFound
from ..utilities.files import PARQUET, TEMP, columns_of, read_json, require, safe_stem, temp_of, write_json

# The layout (docs/architecture.md, Resources on disk). A set is written whole under a folder with the temporary suffix, then
# renamed. Its block files are the shared block format of utilities/blocks.py.
SETS_DIR = "sets"
PROVENANCE = "provenance.json"
GUESSES = "guesses.json"

# What a set records about how it was made (docs/plan.md, Synthetic slice design): the sources and environments it drew on, the camera,
# seed, lengths, rules and settings it was generated under, the code and generator versions, the recipe of the real blocks and of its own
# blocks, the generator's warnings and the blocks that failed to build. A guess is one answer on the quiz page: when, who, the pair, the
# two blocks, the kind, the block the person called real and whether they were right.
PROVENANCE_KEYS = ("set_id", "created_at", "created_by", "sources", "environments", "camera", "seed", "length_s", "rules", "settings",
                   "code_version", "generator", "recipe_real", "recipe_synthetic", "warnings", "failed")
GUESS_KEYS = ("at", "by", "pair_id", "real_block", "synthetic_block", "kind", "guessed_real", "correct")


def check_set_block(set_id, block):
    """
    Invalid unless the block's row holds every csv column and its id starts with the set id, so a block names the set holding it.
    """
    require("block row", BLOCKS_CSV_SCHEMA.names, block["row"])
    block_id = safe_stem(block["row"]["block_id"])
    if not block_id.startswith(set_id):
        raise Invalid(f"block {block_id} does not start with the set id {set_id}")


class SyntheticAccess:
    """
    The synthetic folder at root: one folder per set with its blocks, index, provenance and guesses.
    """

    def __init__(self, root):
        self.root = root

    def schema(self):
        """
        The files, columns and keys a set holds, as json. The blocks are the processed format, guesses arrive with the first answer.
        """
        return {"files": [
            {"path": f"{SETS_DIR}/<set_id>/{PROVENANCE}", "optional": False, "keys": list(PROVENANCE_KEYS)},
            {"path": f"{SETS_DIR}/<set_id>/{BLOCKS_CSV}", "optional": False, "columns": columns_of(BLOCKS_CSV_SCHEMA)},
            {"path": f"{SETS_DIR}/<set_id>/{BLOCKS_DIR}/<block_id>{PARQUET}", "optional": False, "columns": columns_of(BLOCK_SCHEMA)},
            {"path": f"{SETS_DIR}/<set_id>/{GUESSES}", "optional": True, "keys": list(GUESS_KEYS)},
        ]}

    def health(self):
        """
        The folder's root, whether it exists, how it breaks the format, and when whole its counts and when it last changed.
        """
        problems = self._problems()
        health = {"root": str(self.root), "exists": self.root.is_dir(), "problems": problems, "counts": {}, "manifest": None}
        if problems:
            return health
        sets = self.sets()
        counts = {"sets": len(sets), "blocks": sum(len(self.blocks(set_id)) for set_id in sets), "guesses": sum(len(self.guesses(set_id)) for set_id in sets)}
        modified = paths.newest_mtime(self.root) if self.root.is_dir() else None
        return {**health, "counts": counts, "manifest": {"modified": modified} if modified else None}

    def sets(self):
        """
        The ids of the sets, sorted.
        """
        return sorted(path.name for path in (self.root / SETS_DIR).glob("*") if path.is_dir() and not path.name.endswith(TEMP))

    def set(self, set_id):
        """
        The set's provenance, or NotFound.
        """
        return read_json(self._folder(set_id) / PROVENANCE)

    def blocks(self, set_id):
        """
        The rows of the set's blocks index, or NotFound.
        """
        return tables.read_csv(self._folder(set_id) / BLOCKS_CSV, BLOCKS_CSV_SCHEMA)

    def block(self, set_id, block_id):
        """
        One block of the set: its index row and its arrays, or NotFound.
        """
        row = next((row for row in self.blocks(set_id) if row["block_id"] == block_id), None)
        if row is None:
            raise NotFound(f"no block {block_id} in set {set_id}")
        return {"row": row, "arrays": tables.read_parquet(self._folder(set_id) / BLOCKS_DIR / f"{safe_stem(block_id)}{PARQUET}")}

    def find_block(self, block_id):
        """
        The id of the set holding the block, none when no set does.
        """
        return next((set_id for set_id in self.sets() if any(row["block_id"] == block_id for row in self.blocks(set_id))), None)

    def write_set(self, set_id, blocks, provenance):
        """
        Write a new set whole: every file goes under a temporary folder, renamed into place at the end, and a set that exists is refused.
        """
        require("provenance", PROVENANCE_KEYS, provenance)
        if provenance["set_id"] != set_id:
            raise Invalid(f"provenance is of set {provenance['set_id']}, not {set_id}")
        for block in blocks:
            check_set_block(set_id, block)
        target = self.root / SETS_DIR / safe_stem(set_id)
        if target.exists():
            raise Invalid(f"set {set_id} exists")
        stage = temp_of(target)
        shutil.rmtree(stage, ignore_errors=True)
        try:
            for block in blocks:
                tables.write_parquet(block["arrays"], stage / BLOCKS_DIR / f"{block['row']['block_id']}{PARQUET}", BLOCK_SCHEMA)
            tables.write_csv([block["row"] for block in blocks], stage / BLOCKS_CSV, BLOCKS_CSV_SCHEMA)
            write_json(provenance, stage / PROVENANCE)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        stage.rename(target)
        return {"blocks": len(blocks), "folder": target.relative_to(self.root).as_posix()}

    def delete_set(self, set_id):
        """
        Remove the set's folder whole and say whether there was one and how many blocks went.
        """
        target = self.root / SETS_DIR / safe_stem(set_id)
        existed = target.is_dir()
        blocks = len(self.blocks(set_id)) if existed else 0
        shutil.rmtree(target, ignore_errors=True)
        return {"deleted": existed, "blocks": blocks}

    def guesses(self, set_id):
        """
        The guesses made against the set, empty before the first, or NotFound.
        """
        return read_json(self._folder(set_id) / GUESSES) or []

    def write_guess(self, set_id, guess):
        """
        Append the guess to the set's guesses, written whole through a temporary name, and return how many there are now.
        """
        require("guess", GUESS_KEYS, guess)
        guesses = [*self.guesses(set_id), guess]
        path = self._folder(set_id) / GUESSES
        write_json(guesses, temp_of(path))
        temp_of(path).replace(path)
        return len(guesses)

    def _folder(self, set_id):
        """
        The folder of a set that exists, or NotFound.
        """
        folder = self.root / SETS_DIR / safe_stem(set_id)
        if not folder.is_dir():
            raise NotFound(f"no set {set_id}")
        return folder

    def _problems(self):
        """
        How the folder breaks its format: a set without its provenance or index, an index lacking columns or disagreeing with the block files, temporary files or folders left by a crash, and any json file that does not parse.
        """
        problems = []
        for set_id in self.sets():
            folder = self.root / SETS_DIR / set_id
            relative = f"{SETS_DIR}/{set_id}"
            for name in (PROVENANCE, BLOCKS_CSV):
                if not (folder / name).is_file():
                    problems.append(f"{relative} has no {name}")
            for name in (PROVENANCE, GUESSES):
                try:
                    read_json(folder / name)
                except ValueError:
                    problems.append(f"{relative}/{name} is not valid json")
            on_disk = {path.stem for path in (folder / BLOCKS_DIR).glob(f"*{PARQUET}")}
            index = folder / BLOCKS_CSV
            if index.is_file():
                missing = [name for name in BLOCKS_CSV_SCHEMA.names if name not in tables.csv_columns(index)]
                if missing:
                    problems.append(f"{relative}/{BLOCKS_CSV} lacks {', '.join(missing)}")
                else:
                    named = [row["block_id"] for row in self.blocks(set_id)]
                    absent = [block_id for block_id in named if block_id not in on_disk]
                    if absent:
                        problems.append(f"{relative} has {len(absent)} block files missing, the first is {absent[0]}")
                    on_disk -= set(named)
            if on_disk:
                problems.append(f"{relative} has {len(on_disk)} block files with no row in {BLOCKS_CSV}, the first is {sorted(on_disk)[0]}")
        stray = sorted(self.root.rglob(f"*{TEMP}")) if self.root.is_dir() else []
        if stray:
            problems.append(f"{len(stray)} temporary files or folders left by an interrupted write, the first is {stray[0].relative_to(self.root)}")
        return problems
