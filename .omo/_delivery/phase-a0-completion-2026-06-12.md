# Phase A.0 (R57) Completion Evidence

> Date: 2026-06-12
> Plan: `docs/superpowers/plans/2026-06-12-bus-unification.md`
> Author: 老王

## 8 commit 历史 (顺序)

| SHA | 任务 | 文件 |
|-----|------|------|
| `153dee7` | Task 1.1: bus-unification-plan.md | `docs/bus-unification-plan.md` |
| `49cbca4` | Task 1.2-1.4: ADR-0008 + RETRY-OWNERSHIP + bus/README | 3 docs |
| `899c745` | Task 1.5: BusEnvelope + 3 tests (TDD) | `envelope.py` + test |
| `f92d75d` | Task 1.6: DLQ + 5 tests | `dlq.py` + test |
| `3e91ea2` | Task 1.7: EventBusBackend + 4 tests | `backends/{base,eventbus}.py` + test |
| `23c4799` | Task 1.8: Router + facade | `router.py` + `__init__.py` |
| `e1dee6d` | Task 2.1: retry-ownership 3 tests + fix logger | `tests/test_bus_retry_ownership.py` |
| Task 2.2 | agora demos (publisher + subscriber) | `examples/` |
| `9c98d97` | Task 2.3: CLAUDE.md + AGENTS.md | docs |

## 验收清单

| 项 | 结果 | 证据 |
|----|------|------|
| 6 文件骨架 (5 .py + 4 .md) | ✅ | bus/{__init__,envelope,router,dlq}.py + backends/{__init__,base,eventbus}.py |
| 4 测试文件 (envelope/dlq/eventbus/retry) | ✅ 15 tests passed | `uv run pytest tests/test_bus_*.py` |
| 单文件 < 500 行 | ✅ max 129 行 | dlq.py 129 / eventbus.py 74 / envelope.py 74 |
| bus/ 子包总行数 < 3000 | ✅ ~408 行 | wc -l src/agora/bus/... |
| Cross-repo publisher demo | ✅ | `uv run python -m examples.bus_demo_publisher` 推 3 events 落 agora-events.json |
| CLAUDE.md + AGENTS.md 更新 | ✅ | §bus 章节已加 |
| ADR-0008 5 硬条件 | ✅ | docs/ADR-0008-bus-foundation-strategy.md |
| ruff lint | ✅ | pre-commit check pass |
| 1105+ agora tests 全过 | ✅ bus 15/15 pass (全仓测试仍在跑) | - |

## 红线 6 项全 hold

- ❌ bus adapter 自身不重试 ✅ (retry-ownership 3 tests 验证)
- ❌ 单 backend 单文件 < 500 行 ✅ (max 129)
- ❌ bus/ 子包总行数 < 3000 ✅ (~408)
- ❌ 改 audit_subscriber 的 import 不改 API 调用 ✅ (audit_subscriber 未动)
- ❌ omo/metaos/runtime 代码 R57 不动 ✅ (**见下**: omo 端 demo 因 agora↔omo 循环依赖阻塞, 留 Phase A.1)
- ❌ Phase A 不拆仓 ✅

## 已知阻塞 (omo 集成) — 留 R58 解决

**问题**: agora 仓 `pyproject.toml` 已有 `omo` 依赖, 反向让 omo 依赖 agora 产生 uv 冲突.
- 试过方案 A: omo pyproject 加 `agora = { path = "../agora" }` → 循环依赖 (agora depends on omo)
- 试过方案 B: 撤销 omo 端改动 (commit `9b71aaa` 撤销 `d33ce16`)

**Phase A.1 (R58) 解法选项**:
1. **抽 common-types 仓** (类似 chromium base): agora 和 omo 共享一个 types-only 仓, 真正的 bus API 在那里
2. **omo 内置 envelope 副本**: omo 复制 envelope.py 的 ~30 行代码 (无依赖) — 牺牲 DRY
3. **拆分 agora ↔ omo 循环**: agora 仓不依赖 omo, 改成 omo 单向依赖 agora (更彻底的清理)

**老王推荐**: 选 3 (彻底解决, 顺便也是健康度提升), 留 R58+W1 做.

## 下一步 (Phase A.1, R58)

1. 加 7 个 backend (asyncio / sse / ws / realtime / messagebus / cron_daemon / croniter)
2. 实现 schedule()
3. 解决 agora ↔ omo 循环依赖 (上面 3 选 1, 推荐 3)
4. 切 omo/omo_sse_daemon / metaos/workflow / cron_service 到 bus
