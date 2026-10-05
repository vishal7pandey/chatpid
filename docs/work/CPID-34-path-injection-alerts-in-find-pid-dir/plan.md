# CPID-34 — Plan: contain the path before touching the filesystem in _find_pid_dir

Status: plan-approved · Risk: high · Jira: CPID-34 (also CPID-35)
Created: 2026-10-05 · Slug: path-injection-alerts-in-find-pid-dir · Spec: spec.md

## Summary

Rewrite `_find_pid_dir` so the candidate path is resolved with `os.path.realpath` and checked with
`startswith(base + os.sep)` inline, before `os.path.isfile` is called. This is the pattern CodeQL recognises as a
path sanitizer, and it is also the safer order. Test first.

**Size:** S

## Current state

`chatpid/api.py::_find_pid_dir` (about line 382) loops over `PID_SEARCH_DIRS`, builds `Path(d).resolve()` and
`(base / filename).resolve()`, calls `candidate.is_file()` and then `candidate.is_relative_to(base)`. Its only caller is
`get_pid_svg`, which already rejects bad names with `_is_plain_xml_name()`. Tests: `uv run python -m pytest -q`
(237 passing baseline); lint `uv run python -m ruff check .` (CI enforces both).

## Approach

```python
base = os.path.realpath(d)
candidate = os.path.realpath(os.path.join(base, filename))
if not candidate.startswith(base + os.sep):
    continue
if os.path.isfile(candidate):
    return d
```

Needs `import os`. Symlinks that point outside still fail the prefix check because `realpath` follows them.

**Alternatives rejected**
- Keep `pathlib` and move `is_relative_to` before `is_file`: safer order, but CodeQL does not model `Path.is_relative_to` as a
  sanitizer, so the alert would likely stay open.
- Dismiss the alerts: forbidden by the findings policy.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing regression tests (red) | tests/test_api_pid_svg.py | AC1, AC2 | 3 failed on old code |
| T2 | Contain-then-probe in `_find_pid_dir` | chatpid/api.py | AC1, AC2 | tests/test_api_pid_svg.py all pass |
| T3 | Full suite, ruff, verify.py, CI | whole repo | AC2 | 237 + new passing; CI green |
| T4 | After merge: CodeQL run on main, re-query alerts 1 and 2 | none | AC3 | `gh api .../code-scanning/alerts/1` and `/2` state `fixed` |

## Data, API and migration impact

None. Same endpoint, same responses.

## Security and failure modes

This is the fix. Fails closed: an escaping or non-existent name returns None and the endpoint answers 400/404 as before.

## Rollout and rollback

Merge, wait for the CodeQL run on main, re-query. Revert the commit to undo.

## Risks and open points

- CodeQL may not close the alerts if it does not recognise the sanitizer in this shape. Signal: alert still `open` after the
  main scan; then improve the fix (never dismiss).
- Symlink test cannot run on this Windows machine; CI (Linux) covers it.
