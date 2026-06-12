# Phase A.1 (R58) Milestone Evidence

> Date: 2026-06-12
> Plan: `docs/superpowers/plans/2026-06-12-bus-unification.md`
> Author: 老王

## 5 commit 落地

| SHA | 内容 |
|-----|------|
| `4f42a78` | refactor(agora): drop phantom omo dep (0 Python imports; cycle unblock) |
| `a40c697` | feat(bus): add AsyncioBackend + 4 tests |
| `b210aa4` | feat(bus): add CroniterBackend + MessageBusBackend (2 of 7) |
| `2fd10f0` | feat(bus): implement schedule() + multi-backend dispatch |
| (omo) `b250cfe` | feat(omo): add agora workspace dep + bus_demo_omo_producer |

## 解循环 (architecture win)

**问题**: agora ↔ omo 循环依赖 — omostation 多年来**假依赖** (agora pyproject 写 `omo`, 实际 0 Python import).

**Architect 方案 3 验证**:
- `grep -rn "from omo\|import omo" projects/agora/src` → **0 matches** (确认 0 真实 import)
- 删 2 行假依赖 (`agora/pyproject.toml` line 32, 86)
- 加 omo → agora 单向依赖 (mirror 现 aetherforge-gateway 模式)
- 加 `bus_demo_omo_producer.py` 真用 agora.bus
- 跑通: `uv run python -m omo.bus_demo_omo_producer` 输出 `omo demo event published: evt_...`

**净影响**: 0 行 src/ 改, 3 行 pyproject 改, 40 行 omo demo 加, 1 个真跨仓 import 跑通.

## Phase A.1 进度

- ✅ AsyncioBackend (进程内 await, asyncio.Queue)
- ✅ CroniterBackend (every Xm / every Xh, 30s tick)
- ✅ MessageBusBackend (agent-to-agent, 保持 req/resp 语义)
- ✅ schedule() decorator (走 CroniterBackend)
- ✅ Multi-backend dispatch (按 envelope.backend 选)
- ⏳ 4 backend 待: SSE / WS / Realtime / CronDaemon
- ⏳ 3 demo 待: omo_sse_daemon / metaos/workflow / cron_service

## 验收

| 项 | 结果 |
|----|------|
| 4 backend 实现 | ✅ (3 个 + 原有 eventbus) |
| schedule() 落地 | ✅ (3 tests) |
| 单 backend < 500 行 | ✅ max 115 (croniter) |
| 子包总行数 | ✅ ~530 行 |
| Cross-repo 真跑通 | ✅ (omo demo) |
| 22/22 bus tests | ✅ |
| 41/41 eventbus+bus tests | ✅ |
| agora ↔ omo 解循环 | ✅ |
| ruff lint | ✅ |

## Phase A.1 剩余 (R58 末目标)

1. 加 4 个 backend (sse / ws / realtime / cron_daemon) — 各 ~80 行
2. 切 omo_sse_daemon → `from agora.bus import subscribe`
3. 切 metaos/workflow.py → `from agora.bus import publish` (RED gate SSE)
4. 切 cron_service → `from agora.bus import schedule`
5. 全仓回归 (1105+ tests) + 写 5 硬条件监测脚本
6. evidence 落盘
