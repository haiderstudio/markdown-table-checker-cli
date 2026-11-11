#!/usr/bin/env python3
"""Tests for markdown-table-checker-cli.

Standard library unittest only. Run from the repo root:

    python3 tests/test_markdown_table_checker.py

or:

    python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "markdown_table_checker.py"
sys.path.insert(0, str(ROOT / "src"))

import markdown_table_checker as tool  # noqa: E402


def run_cli(*args, stdin_text=None):
    """Run the tool as a subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(SRC), *args],
        input=stdin_text,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return result.returncode, result.stdout, result.stderr


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class TestSplitCells(unittest.TestCase):
    def test_outer_pipes(self):
        self.assertEqual(
            tool.split_cells("| a | b |"), ["a", "b"]
        )

    def test_no_outer_pipes(self):
        self.assertEqual(tool.split_cells("a | b"), ["a", "b"])

    def test_single_column(self):
        self.assertEqual(tool.split_cells("| only |"), ["only"])

    def test_escaped_pipe_stays_in_cell(self):
        self.assertEqual(
            tool.split_cells("| a \\| b | c |"), ["a | b", "c"]
        )

    def test_cells_stripped(self):
        self.assertEqual(
            tool.split_cells("|  a  |   b   |"), ["a", "b"]
        )

    def test_empty_cells_kept(self):
        self.assertEqual(
            tool.split_cells("| a | | c |"), ["a", "", "c"]
        )


class TestSeparatorRow(unittest.TestCase):
    def test_plain_dashes(self):
        self.assertTrue(tool.is_separator_row("| --- | --- |"))

    def test_alignment_colons(self):
        self.assertTrue(tool.is_separator_row("| :--- | ---: | :---: |"))

    def test_no_dashes_not_a_separator(self):
        self.assertFalse(tool.is_separator_row("| a | b |"))

    def test_no_pipe_not_a_separator(self):
        self.assertFalse(tool.is_separator_row("--- ---"))

    def test_valid_separator_no_problems(self):
        self.assertEqual(
            tool.check_separator_row("| --- | :---: | ---: |"), []
        )

    def test_single_dash_valid(self):
        self.assertEqual(tool.check_separator_row("| - |"), [])

    def test_text_cell_is_a_problem(self):
        problems = tool.check_separator_row("| --- | x |")
        self.assertEqual(len(problems), 1)
        self.assertIn("'x'", problems[0])

    def test_dashes_with_spaces_invalid(self):
        problems = tool.check_separator_row("| -- -- |")
        self.assertEqual(len(problems), 1)

    def test_colon_only_invalid(self):
        problems = tool.check_separator_row("| : |")
        self.assertEqual(len(problems), 1)


class TestCheckLines(unittest.TestCase):
    def test_clean_table(self):
        lines = ["| a | b |", "| --- | --- |", "| 1 | 2 |"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_ragged_row(self):
        lines = ["| a | b |", "| --- | --- |", "| 1 | 2 | 3 |"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 3)
        self.assertEqual(
            problems[0]["reason"], "row has 3 cell(s), header has 2"
        )

    def test_short_row(self):
        lines = ["| a | b | c |", "| --- | --- | --- |", "| 1 | 2 |"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(
            problems[0]["reason"], "row has 2 cell(s), header has 3"
        )

    def test_bad_separator_cell(self):
        lines = ["| a | b |", "| --- | x |", "| 1 | 2 |"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0]["line"], 2)
        self.assertIn("invalid separator cell 'x'", problems[0]["reason"])

    def test_separator_wrong_cell_count(self):
        lines = ["| a | b | c |", "| --- | --- |", "| 1 | 2 | 3 |"]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 1)
        self.assertEqual(
            problems[0]["reason"],
            "separator row has 2 cell(s), header has 3",
        )

    def test_table_without_outer_pipes(self):
        lines = ["a | b", "--- | ---", "1 | 2"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_header_without_separator_is_not_a_table(self):
        # Plain lines with pipes are common in prose; only a
        # separator-looking line after a header starts a table.
        lines = ["use a | b when you mean or", "| c | d |"]
        self.assertEqual(tool.check_lines(lines), [])

    def test_table_ends_at_blank_line(self):
        lines = [
            "| a | b |",
            "| --- | --- |",
            "| 1 | 2 |",
            "",
            "| 3 | 4 | 5 |",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_table_ends_at_line_without_pipe(self):
        lines = [
            "| a | b |",
            "| --- | --- |",
            "| 1 | 2 |",
            "plain text",
            "| 3 | 4 | 5 |",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_fenced_code_block_skipped(self):
        lines = [
            "```",
            "| a | b |",
            "| --- | --- |",
            "| 1 | 2 | 3 |",
            "```",
            "| a | b |",
            "| --- | --- |",
            "| 1 | 2 |",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_tilde_fence_skipped(self):
        lines = [
            "~~~",
            "| a | b |",
            "| --- | --- |",
            "| 1 | 2 | 3 |",
            "~~~",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_escaped_pipe_in_cell(self):
        lines = [
            "| item | note |",
            "| --- | --- |",
            "| pipe | a \\| b |",
        ]
        self.assertEqual(tool.check_lines(lines), [])

    def test_two_tables_both_checked(self):
        lines = [
            "| a | b |",
            "| --- | --- |",
            "| 1 | 2 | 3 |",
            "",
            "| c | d |",
            "| --- | --- |",
            "| 4 | 5 | 6 |",
        ]
        problems = tool.check_lines(lines)
        self.assertEqual(len(problems), 2)
        self.assertEqual([p["line"] for p in problems], [3, 7])

    def test_empty_input(self):
        self.assertEqual(tool.check_lines([]), [])

    def test_no_tables(self):
        self.assertEqual(
            tool.check_lines(["# Title", "", "Some text."]), []
        )


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(
                Path(tmp) / "doc.md",
                "| a | b |\n| --- | --- |\n| 1 | 2 |\n",
            )
            problems, skipped = tool.check_file(path)
            self.assertEqual(problems, [])
            self.assertFalse(skipped)

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(
                Path(tmp) / "doc.md",
                "| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n",
            )
            problems, _ = tool.check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0]["line"], 3)

    def test_missing_file_is_a_problem(self):
        problems, _ = tool.check_file(Path("/nonexistent/doc.md"))
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot read file", problems[0]["reason"])

    def test_non_utf8_file_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_bytes(b"\xff\xfe bad bytes\n")
            problems, _ = tool.check_file(path)
            self.assertEqual(len(problems), 1)
            self.assertIn("UTF-8", problems[0]["reason"])

    def test_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(
                Path(tmp) / "doc.md",
                "| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n",
            )
            before = path.read_bytes()
            tool.check_file(path)
            self.assertEqual(path.read_bytes(), before)


class TestGather(unittest.TestCase):
    def test_direct_file_always_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(
                Path(tmp) / "notes.txt",
                "| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n",
            )
            entries, checked, _ = tool.gather([str(path)], [], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)

    def test_folder_only_checks_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "| a |\n| --- |\n| 1 | 2 |\n")
            write(root / "b.markdown", "| a |\n| --- |\n| 1 | 2 |\n")
            write(root / "c.txt", "| a |\n| --- |\n| 1 | 2 |\n")
            entries, checked, _ = tool.gather([str(root)], [], True)
            self.assertEqual(len(checked), 2)
            self.assertEqual(len(entries), 2)

    def test_git_folder_never_walked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / ".git" / "a.md", "| a |\n| --- |\n| 1 | 2 |\n")
            write(root / "a.md", "| a |\n| --- |\n| 1 |\n")
            _entries, checked, _ = tool.gather([str(root)], [], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(checked[0]["file"], str(root / "a.md"))

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "| a |\n| --- |\n| 1 |\n")
            write(root / "sub" / "b.md", "| a |\n| --- |\n| 1 | 2 |\n")
            _entries, checked, _ = tool.gather([str(root)], [], False)
            self.assertEqual(len(checked), 1)

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "a.md", "| a |\n| --- |\n| 1 | 2 |\n")
            write(root / "sub" / "b.md", "| a |\n| --- |\n| 1 | 2 |\n")
            entries, checked, skipped = tool.gather(
                [str(root)], ["sub/b.md"], True
            )
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)
            self.assertEqual(len(skipped), 1)

    def test_direct_file_checked_even_if_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(
                Path(tmp) / "a.md",
                "| a |\n| --- |\n| 1 | 2 |\n",
            )
            entries, checked, _ = tool.gather([str(path)], ["a.md"], True)
            self.assertEqual(len(checked), 1)
            self.assertEqual(len(entries), 1)

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            tool.gather(["/nonexistent/path"], [], True)


class TestCLI(unittest.TestCase):
    def test_clean_file_exit_0(self):
        code, out, _err = run_cli("examples/good.md")
        self.assertEqual(code, 0)
        self.assertIn("examples/good.md: tables OK", out)
        self.assertIn("all tables are well formed", out)

    def test_bad_file_exit_1(self):
        code, out, _err = run_cli("examples/bad.md")
        self.assertEqual(code, 1)
        self.assertIn("FAIL examples/bad.md:6:", out)
        self.assertIn("FAIL examples/bad.md:9:", out)
        self.assertIn("FAIL examples/bad.md:13:", out)
        self.assertIn("Checked 1 file(s), 3 problem(s) in 1 file(s).", out)

    def test_fenced_file_exit_0(self):
        code, out, _err = run_cli("examples/fenced.md")
        self.assertEqual(code, 0)
        self.assertIn("tables OK", out)

    def test_folder_walk(self):
        code, out, _err = run_cli("examples/")
        self.assertEqual(code, 1)
        self.assertIn("Checked 5 file(s), 4 problem(s) in 2 file(s).", out)
        self.assertIn("FAIL examples/sub/nested.md:5:", out)

    def test_no_recursive_flag(self):
        code, out, _err = run_cli("--no-recursive", "examples/")
        self.assertEqual(code, 1)
        self.assertIn("Checked 4 file(s), 3 problem(s) in 1 file(s).", out)

    def test_stdin(self):
        code, out, _err = run_cli(
            "--stdin",
            stdin_text="| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n",
        )
        self.assertEqual(code, 1)
        self.assertIn("FAIL <stdin>:3:", out)

    def test_stdin_clean(self):
        code, out, _err = run_cli(
            "--stdin",
            stdin_text="| a | b |\n| --- | --- |\n| 1 | 2 |\n",
        )
        self.assertEqual(code, 0)
        self.assertIn("all tables are well formed", out)

    def test_json_output(self):
        code, out, err = run_cli("--json", "examples/bad.md")
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["summary"]["checked"], 1)
        self.assertEqual(data["summary"]["problems"], 3)
        self.assertEqual(data["summary"]["files_with_problems"], 1)
        self.assertEqual(len(data["files"][0]["problems"]), 3)
        self.assertEqual(data["files"][0]["problems"][0]["line"], 6)
        self.assertIn("Checked 1 file(s), 3 problem(s)", err)

    def test_json_clean(self):
        code, out, err = run_cli("--json", "examples/good.md")
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["summary"]["problems"], 0)
        self.assertIn("all tables are well formed", err)

    def test_version(self):
        code, out, _err = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "markdown-table-checker-cli 1.0.0")

    def test_missing_path_exit_2(self):
        code, _out, err = run_cli("/nonexistent/doc.md")
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_no_paths_exit_2(self):
        code, _out, err = run_cli()
        self.assertEqual(code, 2)
        self.assertIn("no Markdown files to check", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _out, err = run_cli(tmp)
            self.assertEqual(code, 2)
            self.assertIn("no Markdown files to check", err)

    def test_bad_flag_exit_2(self):
        code, _out, err = run_cli("--nope")
        self.assertEqual(code, 2)
        self.assertIn("unrecognized arguments", err)


class TestBundledExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)
        expected = (ROOT / "examples" / "sample-output.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(result.stdout, expected)

    def test_run_example_script_exits_zero(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        self.assertEqual(result.returncode, 0)

    def test_readme_quotes_real_output(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for line in [
            "examples/good.md: tables OK",
            "OK — 1 file(s) checked, all tables are well formed.",
            "FAIL examples/bad.md:6: row has 3 cell(s), header has 2",
            "FAIL examples/bad.md:9: invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)",
            "FAIL examples/bad.md:13: separator row has 2 cell(s), header has 3",
            "Checked 1 file(s), 3 problem(s) in 1 file(s).",
            "FAIL examples/sub/nested.md:5: row has 3 cell(s), header has 2",
            "Checked 5 file(s), 4 problem(s) in 2 file(s).",
        ]:
            self.assertIn(line, readme, f"README is missing real output: {line}")


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        # Hygiene scans exclude .git, __pycache__, and tests/ —
        # the test file itself names the banned words it scans
        # for, and its own path strings are not shipped content.
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = sorted(
                d
                for d in dirnames
                if d not in (".git", "__pycache__", "tests")
            )
            for name in filenames:
                yield Path(dirpath) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "Lorem", "FIXME", "XXX"]
        for path in self._repo_files():
            if path.suffix in (".pyc",):
                continue
            text = path.read_bytes().decode("utf-8", errors="ignore")
            for word in banned:
                self.assertNotIn(
                    word, text, f"{word} found in {path.relative_to(ROOT)}"
                )

    def test_no_absolute_local_paths(self):
        for path in self._repo_files():
            text = path.read_bytes().decode("utf-8", errors="ignore")
            self.assertNotIn(
                "/home/hatch", text, f"absolute path in {path.relative_to(ROOT)}"
            )

    def test_stdlib_imports_only(self):
        source = (ROOT / "src" / "markdown_table_checker.py").read_text(
            encoding="utf-8"
        )
        stdlib = {
            "argparse",
            "fnmatch",
            "json",
            "os",
            "re",
            "sys",
            "pathlib",
        }
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                names = stripped[7:].split(",")
                for name in names:
                    self.assertIn(
                        name.strip().split()[0], stdlib, f"non-stdlib import: {line}"
                    )
            elif stripped.startswith("from "):
                module = stripped[5:].split()[0]
                self.assertIn(
                    module.split(".")[0], stdlib, f"non-stdlib import: {line}"
                )

    def test_gitignore_first_line_is_env(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_file_runs_the_test_file(self):
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("tests/test_markdown_table_checker.py", ci)
        self.assertIn("setup-python", ci)


if __name__ == "__main__":
    unittest.main()
