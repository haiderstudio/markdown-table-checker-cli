#!/usr/bin/env python3
"""Check Markdown tables are well formed, fail CI on a bad table.

Run: python3 src/markdown_table_checker.py examples/good.md
     python3 src/markdown_table_checker.py examples/
     python3 src/markdown_table_checker.py --json examples/bad.md

The problem is quiet: a Markdown table with a ragged
row — one cell too few, one too many — renders broken
on GitHub. The cells shift into the wrong columns and
nobody notices until a reader complains. This tool reads
each Markdown file, finds its tables, checks every data
row has the same number of cells as the header and that
the separator row is a valid |---|---| line, reports
every bad row with its file and line number, and exits 1
when any problem is found, so it can fail a CI run. A
clean file exits 0.

A table is a header row (a line with pipes), followed by
a separator row, followed by data rows. The separator
row is a line of pipe-separated cells made of dashes,
with an optional colon on either side for alignment —
"| --- | :---: | ---: |" is valid, "| --- | x |" is not.
A data row is any following line that contains a pipe;
the table ends at the first blank line or line with no
pipe. Escaped pipes ("\\|") inside a cell do not split
it. Tables inside fenced code blocks are skipped — they
are examples, not tables.

A header with no separator-looking line after it is not
a table at all: plain lines with pipes are common in
prose, and guessing would flag ordinary writing. Only a
line with pipes AND dashes after a header starts a
table, and then the separator is checked strictly.

It never rewrites a file. It is report-only and runs
fully offline: it sends nothing anywhere and needs no
API key.

Exit codes: 0 when every table is well formed, 1 when
any bad row is found, 2 for a usage or input problem (a
missing path, a bad flag, a bad --exclude value, or no
Markdown file to check).

Python standard library only.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

MARKDOWN_EXTENSIONS = {".md", ".markdown"}

_SEPARATOR_CELL = re.compile(r"^:?-+:?$")
_FENCE = re.compile(r"^\s*(```|~~~)")


def split_cells(line):
    """Return the cells of one table row line.

    The line is split on pipes that are not escaped with a
    backslash, so "\\|" stays inside a cell. A leading or
    trailing pipe marks the edge of the row, not a cell, so
    an empty first or last piece is dropped. Every cell is
    stripped of surrounding whitespace.
    """
    cells = []
    current = []
    escaped = False
    for char in line:
        if escaped:
            # An escaped pipe is a literal pipe inside the
            # cell; any other escaped character keeps its
            # backslash.
            if char == "|":
                current.append("|")
            else:
                current.append("\\")
                current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current))
            current = []
        else:
            current.append(char)
    cells.append("".join(current))
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [cell.strip() for cell in cells]


def is_separator_row(line):
    """Return True when a line looks like a separator attempt.

    A separator-looking line has at least one pipe and at
    least one dash. This is the loose test that decides
    whether a header starts a table at all — the strict
    check is check_separator_row.
    """
    return "|" in line and "-" in line


def check_separator_row(line):
    """Return the problems in one separator row, or [].

    A valid separator row is pipe-separated cells that are
    only dashes, with an optional colon on either side
    (":---", "---:", ":---:"). A cell with anything else
    is one problem.
    """
    cells = split_cells(line)
    if not cells:
        return ["separator row has no cells"]
    problems = []
    for cell in cells:
        if not _SEPARATOR_CELL.match(cell):
            problems.append(
                f"invalid separator cell '{cell}' "
                "(a separator cell is only dashes, "
                "with an optional : on either side)"
            )
    return problems


def check_table(header_cells, rows):
    """Return the problems in one table's data rows.

    header_cells is the list of header cells; rows is a
    list of (line_number, cells) for the data rows. Each
    problem is a dict with "line" and "reason".
    """
    expected = len(header_cells)
    problems = []
    for number, cells in rows:
        if len(cells) != expected:
            problems.append(
                {
                    "line": number,
                    "reason": (
                        f"row has {len(cells)} cell(s), "
                        f"header has {expected}"
                    ),
                }
            )
    return problems


def check_lines(lines):
    """Return the table problems in one file's lines.

    lines is a list of the file's lines in order. Each
    problem is a dict with "line" (the bad row's line
    number, starting at 1) and "reason". Tables inside
    fenced code blocks are skipped.
    """
    problems = []
    in_fence = False
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        if _FENCE.match(line):
            in_fence = not in_fence
            index += 1
            continue
        if in_fence:
            index += 1
            continue
        if "|" not in line or not line.strip():
            index += 1
            continue
        # A table starts at a header row whose next line
        # looks like a separator row.
        if index + 1 < total and is_separator_row(lines[index + 1]):
            header_cells = split_cells(line)
            separator_line = lines[index + 1]
            separator_cells = split_cells(separator_line)
            for reason in check_separator_row(separator_line):
                problems.append({"line": index + 2, "reason": reason})
            if len(separator_cells) != len(header_cells):
                problems.append(
                    {
                        "line": index + 2,
                        "reason": (
                            f"separator row has "
                            f"{len(separator_cells)} cell(s), "
                            f"header has {len(header_cells)}"
                        ),
                    }
                )
            rows = []
            index += 2
            while index < total:
                row_line = lines[index]
                if not row_line.strip() or "|" not in row_line:
                    break
                if _FENCE.match(row_line):
                    break
                rows.append((index + 1, split_cells(row_line)))
                index += 1
            problems.extend(check_table(header_cells, rows))
            continue
        index += 1
    return problems


def check_file(path):
    """Return (problems, skipped) for one Markdown file.

    skipped is always False — nothing is skipped, a file
    that cannot be read is a problem.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError:
        return (
            [{"line": 0, "reason": "not readable as UTF-8 text"}],
            False,
        )
    except OSError as exc:
        return (
            [{"line": 0, "reason": f"cannot read file: {exc.strerror}"}],
            False,
        )
    return check_lines(text.splitlines()), False


def _is_markdown(name):
    return Path(name).suffix.lower() in MARKDOWN_EXTENSIONS


def gather(paths, exclude, recursive):
    """Walk the given paths and return (entries, checked, skipped).

    entries is a list of (file, problem); checked is a list
    of one dict per file the tool tried, with file and
    problems; skipped is a list of files skipped by
    --exclude. A file passed on the command line is always
    checked, even if it matches --exclude and even if it
    has no Markdown extension. Inside a folder, only
    .md and .markdown files are checked.
    """
    entries = []
    checked = []
    skipped = []
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            raise FileNotFoundError(raw)
        if path.is_file():
            problems, _was_skipped = check_file(path)
            checked.append({"file": str(path), "problems": problems})
            for problem in problems:
                entries.append((str(path), problem))
            continue
        if recursive:
            for dirpath, dirnames, filenames in _walk(path):
                for name in filenames:
                    if not _is_markdown(name):
                        continue
                    candidate = Path(dirpath) / name
                    if _excluded(candidate, path, exclude):
                        skipped.append(str(candidate))
                        continue
                    problems, _was_skipped = check_file(candidate)
                    checked.append(
                        {"file": str(candidate), "problems": problems}
                    )
                    for problem in problems:
                        entries.append((str(candidate), problem))
        else:
            for candidate in sorted(path.iterdir()):
                if not candidate.is_file():
                    continue
                if not _is_markdown(candidate.name):
                    continue
                if _excluded(candidate, path, exclude):
                    skipped.append(str(candidate))
                    continue
                problems, _was_skipped = check_file(candidate)
                checked.append(
                    {"file": str(candidate), "problems": problems}
                )
                for problem in problems:
                    entries.append((str(candidate), problem))
    return entries, checked, skipped


def _walk(root):
    """os.walk that never enters .git and never follows links."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        yield dirpath, dirnames, sorted(filenames)


def _excluded(candidate, root, patterns):
    name = candidate.name
    try:
        rel = str(candidate.relative_to(root))
    except ValueError:
        rel = name
    return any(
        fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern)
        for pattern in patterns
    )


def _format_problem(location, problem):
    return f"FAIL {location}:{problem['line']}: {problem['reason']}"


def _summary_line(checked, problems):
    total = len(problems)
    bad_files = len({f for f, _p in problems})
    if total:
        return (
            f"Checked {len(checked)} file(s), {total} "
            f"problem(s) in {bad_files} file(s)."
        )
    return (
        f"OK — {len(checked)} file(s) checked, "
        f"all tables are well formed."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="markdown-table-checker-cli",
        description="Check Markdown tables are well formed.",
    )
    parser.add_argument(
        "paths", nargs="*", help="files or folders to check"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read one Markdown file from standard input",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="skip files matching this glob (repeatable)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="do not walk into subfolders",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the result as JSON (summary goes to stderr)",
    )
    parser.add_argument("--version", action="store_true", help="print the version")
    args = parser.parse_args(argv)

    if args.version:
        print(f"markdown-table-checker-cli {VERSION}")
        return 0

    entries = []
    checked = []
    skipped = []
    try:
        if args.paths:
            found, found_checked, found_skipped = gather(
                args.paths,
                args.exclude,
                not args.no_recursive,
            )
            entries.extend(found)
            checked.extend(found_checked)
            skipped.extend(found_skipped)
    except FileNotFoundError as exc:
        print(f"error: no such file or folder: {exc}", file=sys.stderr)
        return 2

    if args.stdin:
        text = sys.stdin.read()
        problems = check_lines(text.splitlines())
        checked.append({"file": "<stdin>", "problems": problems})
        for problem in problems:
            entries.append(("<stdin>", problem))

    if not checked:
        print("error: no Markdown files to check", file=sys.stderr)
        return 2

    problems = entries
    bad_files = len({f for f, _p in problems})
    total = len(problems)
    summary = _summary_line(checked, problems)

    if args.json:
        files = []
        for entry in checked:
            files.append(
                {
                    "file": entry["file"],
                    "problems": entry["problems"],
                }
            )
        result = {
            "files": files,
            "summary": {
                "checked": len(checked),
                "files_with_problems": bad_files,
                "problems": total,
                "skipped": len(skipped),
            },
        }
        print(json.dumps(result, indent=2))
        print(summary, file=sys.stderr)
        return 1 if problems else 0

    for entry in checked:
        if entry["problems"]:
            for problem in entry["problems"]:
                print(_format_problem(entry["file"], problem))
        else:
            print(f"{entry['file']}: tables OK")
    print(summary)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
