"""
The processor's output folder (docs/process_lab_data/spec.md Outputs): the blocks csv and parquet per kind, the manifest.
"""

from pathlib import Path

import pyarrow.csv as pacsv

from axis_of_travel_rnn import trajectory

from ..utilities.errors import NotFound

# The columns the window logic reads for a block's heading and trip shares, kept in memory per block file with its
# modification time, so each block is read once and again only after the processor rewrites it.
SHARE_COLUMNS = ("heading", "heading_filled", "heading_held", "trip")
SHARES = {}


def is_built(sources):
    """
    Whether the processor has written its manifest under the folder.
    """
    return (sources.processed_root() / trajectory.MANIFEST).is_file()


def require_built(sources):
    """
    NotFound unless the processor has written its manifest under the folder.
    """
    if not is_built(sources):
        raise NotFound(f"no processed dataset under {sources.processed_root()}: it has no {trajectory.MANIFEST}. Run pixi run process-lab-data")


def csv_columns(sources, kind):
    """
    The column names of a kind's blocks csv, read from its header.
    """
    return pacsv.open_csv(sources.processed_root() / kind / trajectory.BLOCKS_CSV).schema.names


def has_blocks_csv(sources, kind):
    """
    Whether the kind's blocks csv exists.
    """
    return (sources.processed_root() / kind / trajectory.BLOCKS_CSV).is_file()


def list_blocks(sources):
    """
    The rows of every kind's blocks csv with the kind and the path of each block's parquet added.
    """
    return trajectory.list_blocks(sources.processed_root())


def read_manifest(sources):
    """
    The processor's manifest as a dict.
    """
    return trajectory.read_manifest(sources.processed_root())


def load_block(path):
    """
    A block parquet as a dict of numpy arrays.
    """
    return trajectory.load_block(path)


def block_shares(path):
    """
    The share columns of a block parquet, read once and kept until the file changes.
    """
    stamp = Path(path).stat().st_mtime_ns
    if path not in SHARES or SHARES[path][0] != stamp:
        block = load_block(path)
        SHARES[path] = (stamp, {name: block[name] for name in SHARE_COLUMNS})
    return SHARES[path][1]


def blocks_with_shares(sources):
    """
    The rows of every block and, by block id, the columns its verdict is computed from.
    """
    require_built(sources)
    rows = list_blocks(sources)
    return rows, {row["block_id"]: block_shares(row["path"]) for row in rows}
