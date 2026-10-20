"""
A yaml file read into a dict that answers the path a key holds, with no knowledge of which keys exist.
"""

import yaml

from .errors import Invalid
from .paths import resolved


class Config:
    """
    The yaml file at path, read at construction and again on reload.
    """

    def __init__(self, path):
        self.path = resolved(path)
        self.reload()

    def reload(self):
        """
        Read the file again, a file that is absent or holds no mapping holds no keys.
        """
        data = yaml.safe_load(self.path.read_text()) if self.path.is_file() else None
        self.values = data if isinstance(data, dict) else {}

    def value(self, key):
        """
        The resolved path the key holds, refused when the key is missing or empty.
        """
        if not self.values.get(key):
            raise Invalid(f"{key} is not set in {self.path}")
        return resolved(self.values[key])
