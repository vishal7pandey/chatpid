---
id: D-001
type: dismissal
title: Dismiss SonarCloud S2083 on the ingest upload as a false positive
status: proposed
jira: CPID-41
proposed_by: Claude (agent)
proposed_at: '2026-10-07'
alert: https://sonarcloud.io/project/issues?id=vishal7pandey_chatpid&issues=AaESVCox-B_YsUej5pDi&open=AaESVCox-B_YsUej5pDi
reason: false positive
options:
- text: Dismiss the alert as 'false positive'
  recommended: true
- text: Reject the dismissal and change how the upload is written (for example stream it to a file object without a path-sink pattern)
decision: null
by: null
at: null
delegated: false
---
# Dismiss SonarCloud S2083 on the ingest upload as a false positive

## Context

SonarCloud still reports `pythonsecurity:S2083` (path traversal, BLOCKER) on `POST /ingest` at `chatpid/api.py:362`,
after the endpoint was made safe twice (CPID-20, then CPID-41). The agent fixed what a reader can fix and now believes
the remaining report is a false positive, but dismissing a scanner finding is the owner's decision
(`.factory/policies/findings.md`). Jira ticket CPID-41 (work item `docs/work/CPID-41-sonar-s2083-on-ingest/`) carries
the agent's proposal comment; this record turns that comment into a question the owner can answer with one command.

## Evidence

- Alert: SonarCloud issue `AaESVCox-B_YsUej5pDi`, rule `pythonsecurity:S2083`, project `vishal7pandey_chatpid`,
  `chatpid/api.py:362`. An earlier key for the same finding, `AaESHd3k4FTZ_gsvTVdz` (`api.py:355`), was already closed
  when the code moved; this is the current one.
- Sonar's taint flow is the upload CONTENT: `content = await file.read()` flows into `write_bytes(content)`.
  Request content reaching a file is the endpoint's purpose (it is the DEXPI XML to ingest).
- The PATH written is not request-derived: a fresh `tempfile.TemporaryDirectory()` plus the constant `upload.xml`
  (`UPLOAD_TMP_NAME`). The client file name is only checked by `_is_plain_xml_name()` and never used as a path.
- Proof by test, `tests/test_api_ingest_filename.py`: 13 hostile file names (`../x.xml`, `..\..\x.xml`, absolute and
  drive paths, UNC, percent-encoded and double-encoded traversal, NUL) and 5 hostile contents sent through `/ingest`;
  every write landed only in `<temp>/upload.xml`, nothing outside the temp dir.
- Containment at the point of write: inline `os.path.realpath` plus `startswith(base + os.sep)` in `ingest_document`
  (PRs #25 and #26), tested by `test_write_is_contained_in_the_temp_dir_at_the_point_of_use`.
- After those two PRs the scanner still reports the finding, so what it tracks is content going into `write_bytes`,
  not a path.

## Options

1. Dismiss as `false positive` (recommended): closes the alert with the reason recorded in the repository. Cost: the
   scanner will not warn again for this flow; a future change that makes the path request-derived would be caught by
   the 13-name test, not by Sonar. CPID-41 can then be closed.
2. Reject and change how the upload is written, for example stream the upload to a file object without the
   `Path.write_bytes` pattern so the scanner no longer sees a path sink. Cost: a code change to a high-risk endpoint
   purely to quiet a scanner, with no safety gain over the current tests; it may also not satisfy the rule.

## Recommendation

Option 1: the tainted value is the upload content, the path is a constant inside a fresh temp dir, and 13 hostile names
and 5 hostile contents plus an inline containment check show nothing escapes it.
