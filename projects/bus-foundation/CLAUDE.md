# CLAUDE.md — bus-foundation

> Standalone Python package providing the unified bus interface for omostation.
> Split from `agora/bus/` in Phase B (R66) per ADR-0008.

## Owner / Maintainers

- **Primary owner**: 夏 (Xia Mingxing)
- **Maintainers**: omostation bus-foundation team (see `OWNERS.md`)
- **Decision protocol**: see `OWNERS.md` (1 reviewer for patch, 2 for minor, 2+ADR for major)

## 项目身份

bus-foundation 是 eCOS 跨项目共用的事件总线基础库。它的关键边界:

- **零 agora 依赖**: 不能 `import agora` (除可选 premium backends 文档中说明的 opt-in)
- **零外部依赖**: 仅 pydantic + stdlib (sqlite3, threading, asyncio, json)
- **单一公共 API**: `publish`, `subscribe`, `schedule`, `BusEnvelope`, `EventType`

## 文件职责

| 文件 | 职责 | 风险 |
|------|------|------|
| `src/bus_foundation/__init__.py` | facade (publish/subscribe/schedule) | 单文件 < 120 行 |
| `src/bus_foundation/envelope.py` | BusEnvelope wire format | schema 冻结 |
| `src/bus_foundation/router.py` | backend 分发 + DLQ fallback | 路由逻辑集中点 |
| `src/bus_foundation/dlq.py` | SQLite DLQ (WAL + 50MB GC) | 落 `~/.runtime/bus_dlq.db` |
| `src/bus_foundation/backends/base.py` | BusBackend Protocol | - |
| `src/bus_foundation/backends/pattern_match.py` | **R74 共享 helper** (6 backend delegate) | - |
| `src/bus_foundation/backends/eventbus.py` | in-process pubsub (无 agora 依赖) | 替代 agora 的 premium 版本 |
| `src/bus_foundation/backends/asyncio.py` | asyncio.Queue pubsub | - |
| `src/bus_foundation/backends/croniter.py` | cron 风格调度 | - |
| `src/bus_foundation/backends/messagebus.py` | agent 通信 pub/sub | - |
| `src/bus_foundation/backends/sse.py` | in-process fan-out | HTTP 层自接 |
| `src/bus_foundation/backends/ws.py` | **R73 新增** full-duplex | - |
| `src/bus_foundation/backends/realtime.py` | **R73 新增** versioned task events | - |
| `src/bus_foundation/backends/persistent_bus.py` | **R73 新增** SQLite durable | - |
| `tests/` | 56 tests, 100% pass (R75) | - |

## 快速命令

```bash
uv sync                                    # 安装 dev 依赖
uv run pytest -q                           # 56 tests (R75)
uv run ruff check src tests                # 0 errors (R75 后)
uv run ruff format --check src tests       # format check
bash scripts/check-bus-hard-conditions.sh   # 5 hard conditions monitor
```

## 关键约束 (R75 update)

1. **零 agora 依赖**: `grep -r "from agora" src/bus_foundation/` 必须返回 0 行
2. **单文件 < 500 行** (per ADR-0008): `find src -name '*.py' -exec wc -l {} \;`
3. **公共 API 冻结 6 个月**: 任何破坏性变更必须走 ADR
4. **`collections.abc` only** (R75): `from collections.abc import Callable` 等,
   **不要** `from typing import Callable` (UP035)
5. **Backend 自身不重试** (RETRY-OWNERSHIP.md)
6. **`match_pattern` 唯一**: 所有 backend delegate, **不要**重写 `_match` (R74 simplify)

## 与 agora.bus 的关系

agora 项目的 `agora/bus/` 子包**继续存在**,作为 agora-specific premium backends
(持久化 EventBus + 全局 sse_manager) 的所在地。消费者可选:

```python
# 跨仓共用 (默认推荐): 零 agora 依赖
from bus_foundation import publish, BusEnvelope

# agora 增强: 持久化 event log + 全局 SSE manager
from agora.bus import publish, BusEnvelope  # agora-only
```

## 5 硬条件 (ADR-0008, frozen 6 个月)

bus-foundation 接收 7 仓内采用 (omo, metaos, runtime, aetherforge, kairon-pipeline,
llm-gateway, hermes-console) 作为 Condition 4 (eCOS-external usage) 的代理。
详细条件见 `/Users/xiamingxing/Workspace/projects/agora/docs/ADR-0008-bus-foundation-strategy.md`。

## Phase A-C 状态 (R57-R72, closed)

- **Phase A (R57-R65)**: 9 月 沉淀 + 治理 → bus facade in agora + 7 仓采纳
- **Phase B (R66-R69)**: 4 月 拆 bus-foundation 独立仓 + 7 消费者迁移
- **Phase C (R70-R72)**: 3 月 Path C Defer (no L0 提升, 1-way ratchet 不适用)

## Phase D 决策 (R72 final, frozen)

**Phase D 永不开**. bus-foundation 是普通 standalone repo, 未来改进走:
- 普通 feature work (bug fix, new backend, new helper)
- 普通 patch release (0.1.x → 0.1.x+1)
- 任何"提升到 L0 协议层"建议需新 ADR + 5 硬条件全 PASS (现 1/5 未真 PASS,
  仅 proxy 修订)

详见 `.omo/_delivery/r72-final-retrospective-2027-09-12.md` 和
`docs/GOVERNANCE.md` §"What bus-foundation is NOT"。

## 后续改进 (backlog)

- 0.1.x patch: R75-UP035-batch (re-verify 0 warnings)
- 0.1.x patch: Performance LOW fixes (R74 simplify 留的 2 项)
- 0.2.0: NOT planned (frozen public API)
- Phase D: NOT planned (per R72 decision)

详见 `CHANGELOG.md` §"Backlog"。
