# CPID-13 — Plan: path containment for /pid/svg

Status: plan-approved · Risk: high · Jira: CPID-13
Created: 2026-10-05 · Slug: pid-svg-path-traversal · Spec: spec.md

## Summary

Validate the name, resolve the candidate path and require it to stay inside the allowed directory before
rendering; make error bodies generic. Test first with a failing regression suite.

**Size:** S

## Current state

`chatpid/api.py::get_pid_svg` joins the query value onto `data/dexpi_real` / `data/raw` (cwd-relative; the
compose file mounts `./data` at `/app/data`). `/pid/files` lists the same dirs. Run tests with
`.venv/Scripts/python.exe -m pytest -q`, lint with `python -m ruff check .` (CI enforces both, CPID-1).

## Approach

Add `PID_SEARCH_DIRS`, `_is_plain_xml_name()` (reject empty/non-`.xml`, `..`, `/`, `\`, `:`, NUL) and
`_find_pid_dir()` (`Path.resolve()` of base and candidate, `is_file()` and `is_relative_to(base)`, which also
rejects symlinks that point outside). 400 for a bad name, 404 for not found, both without paths; 500 body is a
fixed string.

**Alternatives rejected**
- `os.path.basename(filename)` silently rewriting input: hides abuse and changes meaning.
- Regex charset allow-list: could reject legitimate names that `/pid/files` lists.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing regression tests (red) | tests/test_api_pid_svg.py | AC1, AC2 | 16 failed on old code |
| T2 | Name validation + containment + generic errors | chatpid/api.py | AC1, AC2 | 18 passed, 1 skipped locally |
| T3 | Full suite, ruff, verify.py, CI incl. Linux symlink test | whole repo | AC1 | CI `test` green, symlink test not skipped on Linux |

## Data, API and migration impact

No schema change. `/pid/svg` now returns 400 for invalid names (was 404/200/500) and fixed error messages.

## Security and failure modes

This is the fix. Fails closed: any doubt returns 4xx. Rendering errors return a generic 500.

## Rollout and rollback

Merge; revert the commit to undo. No deploy performed by the agent.

## Risks and open points

- Symlink test cannot run on this Windows machine; CI (Linux) must show it executed.
