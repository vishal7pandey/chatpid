# CPID-13 — Path traversal in GET /pid/svg

Status: spec-approved · Risk: high · Jira: CPID-13

## Repro

Environment: main @ 3a825d7 (before the fix), Windows, Python 3.14, FastAPI TestClient.

1. A `.xml` file exists outside the allowed dirs, e.g. `<cwd>/outside/secret.xml`; cwd has `data/dexpi_real/` and `data/raw/`.
2. `GET /pid/svg?filename=../../outside/secret.xml` (or `..%2f..%2foutside%2fsecret.xml`, or an absolute path).

Automated repro (fails on the old code, passes after the fix):

- `.venv/Scripts/python.exe -m pytest tests/test_api_pid_svg.py -q`; before the fix 16 tests failed, e.g. `assert 400 <= 200` for `../../outside/secret.xml` (the endpoint handed the outside file to the loader and returned 200).

Reproducibility: always.

## Expected

Only bare `*.xml` names that really live inside `data/dexpi_real/` or `data/raw/` are rendered; everything else is a 4xx that does not reveal filesystem paths (ticket AC1, AC2).

## Actual

`chatpid/api.py` `get_pid_svg`: `candidate = os.path.join(d, filename)` then `os.path.isfile(candidate)`, and the same untrusted `filename` is passed to `ProteusSerializer().load(d, filename)`. `..`, separators and absolute paths (`os.path.join` discards the base when the second part is absolute) all escape the directory. The 404 and 500 bodies also embed the filename, the directory names and the raw exception text.

## Root cause (with evidence)

- Where: `chatpid/api.py`, `get_pid_svg()` (the `search_dirs` loop and the `load(found_path, filename)` call).
- Why it fails: user input is used as a path component with no allow-list, no `resolve()`, no containment check.
- Introduced by: always present (endpoint written that way; finding 3 in the snapshot AUDIT.md).
- Evidence: failing regression tests above; on the old code the fake loader received `../../outside/secret.xml`.

## Blast radius

- Only `.xml` files whose content the pyDEXPI loader can parse render as SVG, but the loader reads and parses any readable path; parse errors echoed `{exc}` in the 500 body (information leak, also fixed).
- Same class, not fixed here: `POST /ingest` builds `Path(tmpdir) / file.filename` from the upload filename (`chatpid/api.py`, `ingest_document`), so a crafted multipart filename can write outside the temp dir. Filed as a separate Jira bug.
- `GET /pid/files` only lists basenames of `*.xml` inside the two dirs; unaffected.
- Repo is public; no deployment known. Exposure since the endpoint was added.

## Regression criterion (AC1)

AC1: `tests/test_api_pid_svg.py` passes after the fix and fails on the current code. It covers `../x`, `..\x`, `../raw/../..`, absolute path, URL-encoded `..%2f`/`%2e%2e%2f`/`..%5c`/double-encoded, NUL, wrong extension, empty name and a symlink pointing outside (runs where symlinks can be created, i.e. Linux CI) all returning 4xx, and a valid name (`good.xml` with fakes, and the tracked `C03V04-VER.EX02.xml` unfaked) returning 200 `image/svg+xml`.

AC2: 4xx and 5xx bodies of `/pid/svg` contain no filesystem path, no directory name and no exception text (asserted for rejection, 404 and a forced render failure).

## Fix constraints

Minimal diff in `get_pid_svg`; same URL, parameter and success response; `/pid/files` and the frontend (`frontend/lib/api.ts` only builds the URL) unchanged; no new dependency.

## Risks

High because it is a security fix on a network-facing endpoint (security.md: human review before merge; delegated here). Could reject a legitimate file name containing `..` or `:`; the repo's files do not. Rollback: revert the commit.
