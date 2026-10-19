"""
The format of a built block, shared by the processed folder and the synthetic sets: the columns of a block parquet and of the blocks index.
"""

import pyarrow as pa

# A block parquet holds the lab frame number first, so a row maps back to the converter's frames, then one row per frame
# of the trajectory. The blocks csv holds one wide row per block: the block and its session, where it lies, what it holds,
# how its heading was filled, how it was reviewed and the frame parameters and kinematics version it was built under.
BLOCKS_CSV = "blocks.csv"
BLOCKS_DIR = "blocks"
BLOCK_SCHEMA = pa.schema([
    ("frame", pa.int32()), ("t", pa.float64()), ("x", pa.float64()), ("y", pa.float64()), ("heading", pa.float64()),
    ("speed", pa.float64()), ("turn_rate", pa.float64()), ("n_lights", pa.int8()), ("heading_filled", pa.bool_()),
    ("heading_held", pa.bool_()), ("filled_front", pa.bool_()), ("filled_back", pa.bool_()), ("phase", pa.string()),
    ("trip", pa.int32()), ("run", pa.int32()), ("path_id", pa.int16()), ("clean", pa.bool_()),
])
BLOCKS_CSV_SCHEMA = pa.schema([
    ("block_id", pa.string()), ("session_id", pa.string()), ("subject_id", pa.string()), ("date", pa.string()),
    ("protocol", pa.string()), ("environment", pa.string()), ("epoch", pa.string()), ("kind", pa.string()),
    ("frame_start", pa.int64()), ("frame_end", pa.int64()), ("n_frames", pa.int64()), ("duration_s", pa.float64()), ("rate_hz", pa.int64()),
    ("n_runs", pa.int64()), ("n_clean_runs", pa.int64()), ("n_trips", pa.int64()), ("n_complete_trips", pa.int64()),
    ("heading_lost_s", pa.float64()), ("heading_filled_s", pa.float64()), ("heading_held_s", pa.float64()),
    ("status", pa.string()), ("reviewed_by", pa.string()),
    ("scale_px_per_m", pa.float64()), ("rotation_rad", pa.float64()), ("led_offset_rad", pa.float64()),
    ("kinematics_version", pa.int64()),
])
