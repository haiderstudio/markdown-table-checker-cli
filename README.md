# markdown-table-checker-cli

Check Markdown tables are well formed, fail CI on a bad table.

[![CI](https://github.com/haiderstudio/markdown-table-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/markdown-table-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`markdown_table_checker` reads each Markdown file,
finds its tables, and checks they are well formed:

- A Markdown table with a ragged row — one cell too
  few, one too many — renders broken on GitHub. The
  cells shift into the wrong columns and nobody notices
  until a reader complains. This tool reports every bad
  row with its file and line number, and exits 1 when any
  problem is found — so it can fail a CI run. A clean file
  exits 0.
- Every data row must have the same number of cells as
  the header. A row with more or fewer cells is one
  problem, reported with its line number.
- The separator row must be a valid `|---|---|` line:
  pipe-separated cells made of dashes only, with an
  optional colon on either side for alignment
  (`:---`, `---:`, `:---:`). A cell with anything else is
  one problem, and a separator with a different cell count
  than the header is one problem.
- Escaped pipes (`\|`) inside a cell do not split it, so
  a cell that really contains a pipe is counted right.
- Tables inside fenced code blocks are skipped — they are
  examples, not tables.
- A header with no separator-looking line after it is not
  a table at all: plain lines with pipes are common in
  prose, and guessing would flag ordinary writing. Only a
  line with pipes AND dashes after a header starts a
  table, and then the separator is checked strictly.
- Files come from the command line (one or more), or from
  a folder walk: every `.md` and `.markdown` file under a
  folder, recursively by default (`--no-recursive` stops
  at the top level). `.git` folders are never walked, and
  directory links are never followed, so a link cycle
  cannot loop the check.
- `--exclude PATTERN` skips files by glob, for example
  `--exclude 'sub/nested.md'`. It can be repeated. A file
  passed directly on the command line is always checked,
  even if it matches an exclude pattern and even if it
  has no Markdown extension.
- `--stdin` reads one Markdown file from standard input.
- `--json` prints the result as machine-readable JSON (the
  summary goes to standard error, so standard output stays
  clean JSON).
- It is report-only and runs fully offline: it never
  rewrites a file, sends nothing anywhere, and needs no
  API key. Python standard library only.

## What it does NOT do

- It does not rewrite or tidy a Markdown table. A bad row
  is reported; fixing it is your job.
- It does not check links, headings, or anything else in
  a Markdown file. This tool's one job is table shape.
- It does not convert tables between formats — that is
  repo #5's `markdown-table-converter-cli`. This tool
  validates tables — a different job on the same tables.
- It does not fetch anything from a live site. Every input
  is a local file or standard input.

## Who it is for

Every docs writer: a blogger adding a CI step that fails
the build when a table row is ragged, or anyone tidying a
README before a release. A broken table is invisible in
the file itself — this catches it before a reader sees it.

## How this differs from similar tools

The exact name `markdown-table-checker-cli` matches 0
repositories on GitHub (checked Nov 10, 2026), and the
wider field is nearly empty: `markdown table checker`
matches 4 repositories. The top one is
neuvecom/markdown-format-checker, 0 stars — a VS Code
extension that warns about tables placed right after
headings (a different job); the rest are noise (a
voice-AI audit tool, a Medium editor, a Claude Code
plugin). No rival checks table shape. This tool does one
job: a Python standard-library-only CLI that checks
Markdown tables are well formed, reports each bad row
with file and line, and exits 1 for CI — no install
beyond Python, no website, no network.

## Install

Python standard library only — no packages to download. You need
Python 3.8 or newer. Clone the repo and run it in place:

```
git clone https://github.com/haiderstudio/markdown-table-checker-cli.git
cd markdown-table-checker-cli
python3 src/markdown_table_checker.py examples/good.md
```

```
examples/good.md: tables OK
OK — 1 file(s) checked, all tables are well formed.
```

## Usage

Check one clean file:

```
python3 src/markdown_table_checker.py examples/good.md
```

```
examples/good.md: tables OK
OK — 1 file(s) checked, all tables are well formed.
```

Check a file with broken tables — a ragged row, a bad
separator cell, and a short separator:

```
python3 src/markdown_table_checker.py examples/bad.md
```

```
FAIL examples/bad.md:6: row has 3 cell(s), header has 2
FAIL examples/bad.md:9: invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)
FAIL examples/bad.md:13: separator row has 2 cell(s), header has 3
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

A broken table inside a code block is skipped:

```
python3 src/markdown_table_checker.py examples/fenced.md
```

```
examples/fenced.md: tables OK
OK — 1 file(s) checked, all tables are well formed.
```

Check a whole folder:

```
python3 src/markdown_table_checker.py examples/
```

```
FAIL examples/bad.md:6: row has 3 cell(s), header has 2
FAIL examples/bad.md:9: invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)
FAIL examples/bad.md:13: separator row has 2 cell(s), header has 3
examples/fenced.md: tables OK
examples/good.md: tables OK
examples/sample-output.md: tables OK
FAIL examples/sub/nested.md:5: row has 3 cell(s), header has 2
Checked 5 file(s), 4 problem(s) in 2 file(s).
```

Skip one file with `--exclude`:

```
python3 src/markdown_table_checker.py --exclude 'sub/nested.md' examples/
```

```
FAIL examples/bad.md:6: row has 3 cell(s), header has 2
FAIL examples/bad.md:9: invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)
FAIL examples/bad.md:13: separator row has 2 cell(s), header has 3
examples/fenced.md: tables OK
examples/good.md: tables OK
examples/sample-output.md: tables OK
Checked 4 file(s), 3 problem(s) in 1 file(s).
```

Check one file from standard input:

```
python3 src/markdown_table_checker.py --stdin < examples/bad.md
```

```
FAIL <stdin>:6: row has 3 cell(s), header has 2
FAIL <stdin>:9: invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)
FAIL <stdin>:13: separator row has 2 cell(s), header has 3
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

Machine-readable output with `--json` (the summary goes to
standard error, so standard output stays clean JSON):

```
python3 src/markdown_table_checker.py --json examples/bad.md
```

```
{
  "files": [
    {
      "file": "examples/bad.md",
      "problems": [
        {
          "line": 6,
          "reason": "row has 3 cell(s), header has 2"
        },
        {
          "line": 9,
          "reason": "invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)"
        },
        {
          "line": 13,
          "reason": "separator row has 2 cell(s), header has 3"
        }
      ]
    }
  ],
  "summary": {
    "checked": 1,
    "files_with_problems": 1,
    "problems": 3,
    "skipped": 0
  }
}
```

Exit codes: 0 when every table is well formed, 1 when
any bad row is found, 2 for a usage problem (no Markdown
files given, a bad flag, or a missing file or folder).

## Examples

### 1. A file with three broken tables

`examples/bad.md` holds a ragged row (line 6: 3 cells
against a 2-cell header), a separator with a text cell
(line 9: `x` is not dashes), and a separator with fewer
cells than its header (line 13: 2 cells against 3):

```
python3 src/markdown_table_checker.py examples/bad.md
```

```
FAIL examples/bad.md:6: row has 3 cell(s), header has 2
FAIL examples/bad.md:9: invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)
FAIL examples/bad.md:13: separator row has 2 cell(s), header has 3
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

### 2. A broken table inside a code block is not a table

`examples/fenced.md` has a ragged table inside a fenced
code block — it is an example, so the tool skips it and
passes the file:

```
python3 src/markdown_table_checker.py examples/fenced.md
```

```
examples/fenced.md: tables OK
OK — 1 file(s) checked, all tables are well formed.
```

### 3. The bundled examples, all at once

```
sh examples/run-example.sh
```

The script checks one clean file (pass), then the file
with broken tables (fail, on purpose), then the fenced
example (pass — the broken table inside the code block
is skipped), then the whole `examples/` folder (fail, on
purpose — it picks up the three problems in `bad.md`
plus the one in `examples/sub/nested.md`). Its full
output is in `examples/sample-output.md`, ending with
`Checked 5 file(s), 4 problem(s) in 2 file(s).` The
failing runs exit 1, which is the expected result — the
script ends with exit 0 so it can be run as a demo.

## How it is tested

Tests, standard library `unittest` only, no packages to install:

```
python3 tests/test_markdown_table_checker.py
```

The tests cover: cell splitting (outer pipes, no outer
pipes, one column, escaped pipes, stripped cells, empty
cells), separator rows (plain dashes, alignment colons,
text cells, dashes with spaces, colon-only cells),
table checks (clean table, ragged row, short row, bad
separator cell, separator with the wrong cell count, a
table without outer pipes, a header with no separator
not counting as a table, a table ending at a blank line
or a line with no pipe, fenced code blocks with backticks
and tildes skipped, escaped pipes in cells, two tables
both checked, empty input, no tables), file checks
(clean file, bad file, missing file, non-UTF-8 file,
input file left unchanged), folder walking (a direct file
always checked, only Markdown files inside a folder,
`.git` never walked, `--no-recursive`, `--exclude`, a
direct file checked even if excluded, missing path), the
CLI (exit 0/1/2, each flag, `--stdin` good and bad,
`--json` output, `--version`, bad flags, missing paths,
empty folders), the bundled examples (sample output
compared byte-for-byte against a fresh run, and the
README-quoted outputs checked against it), and hygiene
checks (no placeholder text, no absolute paths, stdlib
imports only, `.env` first in `.gitignore`, CI file runs
the test file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The idea
of checking Markdown tables is not new — the similar
tools named above (the 0-star VS Code extension that
warns about tables after headings) are listed in "How
this differs" — but every line of code here is original,
and the tool builds on nothing but Python's standard
library.
