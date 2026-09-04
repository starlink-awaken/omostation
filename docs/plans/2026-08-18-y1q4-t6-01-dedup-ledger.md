---
title: Y1Q4-T6-01 去重清单终版 — aetherforge → runtime (内包)
type: evidence
owner: engineering-agent
created: 2026-08-18
bet: BET-Y1Q4-T6-01
related:
  - docs/plans/3y-bet-ledger.yaml#BET-Y1Q4-T6-01
  - .omo/_knowledge/retros/BET-Y1Q3-T6-01.md
lifecycle: plan
last_updated: 2026-08-18
---

# Y1Q4-T6-01 去重清单终版（逐项可复核）

## 口径声明

- 归并形态：**目录内包 + 无消费者归档**（复用 T6-01 gbrain+kairon→knowledge 模式）
  - src/aetherforge/ + packages/{mesh,gateway}/ **内包**至 projects/runtime/aetherforge/（runtime 真实消费 gateway/compute_mesh，non_goal 明示）
  - packages/swarm/ **归档**至 projects/aetherforge-archive/swarm/（零外部真实消费者，done_when 要求归档后删）
- 表面计量以 merge 后主仓 `bet-ledger.py surface` 为准
- test_loc 基线 350,854 保护量；本轮实测 431,451（+23%，守住）

## 清单（合并后归档/删除项 → 行数）

| # | 去重项 | 实证 | 删除量 (行) |
|---|--------|------|------------|
| 1 | packages/swarm 归档 | `mv packages/swarm projects/aetherforge-archive/swarm` — 29,814 行（含 swarm_engine 全部源码/测试） | 29,814 |
| 2 | .gitmodules aetherforge 条目删除 | 4 行 `[submodule "projects/aetherforge"]` 块移除 | 4 |
| 3 | project-registry.yaml aetherforge block | 9 行 `aetherforge:` 项目声明移除 | 9 |
| 4 | bos-services.yaml 路径更新 | `--directory projects/aetherforge` → `--directory projects/runtime/aetherforge`（1 处）+ swarm fail-closed 注释（1 处） | 净改写 ≈0 |

**去重合计：~29,827 行**（其中 packages/swarm 29,814 占绝对大头）。

## 内包保留（明确不删）

- src/aetherforge/gateway/（~1945+行） — runtime/executor/engine.py 真实消费 llm_gateway（non_goal 明示刚需）
- src/aetherforge/mesh/（~44行 rpc）— omo_mesh_event_handler.py 真实消费 compute_mesh
- packages/mesh/ + packages/gateway/ — 配套 compute_mesh + llm_gateway 子包
- src/aetherforge/{triage,route,bridge,mcp_server,cli,dashboard,bus_adapter,config} — 真实活跃业务面

## fail-closed 改造（功能不删，禁用声明）

- `src/aetherforge/swarm/rpc.py`：118 行 GraphWorkflow 引擎调用 → 16 行 fail-closed shim（调用即返回 disabled 错误）
- `src/aetherforge/swarm/__init__.py`：原 re-export swarm_engine → 0-export 占位
- `src/aetherforge/cli.py:cmd_swarm`：118 行 swarm 子命令 → 16 行 argparse shim（保留 help/路由形状，调用即 disabled）
- `src/aetherforge/bus_adapter.py`：docstring 注释更新（事件发射函数保留，因为不依赖 swarm_engine 引擎）

## 非去重项（明确不列）

- `src/aetherforge/mcp_server.py`、`dashboard.py`、`triage/*` 等活跃业务：跨子包消费者不归本 bet 处置范围
- cockpit/agora/runtime 等调用方的引用更新：已就地完成（路径更新 + swarm URI fail-closed 注释）

## 实测环境验证（2026-08-18 集成测试）

- `import aetherforge` ✓（inner package 完整）
- `from aetherforge.swarm.rpc import run_swarm_workflow; run_swarm_workflow("test")` → `{"status": "failed", "error": "swarm_engine archived..."}` ✓
- `from aetherforge.mesh import mesh_status` ✓（保留路径，import OK）
- `tests/integration/run-all.sh` → 4/7 pass，3 失败均为 dev 环境（Kairon/gbrain deps 缺 + docker 未启），与本 bet 无关
