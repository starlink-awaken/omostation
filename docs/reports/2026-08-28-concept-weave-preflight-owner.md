---
type: ephemeral
created: 2026-09-03
---

# Concept weave preflight owner evidence — 2026-08-28

The monthly LaunchAgent currently executes a Documents shell writer that
mutates concept notes, logs/history, and sometimes inbox todo files. This wave
adds a Workspace-only read-only preflight; write-capable mesh/bridge operations
remain explicitly deferred.

## Live smoke

- Schema: `documents.concept-weave-preflight.v1`.
- Result: `findings`, exit `1`.
- Concept files: `78`; link edges: `3`; orphan files: `76`; decay candidates: `0`.
- Deferred operations: `mesh`, `bridge`, `exec-bridge`, `inbox-todo`.
- Evidence was written to an isolated Workspace path; no Documents writes or
  legacy script execution occurred.

## LaunchAgent candidate

The existing label/calendar semantics were preserved by migrating the calendar
event to an equivalent monthly cron line. The LaunchAgent plist remains as
disabled rollback material; its program is `/usr/bin/true` and contains no
Documents path.

## Cutover evidence

- Run: `20260827T202802Z-governance-state-mutation-6e0946ad`
- Original plist SHA-256: `5075040e211cce40401c45f981c5e57ecf404baf3c29d2c1e7f0e4723c03c8d8`
- Disabled rollback plist SHA-256: `fc23ff3e3e2679b6359d21f12b16a8922621533c82625d4b9abc297ff77b3657`
- Final direct-Python plist candidate SHA-256:
  `cea8fb20888edf676d3fcc797293bd125d7ecc42db8d1d3b5ffb010395d6abcd`
- All plist variants passed `plutil -lint`; original label and
  `Day=1/Hour=9/Minute=0` calendar were preserved in rollback material.
- LaunchAgent was booted out and is absent from `launchctl print`; the monthly
  09:00 day-1 schedule now runs via cron.
- Cron owner post-smoke: exit `1`, 78 concepts, 76 orphans, 3 link edges, 0
  decay candidates.
- Documents concept/log/inbox snapshot: 92 files before and after, unchanged
  tree fingerprint; no legacy writer executed.

## Current release verification — 2026-08-29

The active day-1 monthly cron now runs exactly once from clean
`accepted-20260908` and invokes the Workspace preflight. The disabled plist
remains the rollback carrier: `plutil -lint` passes, `Disabled=true`,
`ProgramArguments=/usr/bin/true`, and `launchctl print` reports the service is
absent. A fresh preflight returned `documents.concept-weave-preflight.v1`,
status `findings`, exit `1`, 78 concept files, 76 orphan files, 3 link edges,
0 decay candidates, `write_capable_status=deferred`, and no errors. No
Documents content was written.
