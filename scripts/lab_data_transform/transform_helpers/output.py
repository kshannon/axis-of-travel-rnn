"""
Write a table or object the converter hands over to its path under the output root.
"""

import json
from pathlib import Path

import pyarrow.csv as pacsv
import pyarrow.parquet as pq


def write_frames(table, path):
    """
    Write a frames table as Parquet, creating the parent folders.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def write_csv(table, path):
    """
    Write a table as CSV.
    """
    pacsv.write_csv(table, path)


def write_json(obj, path):
    """
    Write obj as sorted, indented json with a trailing newline, creating the parent folders.
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
