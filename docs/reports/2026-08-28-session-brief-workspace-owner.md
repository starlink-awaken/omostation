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

The candidate is not installed by the implementation PR. A separate governed
cutover must record accepted-release identity, before/after crontab hashes,
exact old/new counts, unrelated-line byte identity, and post-cutover smoke.
