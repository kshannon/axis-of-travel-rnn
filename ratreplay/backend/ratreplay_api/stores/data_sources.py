"""
Where the data is: the two folders the config file names.
"""

from proj_helpers import paths

from ..utilities.config import Config
from ..utilities.errors import Invalid, NotFound

# The config key of each folder, which the processor reads too.
KEYS = {"transformed": "TRANSFORMED_LAB_DATA", "processed": "PROCESSED_LAB_DATA"}


class DataSources:
    """
    The one place that knows how the folders are chosen: the config file at config_path, read with the config utility.
    """

    def __init__(self, config_path=None):
        self.config = Config(config_path or paths.repo_root() / paths.LOCAL_CONFIG)
        self.config_path = self.config.path

    def reload(self):
        """
        Read the config file again.
        """
        self.config.reload()

    def root(self, kind):
        """
        The folder the config names for the kind, resolved as the processor resolves it, none when the key is not set.
        """
        try:
            return self.config.value(KEYS[kind])
        except Invalid:
            return None

    def not_set(self, kind):
        """
        The problem of a config file without the kind's key.
        """
        return f"{KEYS[kind]} is not set in {self.config_path}"

    def not_there(self, kind):
        """
        The problem of a folder the config names that is not on disk.
        """
        return f"{KEYS[kind]} {self.root(kind)} does not exist"

    def required(self, kind):
        """
        The folder the config names for the kind, refused when the key is not set.
        """
        return self.config.value(KEYS[kind])

    def transformed_root(self):
        """
        The transformed folder the sessions are read from, refused when the key is not set or the folder is not there.
        """
        root = self.required("transformed")
        if not root.is_dir():
            raise NotFound(self.not_there("transformed"))
        return root

    def processed_root(self):
        """
        The processed folder that holds the reviews and the blocks, refused when the key is not set.
        """
        return self.required("processed")
