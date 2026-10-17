"""
The sources registry: ids, idempotent attach, detach.
"""

import pytest

from ratreplay_api import registry
from ratreplay_api.errors import NotFound


def test_attach_is_idempotent_whatever_the_spelling_of_the_path(tmp_path):
    file, folder = tmp_path / "sources.json", tmp_path / "data"
    folder.mkdir()
    first = registry.attach(file, "transformed", folder, tmp_path / "out")
    again = registry.attach(file, "transformed", f"{folder}/", tmp_path / "out")
    assert again == first
    assert registry.read_all(file) == [first]
    assert first["id"] == registry.source_id(folder.resolve())


def test_detach_forgets_the_entry_and_keeps_the_data(tmp_path):
    file, kept, gone = tmp_path / "sources.json", tmp_path / "kept", tmp_path / "gone"
    kept.mkdir()
    gone.mkdir()
    registry.attach(file, "processed", kept, kept)
    entry = registry.attach(file, "processed", gone, gone)
    registry.detach(file, entry["id"])
    assert [e["path"] for e in registry.read_all(file)] == [str(kept.resolve())]
    assert gone.is_dir()
    with pytest.raises(NotFound):
        registry.detach(file, entry["id"])
