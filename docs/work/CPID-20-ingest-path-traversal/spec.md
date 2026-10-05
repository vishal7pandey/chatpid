# CPID-20 — Path traversal in POST /ingest

Status: spec-approved · Risk: high · Jira: CPID-20

## Repro

Environment: main @ 941e65e (before the fix), Windows, Python 3.14, FastAPI TestClient, DEXPI loader and Neo4j loader replaced by fakes, `tempfile.tempdir` moved under pytest's `tmp_path` so an escaping write is visible.

1. `POST /ingest` with a multipart file named `../../x.xml` (content `PWNED`).
2. `POST /ingest` with a file named `C:/…/outside/evil.xml` (forward-slash absolute path; python-multipart already reduces a backslash `C:\…` name to its basename, forward slashes reach the endpoint unchanged).

Automated repro (fails on the old code, passes after the fix):

- `.venv/Scripts/python.exe -m pytest tests/test_api_ingest_filename.py -q`; before the fix 12 tests failed, e.g. `assert 400 <= 200` for `../x.xml` and `sub/x.xml` (the endpoint answered 200 and wrote the file), and `'/secret/place' is contained here` for the parse-error body.

Reproducibility: always.

## Expected

The client-supplied filename never decides where bytes are written. Names that are not a bare `*.xml` are 4xx; error bodies carry no filesystem path or parser text (ticket AC1, AC2).

## Actual

`chatpid/api.py` `ingest_document()`: `tmp_path = Path(tmpdir) / file.filename; tmp_path.write_bytes(content)`. The only check was `file.filename.endswith(".xml")`, so `../../x.xml`, `sub/x.xml` or an absolute path wrote attacker-controlled bytes outside the temp dir (an absolute path discards the base). `load_dexpi_model(tmpdir, file.filename)` used the same name. The 400 on a parse error echoed `{exc}` (parser text, may contain paths).

## Root cause (with evidence)

- Where: `chatpid/api.py`, `ingest_document()` (the `Path(tmpdir) / file.filename` line and the `except Exception as exc` body).
- Why it fails: untrusted multipart filename used as a path component with no allow-list or containment; same class as CPID-13.
- Introduced by: always present.
- Evidence: the failing regression tests above.

## Blast radius

- Arbitrary `.xml`-named file write with attacker-controlled content to any location the API process can write (no auth on the endpoint; repo is public; no deployment known).
- Same-class grep after the fix (`write_bytes`, `write_text`, `open(`, `Path(` / `os.path.join` fed by a request value) over `chatpid/` and `scripts/`: the only request-derived path uses were `/pid/svg` (CPID-13, fixed) and this one. Scripts write to fixed result dirs or CLI-argument paths chosen by the local operator. `level`, `document_id` and `tag` reach Cypher only as parameters; label and relationship names from uploaded XML go through `_safe_label` / `_safe_rel_type`. No new hit of this class.
- Adjacent, not fixed here (filed as CPID-22): the upload has no size limit and the endpoint has no auth.

## Regression criterion (AC1)

AC1: `tests/test_api_ingest_filename.py` passes after the fix and fails on the old code. It covers `../x.xml`, `..\x.xml`, `../../x.xml`, `sub/x.xml`, `sub\x.xml`, `..`, `C:x.xml`, `x.xml:stream`, `a..b.xml` and a forward-slash absolute path all returning 4xx with nothing written outside the temp dir and the loader never called; NUL in a name is pinned on the helper `_is_plain_xml_name` (httpx cannot send a raw NUL); a valid `.xml` upload still ingests (200, three levels loaded, bytes reach the loader inside the endpoint's own temp dir, nothing left behind).

AC2: 4xx bodies of `/ingest` contain no filesystem path and no parser/exception text (asserted for the rejection bodies and for a parse failure carrying `/secret/place/upload.xml line 3`).

## Fix constraints

Minimal diff in `ingest_document`; same URL, field name and success response; the upload is stored under the fixed name `upload.xml` inside the per-request temp dir, so the client's name is validated but never touches the file system. Reuses the CPID-13 validator `_is_plain_xml_name`. No new dependency. The existing test that asserted the loader receives `plant.xml` is updated to the fixed name (intended behaviour change, noted in the PR).

## Risks

High: security fix on a network-facing write endpoint (security.md: human review; delegated here). A legitimate file name containing `..` or `:` is now rejected with 400. Rollback: revert the commit.
