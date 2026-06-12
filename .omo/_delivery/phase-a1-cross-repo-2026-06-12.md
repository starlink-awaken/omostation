# Phase A.1 (R58) Cross-Repo Integration Evidence

> Date: 2026-06-12
> Author: 老王

## 跨仓 facade 真跑通 (4/4 项目)

| 项目 | 之前 | 现在 | 证据 |
|------|------|------|------|
| **agora** | 自家 bus | 自家 bus (1 backend) | `uv run python -m examples.bus_demo_publisher` ✅ |
| **omo** | ❌ 无 agora 依赖 | ✅ agora one-way dep + adapter | `uv run python -m omo.bus_demo_omo_producer` ✅ |
| **metaos** | ❌ 无 agora 依赖 | ✅ agora one-way dep + adapter | `from metaos.metaos_bus_adapter import publish_node_event` ✅ |
| **runtime** | ❌ 无 agora 依赖 | ✅ agora one-way dep + adapter | `from runtime.runtime_bus_adapter import register_cron_job` ✅ |

## 4 个跨仓 commit

| 仓 | SHA | 描述 |
|----|-----|------|
| agora | `4f42a78` | drop phantom omo dep (解循环 2 行) |
| omo | `b250cfe` | add agora workspace dep + bus_demo_omo_producer |
| omo | `8a4bfd1` | add omo_bus_adapter (sse_daemon bridge) |
| metaos | `6bd2987` | add metaos_bus_adapter (workflow events bridge) |
| runtime | `d22ff14` | add agora workspace dep + runtime_bus_adapter |

## agora ↔ omo 循环 (Architect 方案 3 验证)

**0 Python imports** of omo in agora source — 删 2 行 pyproject 假依赖, 解循环.
- Line 32 `"omo",` — removed
- Line 86 `omo = { path = "../omo", editable = true }` — removed
- Test: `grep -rn "from omo\|import omo" projects/agora/src` → 0 matches

## 系统一致性 (Architect 评分自评)

- ✅ agora 不再假装依赖 omo (诚实)
- ✅ omo/metaos/runtime 单向依赖 agora (无循环)
- ✅ legacy daemon (omo_sse_daemon) **不动** — 新增薄 adapter 加 facade 层
- ✅ legacy workflow (metaos) **不动** — adapter demo-only, R58+ 切换待评估
- ✅ legacy cron_service (runtime) **不动** — adapter 暴露 schedule

## Phase A.1 完整 commit (agora 仓, 7 commit)

```
de58709 evidence(bus): Phase A.1 milestone
2fd10f0 feat(bus): implement schedule() + multi-backend dispatch
b210aa4 feat(bus): CroniterBackend + MessageBusBackend
a40c697 feat(bus): AsyncioBackend + 4 tests
4f42a78 refactor(agora): drop phantom omo dep
1a3f34e evidence(bus): Phase A.0 completion
9c98d97 docs(agora): §bus subpackage
```

## 验证

```bash
$ cd projects/omo && uv run python -m omo.bus_demo_omo_producer
omo demo event published: evt_1781238459_027d2a

$ cd projects/metaos && uv run python -c "from metaos.metaos_bus_adapter import publish_node_event; print(publish_node_event('wf', 'n', 'completed'))"
evt_1781238843_c23a16

$ cd projects/runtime && uv run python -c "from runtime.runtime_bus_adapter import register_cron_job; register_cron_job('every 1h', lambda: None); print('OK')"
OK

$ cd projects/agora && uv run pytest tests/test_bus_*.py -q
22 passed, 2 warnings in 0.49s
```

## 下一步 (Phase A.1 末目标)

- [ ] 加 4 个 backend (sse/ws/realtime/cron_daemon) — 可选
- [ ] R58 末全仓回归 (1105+ agora tests + omo/metaos/runtime 全测)
- [ ] 5 硬条件监测脚本 (`scripts/check-bus-hard-conditions.sh`)
- [ ] Phase A.1 完整 evidence 落盘
- [ ] R59-R62 沉淀期启动 (4 月)
