"""
Compare two built block folders by content, run as pixi run python scripts/compare_blocks.py OLD NEW, exiting 1 on any difference.
"""

import sys
from pathlib import Path

import numpy as np
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

BLOCKS_CSV, BLOCKS_DIR = "blocks.csv", "blocks"


def same_table(a, b):
    """
    Whether two Arrow tables have the same schema and the same values column by column, NaN equal to NaN.
    """
    if a.schema != b.schema:
        return False
    for name in a.column_names:
        x, y = a.column(name).to_numpy(zero_copy_only=False), b.column(name).to_numpy(zero_copy_only=False)
        if not np.array_equal(x, y, equal_nan=x.dtype.kind == "f"):
            return False
    return True


def main(old, new):
    """
    Print the blocks only one folder holds, the blocks whose parquet differs and whether blocks.csv differs, and return 1 when anything does.
    """
    old, new = Path(old), Path(new)
    ids = {root: {path.stem for path in (root / BLOCKS_DIR).glob("*.parquet")} for root in (old, new)}
    problems = [f"only in {root}: {block_id}" for root, other in ((old, new), (new, old)) for block_id in sorted(ids[root] - ids[other])]
    problems += [f"differs: {block_id}" for block_id in sorted(ids[old] & ids[new])
                 if not same_table(pq.read_table(old / BLOCKS_DIR / f"{block_id}.parquet"), pq.read_table(new / BLOCKS_DIR / f"{block_id}.parquet"))]
    if not same_table(pacsv.read_csv(old / BLOCKS_CSV), pacsv.read_csv(new / BLOCKS_CSV)):
        problems.append(f"differs: {BLOCKS_CSV}")
    print("\n".join(problems) if problems else f"{len(ids[old])} blocks and {BLOCKS_CSV} equal")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
