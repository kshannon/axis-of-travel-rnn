"""
Csv and parquet files in and out as plain Python and numpy.
"""

from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq


def read_csv(path, schema=None):
    """
    A csv file as a list of dicts, one per row, types inferred except for the columns the Arrow schema names, a blank as None unless the column holds other text.
    """
    return pacsv.read_csv(path, convert_options=pacsv.ConvertOptions(column_types=schema)).to_pylist()


def read_parquet(path):
    """
    A parquet file as a dict of column name to numpy array.
    """
    table = pq.read_table(path)
    return {name: table.column(name).to_numpy() for name in table.column_names}


def write_csv(rows, path, schema):
    """
    Write row dicts keyed as the Arrow schema names them, the header alone when there are none, creating the parent folders.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pacsv.write_csv(pa.Table.from_pylist(rows, schema=schema), path)


def write_parquet(arrays, path, schema):
    """
    Write a dict of equal length arrays as the Arrow schema's columns, in its order and types, creating the parent folders.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_arrays([pa.array(arrays[field.name], type=field.type) for field in schema], schema=schema), path)
