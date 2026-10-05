# CPID-20 — Test plan: path traversal in /ingest

Status: implementing · Risk: high · Jira: CPID-20

Test framework and conventions found: pytest in `tests/`, `fastapi.testclient.TestClient`, loader, graph builder and Neo4j loader replaced by fakes via `monkeypatch`, `tests/fakes.py::FakeDriver`; command `.venv/Scripts/python.exe -m pytest -q`.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | integration | tests/test_api_ingest_filename.py::test_valid_xml_upload_still_ingests, ::test_client_filename_never_reaches_the_file_system | `plant.xml` -> 200, 3 levels loaded, bytes inside the endpoint temp dir, nothing left behind; name with spaces/accent stored as `upload.xml` | n/a: single valid names | n/a: see negatives below | verified |
| AC1 | integration | tests/test_api_ingest_filename.py::test_traversal_style_names_are_rejected_and_nothing_is_written | n/a: negative-only | `..`, `a..b.xml` -> 4xx | `../x.xml`, `..\x.xml`, `../../x.xml`, `sub/x.xml`, `sub\x.xml`, `C:x.xml`, `x.xml:stream` -> 4xx, loader never called, no file anywhere under the sandbox | verified |
| AC1 | integration | tests/test_api_ingest_filename.py::test_absolute_path_name_is_rejected_and_nothing_is_written, ::test_ticket_exploit_dotdot_name_writes_nothing_above_the_temp_dir | n/a: negative-only | n/a: single value | absolute `C:/…/evil.xml` or `/…/evil.xml` -> 4xx, target absent; `../../x.xml` creates no `x.xml` | verified |
| AC1 | unit | tests/test_api_ingest_filename.py::test_plain_xml_name_helper, ::test_non_xml_names_are_still_rejected | `plant.xml`, `PLANT.XML` accepted | NUL in name, trailing NUL, `plant.xml.txt` | `a/b.xml`, `a\b.xml`, `/abs.xml`, `x.txt`, blank, no extension | verified |
| AC2 | integration | tests/test_api_ingest_filename.py::test_parse_failure_body_does_not_leak_paths_or_exception_text, ::test_rejection_bodies_do_not_leak_paths | n/a: bodies only | n/a: single case | parser text `/secret/place/upload.xml line 3` absent from the 400 body; tmp path and `sandbox` absent from the rejection body | verified |

## Regression risk

Existing `/ingest` tests in tests/test_api.py must stay green. One assertion changed on purpose: the loader now receives `api.UPLOAD_TMP_NAME` instead of the client's `plant.xml` (the behaviour change this fix introduces); the content assertion beside it is unchanged. `/pid/svg` tests untouched.

## Untestable AC

None. (A raw NUL cannot be sent through httpx, so it is pinned on `_is_plain_xml_name`, the only gate.)

## Manual checks

None.

## Audit (after implementation)

Red first: on the old code 12 of the new tests failed (traversal names answered 200 and wrote the file; the parse-error body contained `/secret/place`). Mutations tried on the fixed code, each caught: (M1) delete the `_is_plain_xml_name` check -> 8 failed; (M2) write to `Path(tmpdir) / file.filename` again -> 4 failed; (M3) echo `{exc}` in the 400 detail -> 1 failed (leak test). Full suite after the fix: 187 passed, 1 skipped.
