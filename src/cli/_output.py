"""
Output helpers shared by every command: tables, labeled lines, JSON, errors.
"""

import json
import sys


def table(rows: list[dict], columns: list[str]) -> str:
    """
    Fixed-width columns, header first, no trailing spaces.
    """
    cells = [[str(row.get(col, "")) for col in columns] for row in rows]
    widths = [max([len(col)] + [len(row[i]) for row in cells])
              for i, col in enumerate(columns)]

    def fmt(values):
        return "  ".join(v.ljust(w) for v, w in zip(values, widths)).rstrip()

    return "\n".join([fmt(columns)] + [fmt(row) for row in cells])


def lines(title: str, pairs: list[tuple[str, object]]) -> str:
    """
    A title line followed by aligned label and value lines.
    """
    width = max(len(label) for label, _ in pairs)
    return "\n".join([title] + [f"  {label.ljust(width)}  {value}"
                                for label, value in pairs])


def emit(data, text: str, *, as_json: bool) -> None:
    print(json.dumps(data, indent=2, default=str) if as_json else text)


def fail(message: str, code: int = 2) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


def not_implemented(args) -> int:
    print(f"{args.name}: not implemented; see docs/cli/spec.md", file=sys.stderr)
    return 3
