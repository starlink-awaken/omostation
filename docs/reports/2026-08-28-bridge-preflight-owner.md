---
type: ephemeral
created: 2026-09-03
---

# Bridge preflight owner evidence — 2026-08-28

The live bridge-refresh cron previously wrote Documents Dashboard projections.
This wave introduces a Workspace-only bridge readiness check and records the
accepted-release cutover below.

The accepted release targets clean `accepted-20260908` and replaced only the 06:05
bridge-refresh writer. The existing Dashboard content and legacy writer remain
intact for parity and rollback; the legacy writer is no longer scheduled.

## Cutover evidence

- Run: `20260827T164501Z-governance-state-mutation-1d0e88e3`
- Accepted root: `c5187900d4ae77e16631c512571cdb82a35dcafb`
- Before crontab SHA-256: `5d69f98aeddf678e4ee50eef6e7fdd7069ea67e8caa54de16f1fac2e9e5e19d1`
- After crontab SHA-256: `d15b1be2d67eb4a5dd44c8acdb761dd0b1916634c9ffe794f8718b0eb73e17e9`
- Target replacement: old `bridge-refresh.py` count `1 -> 0`; new
  `bridge-preflight` count `0 -> 1`.
- Unrelated crontab lines: `108`, byte-identical before/after.
- Post-cutover result: `documents.bridge-preflight.v1`, status `ready`, exit
  `0`, `sources_ready=3`, `markers_ready=2`, errors `[]`.
- The preflight ran with `cd accepted-20260908`, reads Documents and Workspace
  readiness only, and did not execute or write the legacy Documents writer.

## Current release-root reconciliation

T10-46 converged the active owner/preflight schedule roots. The current 06:05
line points to `accepted-20260908`, appears exactly once, and no legacy
`bridge-refresh.py` process was observed. Focused bridge tests pass `4/4`.
The legacy writer remains retained for parity and rollback; this evidence does
not claim Cockpit projection parity.
