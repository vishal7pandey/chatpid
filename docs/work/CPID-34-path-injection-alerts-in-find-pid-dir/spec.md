# CPID-34 — Path injection alerts in _find_pid_dir: CodeQL py/path-injection at api.py:390-391 (CPID-34, CPID-35)

Status: spec-approved · Risk: high · Jira: CPID-34 (also covers CPID-35)

## Repro

Environment: main @ 527faa2 (`chatpid/api.py` after CPID-13 / PR 7), Windows, Python 3.14, pytest, plus the CodeQL default-setup scan on `main`.

Scanner findings (code scanning, rule `py/path-injection`, "Uncontrolled data used in path expression"):

- alert 1 (CPID-34): `chatpid/api.py:390`, `candidate = (base / filename).resolve()`.
- alert 2 (CPID-35): `chatpid/api.py:391`, `candidate.is_file()`.

Both are in `_find_pid_dir(filename)`, called from `GET /pid/svg` with the query value.

Automated repro (fails on the current code, passes after the fix):

- `uv run python -m pytest tests/test_api_pid_svg.py -q`; before the fix 3 tests fail:
  `test_find_pid_dir_never_touches_files_outside_the_base[...]` with `AssertionError: probed outside the base: <tmp>\data`
  (the helper stats a path outside the allowed directory before it checks containment).

Reproducibility: always (test); the alerts are open on `main`.

## Expected

An escaping name (`..`, `../..`, anything whose resolved path leaves `data/dexpi_real` or `data/raw`) is rejected
before the filesystem is probed, the endpoint answers with its normal 4xx (400 for a bad name, 404 for not found),
and legitimate names keep being served. The containment check is written in the form CodeQL recognises as a
path sanitizer, so the two alerts close.

## Actual

`_find_pid_dir` joins the user-controlled `filename` onto the base, resolves it, calls `is_file()` on the result and
only then checks `is_relative_to(base)`. The user-controlled path is therefore used in a filesystem call (a stat,
an existence oracle) before it is known to be inside the base. CodeQL tracks the taint to `resolve()` and `is_file()`
and does not model the later `Path.is_relative_to` guard as a sanitizer for them.

## Root cause (with evidence)

- Where: `chatpid/api.py:390-391` in `_find_pid_dir`.
- Why it fails: the check comes after the use. The endpoint's `_is_plain_xml_name()` already rejects separators,
  `..`, `:`, NUL, so the endpoint is not exploitable to read files today (CPID-13 fixed that); the defect left is
  defence in depth (the helper is not safe on its own) and the scanner finding.
- Introduced by: CPID-13 (PR 7), the containment check was added after `is_file()`.
- Evidence: the 3 failing tests above; `gh api repos/vishal7pandey/chatpid/code-scanning/alerts/1` and `/2`, both `open`.

## Blast radius

- Only `_find_pid_dir` (one caller: `get_pid_svg`). `/pid/files` lists basenames only; `/ingest` was fixed in CPID-20.
- No file content can be read through the current flow (name validation rejects traversal first), so the real
  exposure is low; the alerts are about the helper's own guarantees.
- Other `py/path-injection` alerts: none open besides these two.

## Regression criterion (AC1)

AC1: `tests/test_api_pid_svg.py::test_find_pid_dir_never_touches_files_outside_the_base` (3 cases) passes after the
fix and fails on the current code: an escaping name makes no filesystem probe outside the allowed directories and
`_find_pid_dir` returns None.

AC2: legitimate names keep working: `tests/test_api_pid_svg.py::test_find_pid_dir_still_finds_legitimate_files`,
`test_valid_file_name_is_served`, `test_real_reference_pid_renders`, the symlink-pointing-outside test (on Linux CI)
and the 400/404 behaviour of CPID-13 stay green; backend suite stays at 237 + new tests passing.

AC3 (closure, not code): code-scanning alerts 1 and 2 re-queried after the CodeQL run on `main` show `state: fixed`.
Until then CPID-34 and CPID-35 stay open.

## Fix constraints

Minimal diff in `_find_pid_dir` only: resolve with `os.path.realpath`, require `startswith(base + os.sep)` inline,
before `os.path.isfile`. Same signature and return value, no new dependency, no alert dismissal.

## Risks

High (security finding on a network-facing helper; rule from the findings policy). Behaviour is unchanged for valid
input; symlinks pointing outside stay rejected. If CodeQL still reports after the fix, improve the sanitizer; do not dismiss.
Rollback: revert the commit.
