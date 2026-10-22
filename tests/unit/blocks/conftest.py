"""
The synthetic transformed folder under tmp_path, never a real one.
"""

import pytest

from .fixtures import write_transformed


@pytest.fixture
def transformed(tmp_path):
    """
    A synthetic transformed folder.
    """
    root = tmp_path / "transformed"
    write_transformed(root)
    return root
