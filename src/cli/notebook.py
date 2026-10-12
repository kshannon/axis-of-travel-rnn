"""
The notebook group: create a working notebook from the template.
"""

from pathlib import Path

from proj_helpers.notebooks import new_notebook
from ._output import fail


def register(commands) -> None:
    p = commands.add_parser(
        "new", help="create a notebook from the template",
        description="Create a Jupyter notebook from the template: reads "
                    "templates/notebook.ipynb and writes "
                    "src/notebooks/<date>_<name>.ipynb with the date, title, name "
                    "and author filled in.")
    p.add_argument("name", metavar="<name>", nargs="+",
                   help="notebook name, slugified, e.g. matlab axis analysis")
    p.add_argument("--title", metavar="TEXT",
                   help="header title (default: the name with spaces)")
    p.add_argument("--author", metavar="TEXT",
                   help="header author (default: git's user.name)")
    p.add_argument("--dir", metavar="DIR", type=Path,
                   help="directory to write into (default: src/notebooks/ in the checkout)")
    p.set_defaults(func=new)


def new(args) -> int:
    try:
        path = new_notebook(" ".join(args.name), title=args.title,
                            author=args.author, directory=args.dir)
    except (ValueError, FileExistsError) as e:
        return fail(str(e))
    print(path)
    return 0
