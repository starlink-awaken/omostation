# ecos — System Boundary

> 本文档描述 ecos 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。

---

## 1. 暴露接口

### BOS URI

- `bos://ecos/*`
- `bos://meta/discover`
- `bos://memory/vault/search`

### 入口

- **CLI**: `ecos-dashboard`, `ecos-scheduler`, `ecos-watchdog` (SSB/workflow 入口已收敛至 `cockpit ssb`/`cockpit workflow`)
- **MCP stdio**: `ecos-mcp` (MOF + L0 tools)
- **Tools**: 34 MOF 工具 (`mof-validate`, `mof-audit`, `mof-derive`, `mof-bridge-sync`, `mof-state-bridge`, `mof-contract-lint`, `mof-enforce` 等)
- **Agents**: `mof-contract-agent` (BOS URI 分析/诊断)

## 2. 上游依赖

| 项目 | 依赖方式 | 用途 |
|------|----------|------|
| agora (I0) | 软依赖 (try/except) | Dashboard/MOF BOS 功能 |
| model-driven (M0) | 动态 import (fallback 硬编码) | M3 STANDARD_STAGES / STANDARD_GATES / PipelinePhase |
| omo (L2) | `mof-state-bridge.py` import | `.omo/tasks/` ↔ M1 OMOTask 双向同步 |

## 3. 下游影响

| 项目 | 依赖方向 | 说明 |
|------|----------|------|
| omo (L2) | ecos → omo | `mof-state-bridge.py` 调用 `omo.omo_ingress.create_planned_task` + `omo.omo_io.write_yaml_atomic` |
| cockpit (L3) | cockpit → ecos | `cockpit ssb` / `cockpit mof` / `cockpit workflow` 收敛入口 |
| metaos (L2) | 软依赖 | workflow backend (可选) |
| runtime (L1) | 软依赖 | workflow backend (项目生命周期) |

## 4. 配置 / SSOT

- 项目源码：`projects/ecos/`
- 入口定义：`projects/ecos/pyproject.toml`
- MOF 元模型 SSOT：`projects/ecos/src/ecos/ssot/mof/` (M3/M2/M1 三层)
- L0 约束 SSOT：`projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`
- 测试：`cd projects/ecos && uv run pytest tests/ -q`
