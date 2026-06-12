# CLAUDE.md — bus-foundation

> Standalone Python package providing the unified bus interface for omostation.
> Split from `agora/bus/` in Phase B (R66) per ADR-0008.1.

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
| `src/bus_foundation/backends/eventbus.py` | in-process pubsub (无 agora 依赖) | 替代 agora 的 premium 版本 |
| `src/bus_foundation/backends/asyncio.py` | asyncio.Queue pubsub | - |
| `src/bus_foundation/backends/croniter.py` | cron 风格调度 | - |
| `src/bus_foundation/backends/messagebus.py` | agent 通信 pub/sub | - |
| `src/bus_foundation/backends/sse.py` | in-process fan-out | HTTP 层自接 |

## 快速命令

```bash
uv sync                                    # 安装 dev 依赖
uv run pytest -q                           # 32 tests
uv run ruff check src tests                # lint
uv run ruff format --check src tests       # format check
```

## 关键约束 (R66+)

1. **零 agora 依赖**: `grep -r "from agora" src/bus_foundation/` 必须返回 0 行
2. **单文件 < 500 行** (per ADR-0008): `find src -name '*.py' -exec wc -l {} \;`
3. **公共 API 冻结 6 个月**: 任何破坏性变更必须走 ADR

## 与 agora.bus 的关系

agora 项目的 `agora/bus/` 子包**继续存在**,作为 agora-specific premium backends
(持久化 EventBus + 全局 sse_manager) 的所在地。消费者可选:

```python
# 跨仓共用 (默认推荐): 零 agora 依赖
from bus_foundation import publish, BusEnvelope

# agora 增强: 持久化 event log + 全局 SSE manager
from agora.bus import publish, BusEnvelope  # agora-only
```

## 5 硬条件 (迁移触发, ADR-0008)

bus-foundation 接收 7 仓内采用 (omo, metaos, runtime, aetherforge, kairon-pipeline,
llm-gateway, hermes-console) 作为 Condition 4 (eCOS-external usage) 的代理。
详细条件见 `/Users/xiamingxing/Workspace/projects/agora/docs/ADR-0008-bus-foundation-strategy.md`。

## Phase C 决策 (R70-R72, 2027-07 → 2027-09)

**Phase C 评估结果: Path C (Defer Indefinitely)** — bus-foundation 不提升到 L0 协议层,
继续保持 standalone repo 状态。

触发再评估的条件 (5 硬条件中 Condition 4 真正外部采用时):
- 0 → 1 个 external issue / PR referencing bus-foundation
- 0 → 1 个 academic citation
- 0 → 2 个 distinct organizations using as dep

详见:
- `docs/ADR-0002-phase-c-trigger-reality-DRAFT.md` — 3 路径分析
- `.omo/_delivery/r70-monthly-evidence-2027-07-12.md` — R70 audit
- `.omo/_delivery/r71-phase-c-recommendation-memo.md` — R71 推荐
- `.omo/_delivery/r72-final-retrospective-2027-09-12.md` — R72 retrospective

**未来改进走普通 feature work (bug fix / 新 backend / 新 helper),不经过 Phase D governance gate。**
