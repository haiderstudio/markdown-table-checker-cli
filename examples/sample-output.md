== good.md: well-formed tables, passes ==
examples/good.md: tables OK
OK — 1 file(s) checked, all tables are well formed.

== bad.md: a ragged row, a bad separator, a short separator ==
FAIL examples/bad.md:6: row has 3 cell(s), header has 2
FAIL examples/bad.md:9: invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)
FAIL examples/bad.md:13: separator row has 2 cell(s), header has 3
Checked 1 file(s), 3 problem(s) in 1 file(s).

== fenced.md: a broken table inside a code block is skipped ==
examples/fenced.md: tables OK
OK — 1 file(s) checked, all tables are well formed.

== examples/: a folder walk, four problems ==
FAIL examples/bad.md:6: row has 3 cell(s), header has 2
FAIL examples/bad.md:9: invalid separator cell 'x' (a separator cell is only dashes, with an optional : on either side)
FAIL examples/bad.md:13: separator row has 2 cell(s), header has 3
examples/fenced.md: tables OK
examples/good.md: tables OK
examples/sample-output.md: tables OK
FAIL examples/sub/nested.md:5: row has 3 cell(s), header has 2
Checked 5 file(s), 4 problem(s) in 2 file(s).
