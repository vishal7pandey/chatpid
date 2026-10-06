# CPID-41 — Plan: contain the upload write at the point of use

Status: draft · Risk: high · Jira: CPID-41
Created: 2026-10-06 · Slug: sonar-s2083-on-ingest · Spec: spec.md

## Summary

Prove first (tests) that `POST /ingest` cannot be steered to a path by file name or content, then add the inline
`os.path.realpath` + `startswith(base + os.sep)` containment check immediately before `write_bytes` in `ingest_document`,
the same shape as `_find_pid_dir` (CPID-34). Then see what SonarCloud says on `main`.

**Size:** S

## Current state

`chatpid/api.py::ingest_document` (about line 335): validates the client name (`_is_plain_xml_name`), makes a
`tempfile.TemporaryDirectory()`, writes `await file.read()` to `Path(tmpdir) / UPLOAD_TMP_NAME` and calls
`load_dexpi_model(tmpdir, UPLOAD_TMP_NAME)`. Tests: `tests/test_api_ingest_filename.py` (CPID-20), `tests/test_api.py`. Commands:
`uv run python -m pytest -q` (241 passed, 3 skipped baseline), `uv run python -m ruff check .`, `uv run python -m ruff format --check .`.

## Approach

```python
tmp_base = os.path.realpath(tmpdir)
tmp_path = os.path.realpath(os.path.join(tmp_base, UPLOAD_TMP_NAME))
if not tmp_path.startswith(tmp_base + os.sep):
    raise HTTPException(status_code=500, detail="Upload could not be stored")
Path(tmp_path).write_bytes(content)
```

Fails closed with a generic body (no path in the response), logs the event.

**Alternatives rejected**
- Dismiss the issue straight away: forbidden by the findings policy without the owner's yes, and the unguarded sink is a
  cheap, real hardening.
- Read the upload into a different sink (`open().write`, `shutil.copyfileobj`): changes shape only to dodge a model, no
  safety gain; if the guard does not satisfy Sonar the finding is a content-taint false positive.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Tests: hostile names and contents, sink-target spy, contained-write test (red for the last) | tests/test_api_ingest_filename.py | AC1, AC2 | 3 contained-write cases fail on old code, the rest pass |
| T2 | Inline containment before `write_bytes` | chatpid/api.py | AC1, AC2 | tests/test_api_ingest_filename.py all pass |
| T3 | Full suite, ruff, verify.py, CI, merge | whole repo | AC2 | 262 passed, 3 skipped; CI green |
| T4 | After the push scan on main: re-query the Sonar issue; closed, or propose dismissal | none | AC3 | `api/issues/search?issues=AaESHd3k4FTZ_gsvTVdz` status |

## Data, API and migration impact

None. Same endpoint, same responses for valid input.

## Security and failure modes

This is the hardening. An escaping target returns 500 with a generic message and a log line; unreachable while the name is a constant.

## Rollout and rollback

Merge, wait for the SonarCloud scan on main, re-query. Revert the commit to undo.

## Risks and open points

- Sonar's flow is the upload content reaching `write_bytes`; the guard checks the path, so Sonar may keep reporting. Signal:
  issue still OPEN after the main scan. Then it is a false positive; propose the dismissal, do not dismiss.
