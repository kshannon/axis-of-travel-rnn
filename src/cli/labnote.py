"""
The labnote group: create a dated lab notebook entry from the template.
"""

from pathlib import Path

from proj_helpers.notebooks import new_labnote
from proj_helpers.paths import repo_root
from ._output import fail


def register(commands) -> None:
    p = commands.add_parser(
        "new", help="create a lab notebook entry from the template",
        description="Create a lab notebook entry: reads templates/labnotebook.md and "
                    "writes labnotebook/<date>.md, or labnotebook/<date>__<slug>.md "
                    "when words are given, with the date, timestamp and title filled in.")
    p.add_argument("slug", metavar="<slug words>", nargs="*",
                   help="optional words for the file name, slugified, e.g. axis analysis")
    p.add_argument("--dir", metavar="DIR", type=Path,
                   help="directory to write into (default: labnotebook/ in the checkout)")
    p.set_defaults(func=new)


def new(args) -> int:
    try:
        path = new_labnote(" ".join(args.slug), directory=args.dir)
    except (ValueError, FileExistsError) as e:
        return fail(str(e))
    root = repo_root()
    print(path.relative_to(root) if path.is_relative_to(root) else path)
    return 0
