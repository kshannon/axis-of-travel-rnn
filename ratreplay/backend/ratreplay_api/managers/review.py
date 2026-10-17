"""
A session's review: the file saved for it, and the blocks a list of edits makes.
"""

import getpass

from .. import clock
from ..engines import edits
from ..errors import Invalid
from ..stores import review as review_files
from ..stores import transformed

STILL_AUTO = "some blocks are still auto: confirm, edit or remove them before saving"


def get(sources, session_id):
    """
    The session's review file, or None when it was not reviewed.
    """
    return review_files.read(sources, session_id)


def context(sources, session_id):
    """
    The session as the edits read it.
    """
    found = transformed.read_session(sources, session_id)
    return edits.context(found["frames"], found["session"], found["epochs"], found["runs"])


def preview(sources, session_id, edit_list):
    """
    The blocks, cuts and flagged runs the edits make and the edits skipped as no longer applying, nothing written.
    """
    return edits.preview(context(sources, session_id), edit_list)


def save(sources, session_id, edit_list, notes):
    """
    Apply the edits to the automatic blocks and write the review whole, replacing the earlier one. Refused while a block is still auto. Returns the saved review, the file and whether it replaced one.
    """
    stamp = transformed.manifest(sources)["run"]["timestamp"]
    saved = edits.review_of(context(sources, session_id), edit_list, notes, stamp, getpass.getuser(), clock.iso_now())
    if any(block["status"] == "auto" for block in saved["blocks"]):
        raise Invalid(STILL_AUTO)
    path, replaced = review_files.write(sources, saved)
    return {"review": saved, "path": str(path), "overwrote": replaced}
