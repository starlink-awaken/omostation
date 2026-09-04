---
type: ephemeral
created: 2026-09-03
---

# Documents freshness owner evidence — 2026-08-27

## Result

The Workspace-owned command is:

`bin/gac/documents-domain-owner-job.py freshness-audit`

The live read used the Documents L4 manifest registry and wrote only to:

`.omo/evidence/20260827T143504Z-project-code-change-b0c7854a/documents-freshness-live.json`

With `--today 2026-08-27`, the result was `findings`, exit 1:

| Status | Domains |
| --- | ---: |
| ok | 0 |
| stale | 0 |
| invalid | 0 |
| missing | 12 |

The 12 missing findings are truthful: current domain gateways do not consistently
declare a CLAUDE review date, while STATE review dates are present for the domains
where a STATE file exists. This is an owner-readiness finding, not evidence to
mark the control plane healthy.

## Verification

- focused tests: 4 passed;
- Ruff: passed;
- invalid registry/root/input paths return exit 2;
- healthy fixture returns exit 0;
- evidence path is Workspace-only;
- Documents bytes and mtimes remained unchanged in the fixture proof.

## Cutover decision

The existing Documents freshness cron remains unchanged. Before schedule cutover,
the missing review metadata must be either supplied as content-plane declarations
or explicitly represented as an accepted policy exception; the owner command will
continue to fail truthfully until then.
