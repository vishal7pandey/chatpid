# CPID-41 — Sonar S2083 on ingest

Status: draft · Risk: high · Jira: CPID-41

## Repro

Environment: main @ 2ad662d (`chatpid/api.py`, `ingest_document`), Windows, Python 3.14, pytest, plus the SonarCloud scan of `main`
(project `vishal7pandey_chatpid`).

Scanner finding: SonarCloud issue `AaESHd3k4FTZ_gsvTVdz`, rule `pythonsecurity:S2083` ("Path Traversal via unsanitized user
input in api.ingest_document()"), BLOCKER, `chatpid/api.py:355`, status OPEN. Its taint flow, read from
`api/issues/search?issues=AaESHd3k4FTZ_gsvTVdz&additionalFields=_all`:

1. Source, `api.py:335`: the `file: UploadFile` parameter ("a user can craft an HTTP request with malicious content").
2. `api.py:354`: `content = await file.read()` ("can propagate malicious content to its return value").
3. Sink, `api.py:355`: `tmp_path.write_bytes(content)` ("a malicious value can be used as argument").

The tainted value in the flow is the upload CONTENT. The path written to is `Path(tmpdir) / UPLOAD_TMP_NAME`, a fresh
`tempfile.TemporaryDirectory()` plus the constant `"upload.xml"` (CPID-20, PR 10); the client file name is only validated by
`_is_plain_xml_name()` and never used as a path.

Automated repro (traversal names and hostile content through `POST /ingest`, recording the target of every `Path.write_bytes`):

- `uv run python -m pytest tests/test_api_ingest_filename.py -q` on main plus the new tests: 13 hostile names
  (`../x.xml`, `..\..\x.xml`, `/etc/x.xml`, `C:/Windows/x.xml`, `C:\Windows\x.xml`, UNC, `%2e%2e%2fx.xml`, `..%5cx.xml`,
  double-encoded, NUL) and 5 hostile contents all PASS on the unchanged code: every write targets `<temp dir>/upload.xml`,
  nothing is left outside the temp dir. So the CPID-20 fix is complete for client-controlled paths.
- One new case fails on the unchanged code: `test_write_is_contained_in_the_temp_dir_at_the_point_of_use` (3 cases): if the
  fixed name were ever changed to an escaping one (`../escape.xml`), the write is not stopped (`assert 200 == 500`). That is
  a missing guard at the point of use, not a reachable exploit today.

Reproducibility: the scanner issue is always open; the unguarded-sink test fails always.

## Expected

An upload is written only inside the endpoint's own temp dir, and the containment is checked right where the write happens,
in the `os.path.realpath` + `startswith(base + os.sep)` form Sonar and CodeQL recognise (as in `_find_pid_dir`, CPID-34 /
PR 20).

## Actual

The endpoint is safe today (all hostile inputs end up in `<temp dir>/upload.xml`), but the write has no containment check at
the sink, and SonarCloud reports the file-write sink with a request-derived value.

## Root cause (with evidence)

- Where: `chatpid/api.py:353-355` (`ingest_document`).
- Why it fails: the safety of the write rests on a constant name chosen elsewhere (`UPLOAD_TMP_NAME`), with no check at the
  point of use; Sonar's flow starts at the `UploadFile` parameter and reaches `write_bytes` through the file content.
  Request content reaching a file write is the endpoint's purpose (it is the XML to ingest); the content cannot choose the
  path.
- Introduced by: CPID-20 (PR 10) removed the client name from the path but left the sink unguarded; Sonar was enabled in
  CPID-40 and reported it.
- Evidence: the SonarCloud flow above; the passing hostile-input tests (safe today); the failing contained-write test (no
  guard at the sink).

## Blast radius

- Only `ingest_document`; it is the only upload endpoint. `GET /pid/svg` and `/pid/files` are guarded separately (CPID-13,
  CPID-34).
- No data has been written outside a temp dir: the name was never client-controlled after CPID-20.
- If SonarCloud still reports S2083 after the guard, the finding tracks content (not path) taint into `write_bytes`, which is
  a false positive: propose the dismissal to the owner with this evidence; do not dismiss without a yes.

## Regression criterion (AC1)

AC1: `tests/test_api_ingest_filename.py::test_write_is_contained_in_the_temp_dir_at_the_point_of_use` (3 cases) passes after the
fix and fails on the current code (a target that escapes the temp dir is refused with 500, nothing is written).

AC2: nothing regresses and the endpoint stays safe: `test_upload_bytes_only_ever_land_in_the_fixed_file_of_the_endpoint_temp_dir`
(13 hostile names), `test_hostile_upload_content_is_data_never_a_path` (5 contents) and the CPID-20 tests pass; backend suite
stays green (262 passed, 3 skipped with the new tests).

AC3 (closure, not code): after the fix is merged and the push scan on `main` has run, SonarCloud issue `AaESHd3k4FTZ_gsvTVdz`
re-queried shows `status` CLOSED. If it stays OPEN, it is a taint false positive and a dismissal PROPOSAL (reason `false
positive`, this evidence) goes to the owner on the Jira issue; the ticket stays In Progress until the owner says yes.

## Fix constraints

Minimal diff in `ingest_document` only: `os.path.realpath` of the temp dir and of the target, `startswith(base + os.sep)`
inline before `write_bytes`. No API change, no new dependency, no dismissal without the owner's yes.

## Risks

High (security finding on a network-facing endpoint; rule from the findings policy). Behaviour is unchanged for valid input
(the guard cannot trigger while the name is the constant). Rollback: revert the commit.
