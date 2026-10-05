# CPID-5 — Test plan: Refresh AGENTS.md

Status: draft · Risk: low · Jira: CPID-5

Test framework and conventions found: documentation change, no code. Checks are shell commands run once and
recorded here; the pytest suite (`.venv/Scripts/python.exe -m pytest -q`, 38 tests) must stay green.

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | manual | `git grep -n "SCRUM-\|C:.Dev" -- AGENTS.md` | no output; CPID board URL present | n/a: text search | n/a: grep exits 1 when nothing matches | verified |
| AC2 | manual | open Confluence page 16711696 and the link in AGENTS.md | page has the tables | n/a: single page | n/a: no input | verified |
| AC3 | manual | compare each stated fact with pyproject.toml, config.py, .env.example, docker-compose.yml | all match | n/a: facts | n/a: no input | verified |
| AC4 | manual | `.venv/Scripts/python.exe scripts/<name>.py --help` for each documented script | exit 0, flags listed | n/a: flags | a wrong flag would make argparse exit 2 | verified |
| AC5 | manual | extract text between factory markers from HEAD of main and worktree, diff; `python .factory/verify.py` | empty diff, verify OK | n/a: single block | n/a: no input | verified |

## Regression risk

None for code. The 38 tests are unaffected; run once anyway.

## Untestable AC

None.

## Manual checks

All rows are manual because the artefact is prose; the commands above are the exact steps and expected observation.

## Audit (after implementation)

Results recorded in the PR description.
