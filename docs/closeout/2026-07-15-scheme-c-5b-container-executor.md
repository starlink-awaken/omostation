# Closeout — 2026-07-15 Scheme C Phase 5b Container Executor

## What landed

| Surface | Change |
|---------|--------|
| ADR-0184 | Runtime model: local/docker/auto backends + profile SSOT |
| `agora.execution.container_executor` | Facade: `spawn_async` / `spawn_sync` / `build_spawn_argv` |
| `etc/container-executor-profiles.yaml` | default / trusted-local / strict-netnone |
| `StdioMCPClient.connect` | Routes through facade |
| `ProcessPool.get_or_spawn` | Routes through facade |
| `tests/test_container_executor.py` | 14 unit tests (no Docker required) |
| `bin/gac/evidence-smoke.py` | Reports `container_executor` status block |
| `docs/METAOS-ECOS-SCHEME-C.md` | Phase 5b ✅ + operator knobs |

## Defaults (honest)

- **CI / default**: `AGORA_SPAWN_BACKEND=local` — behavior parity with pre-5b.
- **Isolation on demand**: `AGORA_SPAWN_BACKEND=docker` + profile `default`
  (`network=none`, read-only root, cap-drop ALL).
- **Not in this PR**: OS ACL (5c), Docker-as-MCP-tool, forced docker in required CI.

## Verify

```bash
cd projects/agora
PYTHONPATH=src pytest tests/test_container_executor.py -q
# root:
uv run --directory projects/agora python ../../bin/gac/evidence-smoke.py --quiet
```

## Follow-ups

1. Scheme C **5c** OS ACL design ADR.
2. Optional GaC lint: ban parallel raw `Popen` in agora spawn paths.
3. Wave2 Phase B (predictive/viz) — independent of 5b.
4. Pin production docker image digest when ops chooses a hardened base.
