# CPID-42 notes

Date: 2026-10-07

## Dependency status (before this change)

`factory status` for `vishal7pandey/chatpid` reported:

| Source | Open |
|---|---:|
| Dependabot alerts | 12 (3 high, 6 medium, 3 low) |
| Code-scanning alerts | 0 |
| Secret-scanning alerts | 0 |
| Dependabot PRs | 0 |
| Failed Dependabot Updates runs, last 7 days | 10 |

Needs attention: yes (3 critical/high alerts; 10 failed runs). Read-only snapshot; no alert was dismissed.

## Dependabot configuration

`factory sync` (without `--force`) created `.github/dependabot.yml`; `factory sync --check` is clean and
`factory verify` is OK. PyYAML confirms exactly `uv /`, `npm /frontend` and `github-actions /`, each weekly
with a `minor-and-patch` group, no `ignore` or `allow`.

## PR triage

No Dependabot PR was open at triage time. The last one, #22 (`langgraph-sdk` 0.4.2 to 0.4.4, `uv.lock` only,
a patch update from a security-update PR), had already been merged by a human on 2026-10-06 at 17:56 UTC,
before this item; on re-reading it met the four conditions that the policy sets (patch, `uv.lock` only, required
checks `test` and `verify` green).
Re-check after this configuration reaches `main`: the scheduled version updates may open PRs. The frontend
has no CI job (CPID-38) and only `test` and `verify` are required, so a green PR touching `/frontend` proves
little about the frontend.

## Failed update runs

All ten failures are `npm_and_yarn in /frontend` security jobs (`source-map-js`, `undici`, `brace-expansion`,
`js-yaml`). Runs 37497613594 (source-map-js) and 37488935762 (undici) end with `security_update_not_possible`
(source-map-js: latest resolvable 1.2.1, fixed 1.2.2; undici: 8.10.0 vs 8.10.2; no conflicting dependencies).
Both packages are transitive and the project uses pnpm 11.22.0. In a scratch copy of the frontend manifests,
`pnpm update source-map-js undici --lockfile-only` resolved them to 1.2.2 and 8.11.2, touching only the lockfile.
So this is not a configuration problem of the repo (the same finding as ADE-64 in the sibling project); filed as
CPID-43 (Task). No alert was dismissed and no lockfile changed here.
