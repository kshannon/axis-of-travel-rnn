"""
The commit the code is at, for the records a build leaves.
"""

import subprocess

UNKNOWN, DIRTY = "unknown", "+dirty"


def git(root, *arguments):
    """
    The output of a git command run in the folder.
    """
    return subprocess.run(["git", "-C", str(root), *arguments], capture_output=True, text=True, check=True).stdout.strip()


def git_commit(root):
    """
    The short commit of the repository at root with +dirty when a tracked file has uncommitted changes, unknown when git cannot say.
    """
    try:
        commit, changes = git(root, "rev-parse", "--short", "HEAD"), git(root, "status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.CalledProcessError):
        return UNKNOWN
    return commit + (DIRTY if changes else "")
