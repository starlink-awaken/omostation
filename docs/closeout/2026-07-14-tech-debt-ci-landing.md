# Closeout — 2026-07-14 tech-debt + CI landing

## Stack landed on main

| PR | 内容 |
|----|------|
| #347 | bin path SSOT + evidence inline/mcp_proxy + omo evolution_loop |
| #349 | interfaces 7430 + debt-audit GNU stat |
| #350 | opc_p6_self_evolve → omo broker (Submodule Freshness) |
| (this) | CI tip always-run + bos-registry sync + BosService mcp meta + ADR-0182/0183 |

## Mechanism

- **gac-gate**: every push to `main` + every PR
- **evidence-smoke-gate**: every push to `main` + every PR + registry drift check
- **sync-bos-registry.py**: SSOT mirror for smoke/integration

## Residual (explicit)

| Item | Owner / when |
|------|----------------|
| ToolBox wps known-gap | re-check ≤ 2026-08-25 |
| Scheme C 5b container executor | new PR after ADR |
| Scheme C 5c OS ACL | design-only until host model locked |
| Wave 2 Phase B/C | blocked on Phase A delivery |

## Operator one-liner

```bash
git checkout main && git pull
uv run --with pyyaml python bin/ssot/sync-bos-registry.py --check
make gac-local-gate   # or: python bin/gac/gac-local-gate.py
```
