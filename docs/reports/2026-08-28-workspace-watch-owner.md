---
type: ephemeral
created: 2026-09-03
---

# Workspace watch owner evidence — 2026-08-29

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
* * * * * cd "$HOME/.local/share/omostation/accepted-20260908" && uv run --with pyyaml python lib/workspace_watch_dispatch.py --documents-root "$HOME/Documents" --workspace-root "$HOME/Workspace" --stamps "$HOME/Workspace/runtime/.watch-dispatch-stamps.json" --json >> "$HOME/Workspace/runtime/cron/documents-plane.log" 2>&1
```

## Cutover evidence

- Run: `20260827T200025Z-governance-state-mutation-6575ec3b`
- Accepted root: `e0d61b8adae0894d1ca4c37bae9dd73c5c15d275`
- Before crontab SHA-256: `c3e8c84e499400f074429928a6d267b8346153dadbede10e4871abe7631ef334`
- After crontab SHA-256: `800024add72ae588e2615a5b3cbbf14cfc785f6146e195dd3a96825208de4d46`
- Target replacement: old `watch-dispatch.py` count `1 -> 0`; new Workspace
  watcher count `0 -> 1`.
- Unrelated crontab lines: `108`, byte-identical before/after.
- Post-cutover result: `workspace.watch-dispatch.v1`, status `ok`, exit `0`,
  JSON stdout parsed cleanly, no events on stable inputs.
- Live stamps remain under Workspace runtime; no Documents script was invoked by
  the post-cutover smoke.

## Current release verification

The current accepted-20260908 owner was run from an isolated temporary
Workspace root against the real Documents root. The first pass returned the
four expected groups: `domain-manifests=ok`, `workspace-state=findings`,
`inbox-router=ok`, and `weekly-verdict=pending`; the findings status reflects
the underlying bridge owner and is not hidden. The second unchanged-input pass
returned exit `0` with no events. Stamps and generated `BRIEF.md` stayed inside
the temporary Workspace, and no legacy Documents writer process was observed.
