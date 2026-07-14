# ADR-0181: metaos × ecos 方案 C — 三平面契约化

- **Status**: ACCEPTED
- **Date**: 2026-07-14
- **Owner**: governance-team + eCOS team

## Context

metaos (L2 决策) 与 ecos (L0 协议/编排 fabric) 边界不纯：L0 点名 L2、I0 硬 import、认知框架硬路径、双编排入口、ecos 职责膨胀。

## Decision

采用 **方案 C：逻辑平面 + 契约固化 + 入口封顶 + 硬化（渐进）**。

| 决策 | 选择 |
|------|------|
| D1 编排控制面 | ecos workflow fabric (`bos://ecos/workflow/*`) |
| D2 决策/准入语义 | metaos |
| D3 层间耦合 | AdmissionPort SPI；L0 只声明义务 |
| D4 物理拆仓 | 暂缓；ecos 内逻辑分区 core/fabric/ops |
| D5 metaos MCP | 默认禁用 standalone mesh 入口 |
| D6 MOF 数据 | env / walk / 同步镜像 + MANIFEST |

## Phases

### Phase 1 — 契约解耦 ✅

- `agora.admission.AdmissionPort` + metaos provider entry point
- L0 `CR-ADMISSION-01` → `admission.evaluate` + `realized_by`
- cognitive_framework 去 `parents[4]` 硬路径

### Phase 2 — 入口封顶 ✅

- `bos://memory/metaos/mcp-server` deprecated + BOS load 过滤
- `METAOS_MCP_ALLOW_STANDALONE` 门禁
- `ecos.workflow.preflight` + fabric metaos backend

### Phase 3 — 逻辑分区 ✅

- `ecos/ssot/registry/partition-map.yaml`
- `partition_import_lint`（挂 `make lint`）
- 移除 fabric→ops `sys.path` 注入

### Phase 4 — 硬化（子集）✅

1. **MOF 数据包**: `metaos/scripts/sync_cognitive_frameworks.py` + `resources/cognitive_framework/MANIFEST.json`；`METAOS_PREFER_BUNDLED=1`
2. **Bus 生产接线**: `metaos.integrations.bus_adapter`；workflow 经 bus/http/`both`；`METAOS_EVENT_BUS`
3. **会话完整性**: `agent_runtime/integrity.py` HMAC；`METAOS_SESSION_INTEGRITY_*`
4. **Capability 策略 YAML**: `METAOS_CAPABILITY_PROFILES` / `~/.metaos/capability-profiles.yaml`

### 仍属后续（Agent Runtime Phase D 剩余）

- 专用 container executor / Docker socket 门禁
- Provider 版本 smoke
- OS path ACL

## Verification

```bash
# Phase 4
cd projects/metaos
uv run python scripts/sync_cognitive_frameworks.py --check
uv run pytest tests/test_phase4_hardening.py -q
```

## References

- `docs/METAOS-ECOS-SCHEME-C.md`
- `projects/ecos/docs/ARCHITECTURE-REVIEW-workflow-convergence.md`
- `projects/metaos/docs/AGENT-RUNTIME-CONVERGENCE-PLAN.md`
