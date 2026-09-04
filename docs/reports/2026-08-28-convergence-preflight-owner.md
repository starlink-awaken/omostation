---
type: ephemeral
created: 2026-09-03
---

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

- Run from clean accepted release `accepted-20260908` against the live Documents
  root on 2026-08-29.
- Result: `documents.convergence-preflight.v1`, status `findings`, exit `1`.
- Summary: `checks=5`, `passed=4`, `findings=884`.
- The findings are reported as data; no Documents writes were observed.

## Candidate schedule

The canonical candidate adds a single replacement for Monday 06:30:

```cron
30 6 * * 1 cd "$HOME/.local/share/omostation/accepted-20260908" && uv run --with pyyaml python bin/gac/documents-domain-owner-job.py convergence-preflight --json --documents-root "$HOME/Documents" --workspace-root "$HOME/.local/share/omostation/accepted-20260908" --evidence .omo/_delivery/documents-plane/convergence-preflight.json >> runtime/cron/documents-plane.log 2>&1
```

## Cutover evidence

- Run: `20260827T172519Z-governance-state-mutation-fa89806e`
- Accepted root: `a23141ad8a39d5b39ecac0a4c00787e8e6600a2b`
- Before crontab SHA-256: `d15b1be2d67eb4a5dd44c8acdb761dd0b1916634c9ffe794f8718b0eb73e17e9`
- After crontab SHA-256: `705894d0cf34e8a61fa01dfd8dd3452b15cfc34ce735384cb5a8a7bf730d2cdd`
- Target replacement: old `check-convergence.py` count `1 -> 0`; new
  `convergence-preflight` count `0 -> 1`.
- Unrelated crontab lines: `108`, byte-identical before/after.
- Post-cutover result: `documents.convergence-preflight.v1`, status `findings`,
  exit `1`, `checks=5`, `passed=4`, `findings=884`, errors `[]`.
- The accepted release ran from its own directory; evidence was written below
  its Workspace runtime state and no Documents history/report was created by
  the new owner.

## Current verification

- Current owner line count: exactly 1; legacy `check-convergence.py` process
  count: 0.
- Live result: `documents.convergence-preflight.v1`, status `findings`, exit
  `1`, checks `5`, passed `4`, findings `884`, errors `[]`.
- Documents `.history/convergence-history.json` count remained `1 → 1`,
  confirming the preflight did not add a Documents history file.
- The active line now uses clean `accepted-20260908`; release-root provenance is
  covered by T10-46's exact crontab inventory and rollback snapshot.
