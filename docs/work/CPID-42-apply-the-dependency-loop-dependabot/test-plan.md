# CPID-42 — Test plan: Apply the dependency loop: dependabot config and triage

Status: plan-approved · Risk: low · Jira: CPID-42

Test framework and conventions found: this item changes no application code. Evidence is command output: `factory sync --check`, `factory verify`, `factory status`, the YAML parse of `dependabot.yml`, `gh` reads and the Jira tickets. Application test suites are not touched (CI runs them on the PR).

| AC | Level | Test (name/path) | Happy | Boundary | Negative | Status |
|----|-------|------------------|-------|----------|----------|--------|
| AC1 | manual | `factory sync --check` and `factory status` in the worktree | exit 0 after sync; the summary prints with real counts and is pasted into `notes.md` and Jira | `unknown` parts reported as such | sync ran without `--force`; no conflict | verified |
| AC2 | manual | parse `.github/dependabot.yml` with PyYAML and list ecosystem, directory, interval, groups | `uv /`, `npm /frontend`, `github-actions /`, weekly, `minor-and-patch` | n/a: fixed set | no `pip`; no `ignore` or `allow` | verified |
| AC3 | manual | `gh pr list --author app/dependabot` before and after the config merge; per PR `gh pr view`, `gh pr diff`, `gh pr checks --required` | each merged PR has the four conditions written down | a PR with one failed condition is not merged | each non-merged PR has a Jira issue naming the condition | verified |
| AC4 | manual | `gh run view <id> --log` for the failing runs; scratch reproduction with pnpm | cause stated with log lines and reproduction | several packages, one cause | a project or updater cause is filed, not worked around | verified |

## Regression risk

`sync` rewrites managed files: a locally modified managed file would conflict and stop the step. `verify` must stay OK. The merged `dependabot.yml` starts new Dependabot PRs; none merges without the policy conditions.

## Untestable AC

None.

## Manual checks

All four rows are manual by nature (a configuration and operations item); the Test column holds the steps and Happy the expected observation.

## Audit (after implementation)

Manual rows, so no mutation applies; each was confirmed by reasoning about what would make it fail.

| AC | Evidence | How it would fail |
|----|----------|-------------------|
| AC1 | actory sync created 4 and updated 7 managed files with no conflict; actory sync --check printed "in sync with the factory source"; actory verify printed erify: OK; the actory status summary is in 
otes.md | a hand-edited managed file would print CONFLICT and sync --check would exit 1 |
| AC2 | PyYAML on .github/dependabot.yml printed uv /, 
pm /frontend, github-actions /, all weekly with minor-and-patch, and no ignore or llow | an extra or missing ecosystem, or an ignore key, changes that list |
| AC3 | gh pr list showed 0 open Dependabot PRs at triage; the one earlier PR (#22) was re-read against the four conditions in 
otes.md | a PR with a major bump or a source file would show in gh pr view --json files and gh pr diff |
| AC4 | the logs of runs 37497613594 and 37488935762 show security_update_not_possible; pnpm update source-map-js undici --lockfile-only in a scratch copy resolved both, touching only the lockfile; CPID-43 filed | a configuration cause would show as a dependabot.yml parse or directory error in the log, not found |