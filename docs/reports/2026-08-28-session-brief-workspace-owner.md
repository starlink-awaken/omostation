---
status: archived
lifecycle: history
owner: unassigned
last-reviewed: 2026-08-27
---
# Session brief Workspace owner evidence — 2026-08-28

The legacy Documents `session-brief.py` writes
`@驾驶舱/_control/BRIEF.md` and invokes Documents runtime scripts for domain,
bridge, and async checks. The canonical Workspace owner is
`bin/mof/generate-brief.py`; this change adds explicit root/output parameters so
accepted-release code can read live Workspace state and write live Workspace
`BRIEF.md`.

## Owner contract

- `OMOSTATION_WORKSPACE_ROOT` selects the state/knowledge root.
- `OMOSTATION_BRIEF_OUTPUT` selects the generated brief output.
- Defaults remain the repository root and `<root>/BRIEF.md` for existing callers.
- The scheduled command does not import or execute `session-brief.py`,
  `domain-sync.py`, `bridge-refresh.py`, or `async-audit.py` from Documents.

## Candidate schedule

The canonical candidate replaces only daily 06:15:

```cron
15 6 * * * cd "$HOME/.local/share/omostation/accepted-20260901" && OMOSTATION_WORKSPACE_ROOT="$HOME/Workspace" OMOSTATION_BRIEF_OUTPUT="$HOME/Workspace/BRIEF.md" uv run --with pyyaml python bin/mof/generate-brief.py --write --if-changed >> "$HOME/Workspace/runtime/cron/documents-plane.log" 2>&1
```

## Cutover evidence

- Run: `20260827T181949Z-governance-state-mutation-3c5a6f5f`
- Accepted root: `5f6e53083d35433ee4734f063f71cf76e60db296`
- Before crontab SHA-256: `ef7e25fc16346b6792cbdb918d1e971a61f6dd6a17b270615b9dc5c9932f6d7b`
- After crontab SHA-256: `6a0d008c922eda8ed0410b8e91ea93fa2dabc04044d25ee13d0e125d55f68083`
- Target replacement: old `session-brief.py` count `1 -> 0`; new canonical
  `generate-brief.py` count `0 -> 1`.
- Unrelated crontab lines: `108`, byte-identical before/after.
- Pre-cutover release smoke: `generate-brief.py --write --if-changed` exit `0`,
  generated a 2,627-byte Workspace brief in the accepted release.
- Post-cutover live smoke: exit `0`, `BRIEF.md` output target was
  `/Users/xiamingxing/Workspace/BRIEF.md`, and the owner correctly skipped the
  write because its normalized content was unchanged.
- Documents `@驾驶舱/_control/BRIEF.md` SHA, mtime, and byte count were identical
  before/after the live owner invocation (`21437` bytes); no Documents write
  occurred.
