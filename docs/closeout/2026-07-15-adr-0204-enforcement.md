# Closeout — ADR-0204 enforcement bundle

## Landed

1. **Staged-only requirement iteration gate** (`requirement_iteration_report` in omo.workflow)
2. **pre-push** → `bin/ssot/*` + `bin/` compatibility wrappers
3. **worktree claim** default init: ecos, scripts, omo, cockpit, agora
4. **`bin/adr/next-adr-id.py`** next/claim helper
5. ADR-0204 + registry `in_scope_paths` / `exclude_paths` / enforcement pointer

## Verify

```bash
uv run --with pyyaml python bin/agent-workflow.py compliance --json | jq .requirement_iteration
python3 bin/adr/next-adr-id.py --json
test -f bin/ssot/sync-submodules-push.sh && test -x bin/sync-submodules-push.sh
grep -n 'bin/ssot/sync-submodules-push' .githooks/pre-push
```
