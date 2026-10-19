"""
Files an access writes whole: json in and out, the temporary name a file is written under before it is renamed into place, a name that can stand as a file stem, and the keys a dict must hold.
"""

import json
import re

from .errors import Invalid

JSON, PARQUET, TEMP = ".json", ".parquet", ".tmp"
SAFE_STEM = re.compile(r"\w[\w.-]*")


def columns_of(schema):
    """
    The Arrow schema's columns as the format lists them, name and type, every one required.
    """
    return [{"name": field.name, "type": str(field.type), "required": True} for field in schema]


def require(what, keys, found):
    """
    Invalid naming the keys the dict lacks, nothing when it has them all.
    """
    missing = [key for key in keys if key not in found]
    if missing:
        raise Invalid(f"{what} lacks {', '.join(missing)}")


def safe_stem(name):
    """
    The name when it can stand as a file name inside a folder of the root, else Invalid.
    """
    if not SAFE_STEM.fullmatch(str(name)):
        raise Invalid(f"{name} is not a safe file name")
    return name


def temp_of(path):
    """
    The temporary name a file is written under before it is renamed into place.
    """
    return path.with_name(path.name + TEMP)


def read_json(path):
    """
    The json file as data, none when it does not exist.
    """
    return json.loads(path.read_text()) if path.is_file() else None


def write_json(obj, path):
    """
    Write obj as sorted, indented json with a trailing newline, creating the parent folders.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
