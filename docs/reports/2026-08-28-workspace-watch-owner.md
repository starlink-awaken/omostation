# Workspace watch owner evidence — 2026-08-28

The legacy minute watcher executed Documents `domain-sync`, `bridge-refresh`,
`session-brief`, and `weekly-verdict-generator` based on mtime changes. Those
actions could reintroduce retired Documents writers even after their scheduled
cron lines were migrated.

## Owner contract

- Entry: `lib/workspace_watch_dispatch.py`.
- Preserves four watch groups and Workspace stamp semantics.
- Domain, bridge, and inbox changes call canonical Workspace/read-only owners.
- Weekly verdict changes produce an explicit `pending` event because no
  Workspace verdict owner is registered; they never write Documents.
- `--json` stdout is a pure `workspace.watch-dispatch.v1` envelope; logs go to
  stderr for cron redirection.

## Candidate schedule

```cron
* * * * * cd "$HOME/.local/share/omostation/accepted-20260903" && uv run --with pyyaml python lib/workspace_watch_dispatch.py --documents-root "$HOME/Documents" --workspace-root "$HOME/Workspace" --stamps "$HOME/Workspace/runtime/.watch-dispatch-stamps.json" --json >> "$HOME/Workspace/runtime/cron/documents-plane.log" 2>&1
```

The candidate is not installed by the implementation PR. A governed cutover
must record accepted-release identity, crontab backup/hash, exact old/new
counts, unrelated-line byte identity, and a post-cutover smoke.
