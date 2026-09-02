# Closeout — 2026-07-15 hygiene follow-up

## Ops (local, not in git)

- Released ~18 squash-merged stack worktrees (Scheme C / Wave2 / doctor / enforce / …)
- Kept: `ws-agora-heartbeat-transport`, `ws-short-term-improvements` (active / unique work)

## Landed in this PR

| Item | Path |
|------|------|
| Waiver evidence template | `docs/operations/workflow-waiver-template.md` |
| Worktree hygiene guide | `docs/operations/worktree-hygiene.md` |
| Prune helper (dry-run default) | `bin/gac/gac-worktree-prune.sh` |
| suggest --from-diff in red-line paths | AGENTS / CLAUDE / project-governance / contract |
| next-adr-id Python 3.9 fix | `bin/adr/next-adr-id.py` (`timezone.utc`) |

## Verify

```bash
bash bin/gac/gac-worktree-prune.sh
python3 bin/adr/next-adr-id.py --json
```
