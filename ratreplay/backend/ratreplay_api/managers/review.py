"""
A session's review: the file saved for it, and the blocks a list of edits makes.
"""

from pathlib import Path

from ..engines import edits
from ..errors import Invalid
from ..stores import review as review_files
from ..stores import transformed

STILL_AUTO = "some blocks are still auto: confirm, edit or remove them before saving"


def get(source, session_id):
    """
    The session's review file, or None when it was not reviewed.
    """
    return review_files.read(Path(source["processed_path"]), session_id)


def context(source, session_id):
    """
    The session as the edits read it.
    """
    found = transformed.read_session(Path(source["path"]), session_id)
    return edits.context(found["frames"], found["session"], found["epochs"], found["runs"])


def preview(source, session_id, edit_list):
    """
    The blocks, cuts and flagged runs the edits make and the edits skipped as no longer applying, nothing written.
    """
    return edits.preview(context(source, session_id), edit_list)


def save(source, session_id, edit_list, notes):
    """
    Apply the edits to the automatic blocks and write the review whole, replacing the earlier one. Refused while a block is still auto. Returns the saved review, the file and whether it replaced one.
    """
    saved = edits.review_of(context(source, session_id), edit_list, notes,
                            transformed.manifest(Path(source["path"]))["run"]["timestamp"])
    if any(block["status"] == "auto" for block in saved["blocks"]):
        raise Invalid(STILL_AUTO)
    path, replaced = review_files.write(Path(source["processed_path"]), saved)
    return {"review": saved, "path": str(path), "overwrote": replaced}
