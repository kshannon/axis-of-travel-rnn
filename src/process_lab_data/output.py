"""
Write a block table, the blocks csv rows or a json object to its path under PROCESSED_LAB_DATA, in place, parent folders made, and remove a folder of an earlier run.
"""

import json
import shutil
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from axis_of_travel_rnn.trajectory import COLUMNS

# A block parquet holds the lab frame number first, so a row maps back to the converter's frames, then exactly the
# trajectory schema's columns in its order and dtypes. The blocks csv holds one wide row per block in this order (spec
# Outputs): the block and its session, where it lies, what it holds, how its heading was filled, how it was reviewed
# and the frame parameters and kinematics version it was built under.
FRAME_COLUMN = "frame"
BLOCK_SCHEMA = pa.schema([(FRAME_COLUMN, pa.int32())]
                         + [(name, pa.string() if dtype == "U8" else pa.from_numpy_dtype(np.dtype(dtype))) for name, dtype in COLUMNS.items()])
BLOCKS_CSV_SCHEMA = pa.schema([
    ("block_id", pa.string()), ("session_id", pa.string()), ("subject_id", pa.string()), ("date", pa.string()),
    ("protocol", pa.string()), ("environment", pa.string()), ("epoch", pa.string()),
    ("frame_start", pa.int64()), ("frame_end", pa.int64()), ("n_frames", pa.int64()), ("duration_s", pa.float64()),
    ("n_runs", pa.int64()), ("n_clean_runs", pa.int64()), ("n_trips", pa.int64()), ("n_complete_trips", pa.int64()),
    ("heading_lost_s", pa.float64()), ("heading_filled_s", pa.float64()), ("heading_held_s", pa.float64()),
    ("status", pa.string()), ("reviewed_by", pa.string()),
    ("scale_px_per_m", pa.float64()), ("rotation_rad", pa.float64()), ("led_offset_rad", pa.float64()),
    ("kinematics_version", pa.int64()),
])


def block_table(columns):
    """
    The block's arrays, the lab frame and the schema's columns by name, as a table in BLOCK_SCHEMA's order and types.
    """
    return pa.Table.from_arrays([pa.array(columns[field.name], type=field.type) for field in BLOCK_SCHEMA], schema=BLOCK_SCHEMA)


def remove_folder(path):
    """
    Remove the folder with everything in it when it exists.
    """
    if Path(path).is_dir():
        shutil.rmtree(path)


def write_block(table, path):
    """
    Write a block table as parquet, creating the parent folders.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def write_csv(rows, path):
    """
    Write the blocks csv rows, dicts keyed as BLOCKS_CSV_SCHEMA names them, the header alone when there are none, creating the parent folders.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pacsv.write_csv(pa.Table.from_pylist(rows, schema=BLOCKS_CSV_SCHEMA), path)


def write_json(obj, path):
    """
    Write obj as sorted, indented json with a trailing newline, creating the parent folders.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
