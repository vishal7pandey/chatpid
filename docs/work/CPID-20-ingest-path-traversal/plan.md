# CPID-20 — Plan: stop the upload filename deciding the write path

Status: plan-approved · Risk: high · Jira: CPID-20
Created: 2026-10-05 · Slug: ingest-path-traversal · Spec: spec.md

## Summary

Validate the client filename with the CPID-13 helper, store the upload under a fixed name in the temp dir, make the parse-error body generic. Test first.

**Size:** S

## Current state

`ingest_document` in `chatpid/api.py` joins `file.filename` onto a `TemporaryDirectory`. `_is_plain_xml_name` already exists (CPID-13). Tests: `.venv/Scripts/python.exe -m pytest -q`; lint `python -m ruff check .` and `ruff format --check .`.

## Approach

1. After the existing `.xml` check, reject names failing `_is_plain_xml_name` with 400 `Invalid upload file name`.
2. Write to `UPLOAD_TMP_NAME = "upload.xml"` and pass that to `load_dexpi_model`.
3. Parse failure: 400 `Failed to parse DEXPI file` without exception text (`from None`).

**Alternatives rejected**
- `Path(file.filename).name`: silently rewrites hostile input and behaves differently per OS.
- Validate only, keep the client name as the temp file name: Windows reserved names (`CON.xml`) and long names still misbehave; a fixed name removes the class.

## Tasks

| # | Task | Files | Serves | Verify by |
|---|------|-------|--------|-----------|
| T1 | Failing regression tests (red) | tests/test_api_ingest_filename.py | AC1, AC2 | 12 failed on old code |
| T2 | Validation, fixed temp name, generic error | chatpid/api.py, tests/test_api.py (loader-name assertion) | AC1, AC2 | new file green, full suite green |
| T3 | Same-class grep, file follow-up tickets | repo | AC1 | grep result in spec Blast radius |

## Data, API and migration impact

No schema change. `/ingest` now answers 400 for names with separators, `..`, `:` or NUL, and a fixed parse-error message.

## Security and failure modes

This is the fix; it fails closed. Nothing about the client filename reaches the file system.

## Rollout and rollback

Merge; revert the commit to undo. No deploy by the agent.

## Risks and open points

None open.
