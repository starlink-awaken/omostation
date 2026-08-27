# Convergence preflight owner evidence — 2026-08-28

The legacy `@公共/_runtime/check-convergence.py` is a Documents-side writer:
it creates `.history/convergence-history.json` and, with `--report`, writes a
generated report. This owner moves the scheduled execution to Workspace while
leaving the legacy file available for parity and rollback.

## Owner contract

- Entry: `bin/gac/documents-domain-owner-job.py convergence-preflight`.
- Schema: `documents.convergence-preflight.v1`.
- Exit `0`: all checks pass; exit `1`: checks ran with findings; exit `2`:
  required roots, registry, or evidence boundary are unavailable.
- Documents is read-only. Evidence is written only below the caller-provided
  Workspace root; no Documents history/report directory is created.

## Live preflight

- Run from the implementation worktree against the live Documents root on
  2026-08-28.
- Result: `documents.convergence-preflight.v1`, status `findings`, exit `1`.
- Summary: `checks=5`, `passed=4`, `findings=884`.
- The findings are reported as data; no Documents writes were observed.

## Candidate schedule

The canonical candidate adds a single replacement for Monday 06:30:

```cron
30 6 * * 1 cd "$HOME/.local/share/omostation/accepted-20260830" && uv run --with pyyaml python bin/gac/documents-domain-owner-job.py convergence-preflight --json --documents-root "$HOME/Documents" --workspace-root "$HOME/.local/share/omostation/accepted-20260830" --evidence .omo/_delivery/documents-plane/convergence-preflight.json >> runtime/cron/documents-plane.log 2>&1
```

The candidate is not installed by this code PR. A separate governed cutover
must record accepted-release identity, crontab backup/hash, exact old/new
counts, unrelated-line byte identity, and post-cutover smoke.
