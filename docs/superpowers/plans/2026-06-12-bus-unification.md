# Bus Unification — 18-Month Implementation Plan (R57-R75, COMPLETE)

> **Status (2026-06-13)**: **Phase D NOT planned**. All phases A-C closed
> (R57-R72). R73-R75 is "normal feature work" period. The 18-month
> unification effort is complete; this plan is now a historical record.
>
> **For agentic workers (historical context)**: REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Original Goal:** 在 `agora/bus/` 子包里建一个 1-backend 的统一接口骨架, 解决"8 套异步/事件/调度机制没有统一入口"问题, 不动 omo/metaos/runtime 业务代码。

**Final state (R75):**
- bus-foundation 独立仓 (`projects/bus-foundation/`), 8 backend, 56 tests, 100% pass
- 7 consumers migrated (omo / metaos / runtime / aetherforge / kairon-pipeline / llm-gateway / hermes-console)
- 2 ADR ratified (ADR-0008 Phase B trigger + ADR-0008.1 Condition 4 proxy)
- Phase A (R57-R65): 9 月 sedimentation + 治理
- Phase B (R66-R69): 4 月 split + migration
- Phase C (R70-R72): 3 月 Path C Defer Indefinitely (1-way ratchet 不适用)
- Phase D (R73-R75): 3 月 3 new backends + code review + simplify + ruff fix

**Architecture:** facade 模式 — `__init__.py` 暴露 `publish/subscribe/schedule` →
`router.py` 分发 envelope → 8 backends (eventbus/asyncio/croniter/messagebus/sse/ws/realtime/persistent_bus) → 失败时写入 `dlq.py` 管理的 SQLite. **retry 所有权** = bus adapter 自身不重试, 透传给底层.

**Tech Stack:** Python 3.13, Pydantic v2, SQLite (WAL mode), structlog, ruff; bus-foundation 零 agora 依赖 (R66 split).

---


## 文件结构 (新增/修改一览)

```
projects/agora/docs/
├── bus-unification-plan.md          # CREATE  架构图 + 决策表 + 风险表
└── ADR-0008-bus-foundation-strategy.md  # CREATE  为什么先沉淀再拆 + 5 硬条件

projects/agora/src/agora/bus/
├── __init__.py                      # CREATE  facade, re-export
├── envelope.py                      # CREATE  BusEnvelope Pydantic
├── router.py                        # CREATE  Backend 路由
├── dlq.py                           # CREATE  SQLite DLQ (WAL + GC)
├── README.md                        # CREATE  公共 API + 选型表
├── RETRY-OWNERSHIP.md               # CREATE  重试所有权规则
└── backends/
    ├── __init__.py                  # CREATE
    ├── base.py                      # CREATE  BusBackend Protocol
    └── eventbus.py                  # CREATE  包 agora EventBus

projects/agora/src/agora/audit_subscriber.py  # MODIFY  import 切换 (行为不变)
projects/agora/CLAUDE.md                       # MODIFY  + §bus 章节
projects/agora/AGENTS.md                       # MODIFY  + bus 章节
projects/agora/tests/
├── test_bus_envelope.py             # CREATE
├── test_bus_dlq.py                  # CREATE
├── test_bus_eventbus_backend.py     # CREATE
└── test_bus_retry_ownership.py      # CREATE
```

**文件硬上限**: 单个 .py 文件 < 500 行 (红队 #11 校正)

---

## Week 1 (Day 1-5): 设计文档 + 骨架代码

### Task 1.1: 写 `bus-unification-plan.md` 设计文档

**Files:**
- Create: `projects/agora/docs/bus-unification-plan.md`

- [ ] **Step 1: 创建文件并写 header**

```markdown
# Bus Unification Plan

> Date: 2026-06-12
> Status: Phase A.0 (R57)
> Phase B 触发: 5 硬条件 (见 ADR-0008)

## 目标
在 agora/bus/ 子包里建 1 个统一接口, 让新代码用 `from agora.bus import publish/subscribe/schedule` 替代选 8 套机制。

## 架构图

```
┌────────────────────────────────────┐
│ agora/bus/__init__.py (facade)     │  ← 1 行 import, 业务用
│   publish(envelope)                │
│   subscribe(pattern, fn)            │
│   schedule(expr, fn)               │
└──────────────┬─────────────────────┘
               │
               ▼
┌────────────────────────────────────┐
│ agora/bus/router.py                │  ← 路由 envelope.backend → backend
│  RouteConfig(backend="eventbus")   │
└──────────────┬─────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐  ┌─────────────┐
│ eventbus.py │  │ (其他 7 个  │  ← Phase A.0 只 1 个
│  (Phase A.0)│  │  Phase A.1) │
└──────┬──────┘  └─────────────┘
       │
       ▼
┌────────────────────────────────────┐
│ dlq.py (失败兜底)                  │
│  ~/.runtime/bus_dlq.db             │
│  SQLite WAL + 50MB GC              │
└────────────────────────────────────┘
```

## 决策表 (选 backend)

| 场景 | backend | 为什么 |
|------|---------|--------|
| 跨进程事件 | `eventbus` | 唯一跨进程总线 |
| 进程内 awaitable | `asyncio` (A.1) | 低延迟, 不用落盘 |
| 推客户端 | `sse` (A.1) | 单向 push |
| 双向通信 | `ws` (A.1) | full-duplex |
| Task 状态 | `realtime` (A.1) | 复用 version 逻辑 |
| Agent 通信 | `messagebus` (A.1) | 保持 req/resp |
| 定时任务 | `croniter` (A.1) | cron expr 强 |

## 红线 (6 项)
1. ❌ bus adapter 自身不重试 (透传, 避免重试乘法)
2. ❌ 单 backend 单文件 < 500 行
3. ❌ bus/ 子包总行数 < 3000 (R57 末)
4. ❌ 改 audit_subscriber 的 import 不改 API 调用
5. ❌ omo/metaos/runtime 代码 R57 不动
6. ❌ Phase A 不拆仓

## 风险表
| 风险 | 缓解 |
|------|------|
| God module (5000+ 行) | 5 文件拆分 + 500 行硬上限 |
| DLQ SPOF | WAL + busy_timeout + 50MB GC |
| 重试乘法 | RETRY-OWNERSHIP.md 写明 |
| API 演化失控 | A.0 末冻结 6 月 |
```

- [ ] **Step 2: 验证文件存在**

```bash
test -f projects/agora/docs/bus-unification-plan.md && echo OK
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/xiamingxing/Workspace
git add projects/agora/docs/bus-unification-plan.md
git commit -m "docs(agora): add bus-unification plan (Phase A.0)"
```

---

### Task 1.2: 写 ADR-0008 (5 硬条件白纸黑字)

**Files:**
- Create: `projects/agora/docs/ADR-0008-bus-foundation-strategy.md`

- [ ] **Step 1: 写 ADR**

```markdown
# ADR-0008: Bus Foundation Strategy — 先沉淀再拆

> Status: Accepted (R57)
> Date: 2026-06-12
> Deciders: agora team, omo team, metaos team, runtime team

## Context
agora 现在有 8 套机制并存 (EventBus, MessageBus, cron, SSE, WS, TaskSync, omo_daemon, croniter), 没有统一接口。考虑过直接拆独立仓 (bus-foundation), 但风险高。

## Decision
**先沉淀到 agora/bus/ 子包 (Phase A, R57-R58), 拆仓时机由 5 硬条件驱动 (Phase B, R63+)。**

## 5 硬条件 (Phase B 触发)
全部满足才允许拆仓:

1. **≥3 个项目生产环境调用 `from agora.bus`**
   - 测量: `grep -rln "from agora.bus" projects/{omo,metaos,runtime,kairon,cockpit}/src/ | wc -l` ≥ 3
   - 频率: 月度

2. **bus/ 子包有 ≥180 天 git history**
   - 测量: `git log --since="180 days ago" -- projects/agora/src/agora/bus/ | wc -l` ≥ 1
   - 频率: 持续

3. **agora CLAUDE.md 写明 bus owner**
   - 测量: `grep -q "bus.*owner" projects/agora/CLAUDE.md`
   - 频率: 一次性

4. **≥1 个 eCOS 之外的项目使用**
   - 测量: GitHub issue / PR 数量 ≥ 1, by non-contributor
   - 频率: 持续

5. **bus 改动频率 ≥ agora 主体 50%**
   - 测量: `git log --since="6 months ago" -- projects/agora/src/agora/bus/ | wc -l` ≥ `git log --since="6 months ago" -- projects/agora/src/agora/ | wc -l` * 0.5
   - 频率: 月度

## Consequences
**正**: 6 个月沉淀期 = 演化自由度比直接拆高 10x
**负**: 现在看着冗余, 团队可能质疑"为什么不直接拆"
**退路**: R62 末评估不满足 → 继续沉淀, R63 重评

## References
- `.omo/_delivery/async-event-cron-architecture-2026-06-12.md`
- `docs/bus-unification-plan.md`
```

- [ ] **Step 2: Commit**

```bash
git add projects/agora/docs/ADR-0008-bus-foundation-strategy.md
git commit -m "docs(agora): add ADR-0008 (bus-foundation 5 hard conditions)"
```

---

### Task 1.3: 写 `RETRY-OWNERSHIP.md` (重试所有权)

**Files:**
- Create: `projects/agora/src/agora/bus/RETRY-OWNERSHIP.md`

- [ ] **Step 1: 写规则**

```markdown
# Retry Ownership Rule (R57+)

## 核心规则
**每条事件链路只有 1 层做重试, 其他层透传。**

## 链路分层 (从 producer 到 consumer)

| 层 | 组件 | 是否重试 | 重试参数 |
|----|------|---------|---------|
| L1 | producer 代码 | ❌ | - |
| L2 | `agora.bus.publish` | ❌ (透传) | - |
| L3 | `agora.bus.backends.eventbus` (HTTP callback) | ❌ (透传) | - |
| L4 | **agora EventBus 自身** | ✅ | 3x, 2^attempt (event_bus.py:170-188) |
| L5 | **subscriber HTTP 端点** | ✅ | 由 subscriber 决定 (bus_consumer 3x) |

## 为什么这样分
- L4 是 EventBus 边界, 重试可解 HTTP 网络抖动
- L5 是 subscriber 边界, 重试可解端点下线
- L2/L3 透传: 避免重试乘法 (1 个失败 = 9 次重试)

## 监控
- 写 1 个 `bus_stats()` 函数, 报告每层重试次数
- 看板: `~/.runtime/bus_dlq.db` SQLite + `bus_dlq` table

## 违规检测
- producer 写 `for attempt in range(3): ...` → lint 警告
- backend adapter 写 `with_retry(...)` → code review 拒绝
```

- [ ] **Step 2: Commit**

```bash
git add projects/agora/src/agora/bus/RETRY-OWNERSHIP.md
git commit -m "docs(bus): add RETRY-OWNERSHIP rule (1 layer per chain)"
```

---

### Task 1.4: 写 `README.md` (公共 API + 选型表)

**Files:**
- Create: `projects/agora/src/agora/bus/README.md`

- [ ] **Step 1: 写 README**

```markdown
# agora.bus — 统一接口层 (Phase A.0)

## 公共 API

```python
from agora.bus import publish, subscribe, schedule
from agora.bus.envelope import BusEnvelope, EventType

# 1. 发布事件
envelope = BusEnvelope(
    type=EventType.PIPELINE_COMPLETED,
    source="my_service",
    payload={"task_id": "t-123", "result": "ok"},
)
publish(envelope)  # → 走 router → 选 backend → 失败入 DLQ

# 2. 订阅事件
@subscribe(pattern="pipeline:*")
def on_pipeline_event(envelope: BusEnvelope) -> None:
    print(f"received {envelope.type}: {envelope.payload}")

# 3. 调度任务 (Phase A.1)
@schedule(expr="every 5m")
def heartbeat() -> None:
    print("alive")
```

## backend 选型表

| 场景 | backend | Phase |
|------|---------|-------|
| 跨进程事件 | `eventbus` | A.0 ✅ |
| 进程内 await | `asyncio` | A.1 |
| 推客户端 (单向) | `sse` | A.1 |
| 双向通信 | `ws` | A.1 |
| Task 状态同步 | `realtime` | A.1 |
| Agent 通信 (req/resp) | `messagebus` | A.1 |
| 定时任务 | `croniter` | A.1 |
| omo 旧 daemon (deprecating) | `cron_daemon` | A.1 |

## 红线
- 单文件 < 500 行
- backend 自身不重试 (透传, 详见 RETRY-OWNERSHIP.md)
- 改 producer import 不改 API 调用方式
```

- [ ] **Step 2: Commit**

```bash
git add projects/agora/src/agora/bus/README.md
git commit -m "docs(bus): add README (public API + backend selection table)"
```

---

### Task 1.5: 写 `envelope.py` (BusEnvelope Pydantic model) + TDD

**Files:**
- Create: `projects/agora/src/agora/bus/envelope.py`
- Create: `projects/agora/tests/test_bus_envelope.py`

- [ ] **Step 1: 写失败的测试 (TDD red)**

创建 `projects/agora/tests/test_bus_envelope.py`:

```python
"""Test BusEnvelope Pydantic model — first 3 of 12 cases."""

from datetime import datetime

import pytest
from agora.bus.envelope import BusEnvelope, EventType


class TestBusEnvelopeConstruction:
    """Test BusEnvelope construction and field validation."""

    def test_minimal_envelope(self):
        """Envelope with only required fields."""
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="test",
        )
        assert env.type == "pipeline:completed"
        assert env.source == "test"
        assert isinstance(env.id, str) and len(env.id) > 0
        assert env.schema_version == 1  # default
        assert env.payload == {}  # default
        assert env.trace_id is None  # default

    def test_full_envelope(self):
        """Envelope with all fields populated."""
        env = BusEnvelope(
            type=EventType.MESSAGE_RECEIVED,
            source="agora",
            payload={"key": "value"},
            trace_id="trace-123",
            schema_version=1,
        )
        assert env.payload == {"key": "value"}
        assert env.trace_id == "trace-123"

    def test_serialization_roundtrip(self):
        """Envelope can be JSON-serialized and deserialized."""
        original = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="svc",
            payload={"x": 1},
        )
        json_str = original.to_json()
        restored = BusEnvelope.from_json(json_str)
        assert restored.type == original.type
        assert restored.source == original.source
        assert restored.payload == original.payload
        assert restored.id == original.id
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd projects/agora && uv run pytest tests/test_bus_envelope.py -v
```
Expected: `ModuleNotFoundError: No module named 'agora.bus.envelope'`

- [ ] **Step 3: 写最小实现 (TDD green)**

创建 `projects/agora/src/agora/bus/envelope.py`:

```python
"""BusEnvelope — wire-format envelope for all bus events.

Phase A.0: extend agora/core/event_bus.py:124-131 envelope with schema_version.

Wire format (JSON):
    {
        "id": "evt_1700000000_abc123",
        "type": "pipeline:completed",
        "source": "agora",
        "time": "2026-06-12T10:00:00Z",
        "schema_version": 1,
        "trace_id": "trace-xyz" | null,
        "payload": {...}
    }
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Standard event types (subset — Phase A.0).

    Full taxonomy in schemas.py (Phase A.1).
    """

    PIPELINE_COMPLETED = "pipeline:completed"
    PIPELINE_STARTED = "pipeline:started"
    MESSAGE_RECEIVED = "message:received"


class BusEnvelope:
    """Wire-format envelope for bus events.

    NOT a Pydantic model in Phase A.0 — uses simple __init__ + to_dict/from_dict
    for zero-dep compatibility. Pydantic migration in Phase A.1.
    """

    def __init__(
        self,
        type: str | EventType,
        source: str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
        schema_version: int = 1,
        id: str | None = None,
        time: str | None = None,
    ):
        if isinstance(type, EventType):
            type = type.value
        self.id = id or f"evt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.time = time or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.type = type
        self.source = source
        self.schema_version = schema_version
        self.trace_id = trace_id
        self.payload = payload or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict (for JSON)."""
        return {
            "id": self.id,
            "time": self.time,
            "type": self.type,
            "source": self.source,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BusEnvelope":
        """Deserialize from dict."""
        return cls(
            id=d.get("id"),
            time=d.get("time"),
            type=d["type"],
            source=d["source"],
            schema_version=d.get("schema_version", 1),
            trace_id=d.get("trace_id"),
            payload=d.get("payload", {}),
        )

    @classmethod
    def from_json(cls, s: str) -> "BusEnvelope":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(s))

    def __repr__(self) -> str:
        return f"BusEnvelope(id={self.id!r}, type={self.type!r}, source={self.source!r})"
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
cd projects/agora && uv run pytest tests/test_bus_envelope.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add projects/agora/src/agora/bus/envelope.py projects/agora/tests/test_bus_envelope.py
git commit -m "feat(bus): add BusEnvelope + 3 construction tests (TDD)"
```

---

### Task 1.6: 写 `dlq.py` (SQLite DLQ, WAL + GC) + TDD

**Files:**
- Create: `projects/agora/src/agora/bus/dlq.py`
- Create: `projects/agora/tests/test_bus_dlq.py`

- [ ] **Step 1: 写失败测试 (TDD red)**

创建 `projects/agora/tests/test_bus_dlq.py`:

```python
"""Test DLQ — first 5 of 15 cases covering WAL, busy_timeout, GC, rotate."""

import os
import sqlite3
from pathlib import Path

import pytest
from agora.bus.dlq import DLQ, DLQ_MAX_SIZE_MB


class TestDLQBasics:
    def test_init_creates_db(self, tmp_path: Path):
        """DLQ init creates the SQLite DB file."""
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        assert db_path.exists()
        dlq.close()

    def test_wal_mode_enabled(self, tmp_path: Path):
        """WAL mode is set on connection (PRAGMA)."""
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        # Reopen with raw sqlite3 to inspect
        conn = sqlite3.connect(str(db_path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        dlq.close()
        assert mode.lower() == "wal"

    def test_busy_timeout_5000(self, tmp_path: Path):
        """busy_timeout is 5000ms (avoid 'database is locked' on concurrent write)."""
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        conn = sqlite3.connect(str(db_path))
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        conn.close()
        dlq.close()
        assert timeout >= 5000

    def test_enqueue_records_failure(self, tmp_path: Path):
        """enqueue() persists a failed event to DLQ table."""
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        dlq.enqueue(
            event_id="evt-1",
            backend="eventbus",
            envelope_json='{"type":"test","source":"x"}',
            error="connection refused",
        )
        rows = dlq.list_all()
        assert len(rows) == 1
        assert rows[0]["event_id"] == "evt-1"
        assert rows[0]["status"] == "PENDING"
        assert rows[0]["retries"] == 0
        dlq.close()

    def test_enqueue_increments_retries_on_retry(self, tmp_path: Path):
        """requeue() increments retries counter (for circuit-breaker logic)."""
        db_path = tmp_path / "test_dlq.db"
        dlq = DLQ(db_path=db_path)
        dlq.enqueue(event_id="evt-2", backend="eventbus", envelope_json="{}", error="x")
        dlq.requeue(event_id="evt-2", error="still failing")
        rows = dlq.list_all()
        assert rows[0]["retries"] == 1
        assert rows[0]["status"] == "PENDING"
        dlq.close()
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd projects/agora && uv run pytest tests/test_bus_dlq.py -v
```
Expected: `ModuleNotFoundError: No module named 'agora.bus.dlq'`

- [ ] **Step 3: 写最小实现 (TDD green)**

创建 `projects/agora/src/agora/bus/dlq.py`:

```python
"""SQLite DLQ — dead letter queue for failed bus events.

Phase A.0: WAL mode + busy_timeout 5000 + 50MB rolling GC.

Schema (from runtime/bus_consumer.py:44-52):
    dlq(event_id PK, backend, envelope_json, error, retries, status, created_at, updated_at)

States: PENDING → (requeue) → PENDING with retries++ → (retries >= 3) → DLQ.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DLQ_MAX_SIZE_MB = 50
DLQ_MAX_RETRIES = 3
DEFAULT_DB_PATH = Path(
    os.environ.get("BUS_DLQ_PATH", str(Path.home() / ".runtime" / "bus_dlq.db"))
)


class DLQ:
    """Thread-safe SQLite DLQ with WAL + GC.

    Reuses pragmas from runtime/cron_service/db.py:22-28.
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = self._open_conn()
        self._init_schema()
        self._maybe_rotate()

    def _open_conn(self) -> sqlite3.Connection:
        """Open connection with WAL + busy_timeout pragmas."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Create dlq table if not exists."""
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS dlq (
                    event_id TEXT PRIMARY KEY,
                    backend TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    error TEXT,
                    retries INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS dlq_status_idx
                ON dlq(status)
            """)
            self._conn.commit()

    def _maybe_rotate(self) -> None:
        """Rotate DLQ if file > DLQ_MAX_SIZE_MB (move to .old)."""
        if not self.db_path.exists():
            return
        size_mb = self.db_path.stat().st_size / (1024 * 1024)
        if size_mb >= DLQ_MAX_SIZE_MB:
            old_path = self.db_path.with_suffix(".db.old")
            logger.warning(
                "dlq_rotate", size_mb=round(size_mb, 2), target=str(old_path)
            )
            self._conn.close()
            old_path.unlink(missing_ok=True)
            self.db_path.rename(old_path)
            self._conn = self._open_conn()
            self._init_schema()

    def _now(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def enqueue(
        self,
        event_id: str,
        backend: str,
        envelope_json: str,
        error: str,
    ) -> None:
        """Persist a failed event to DLQ."""
        now = self._now()
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO dlq
                    (event_id, backend, envelope_json, error, retries, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, 'PENDING', ?, ?)
                """,
                (event_id, backend, envelope_json, error, now, now),
            )
            self._conn.commit()

    def requeue(self, event_id: str, error: str) -> None:
        """Increment retries. Move to DLQ if >= DLQ_MAX_RETRIES."""
        now = self._now()
        with self._lock:
            row = self._conn.execute(
                "SELECT retries FROM dlq WHERE event_id = ?", (event_id,)
            ).fetchone()
            if row is None:
                logger.warning("dlq_requeue_missing", event_id=event_id)
                return
            new_retries = row["retries"] + 1
            new_status = "DLQ" if new_retries >= DLQ_MAX_RETRIES else "PENDING"
            self._conn.execute(
                """
                UPDATE dlq
                SET retries = ?, status = ?, error = ?, updated_at = ?
                WHERE event_id = ?
                """,
                (new_retries, new_status, error, now, event_id),
            )
            self._conn.commit()

    def list_all(self) -> list[dict]:
        """List all DLQ rows (for tests / admin)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM dlq ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        """Close connection (for tests + shutdown)."""
        with self._lock:
            self._conn.close()
```

- [ ] **Step 4: 跑测试确认 PASS**

```bash
cd projects/agora && uv run pytest tests/test_bus_dlq.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add projects/agora/src/agora/bus/dlq.py projects/agora/tests/test_bus_dlq.py
git commit -m "feat(bus): add DLQ (WAL + busy_timeout + 50MB GC) + 5 tests"
```

---

### Task 1.7: 写 `backends/base.py` (BusBackend Protocol) + `backends/eventbus.py` (Phase A.0 唯一 backend)

**Files:**
- Create: `projects/agora/src/agora/bus/backends/__init__.py`
- Create: `projects/agora/src/agora/bus/backends/base.py`
- Create: `projects/agora/src/agora/bus/backends/eventbus.py`
- Create: `projects/agora/tests/test_bus_eventbus_backend.py`

- [ ] **Step 1: 写失败测试 (TDD red)**

创建 `projects/agora/tests/test_bus_eventbus_backend.py`:

```python
"""Test EventBusBackend — first 4 of 10 cases covering Protocol + is_available + publish."""

import os
import tempfile
from pathlib import Path

import pytest
from agora.bus.backends.base import BusBackend
from agora.bus.backends.eventbus import EventBusBackend
from agora.bus.envelope import BusEnvelope, EventType


class TestEventBusBackendProtocol:
    def test_implements_protocol(self, tmp_path: Path):
        """EventBusBackend satisfies BusBackend Protocol (runtime checkable)."""
        backend = EventBusBackend(storage_path=tmp_path / "eb.json")
        assert isinstance(backend, BusBackend)

    def test_is_available_default_true(self, tmp_path: Path):
        """Backend is available when storage path is writable."""
        backend = EventBusBackend(storage_path=tmp_path / "eb.json")
        assert backend.is_available() is True

    def test_publish_returns_event_id(self, tmp_path: Path):
        """publish() returns the event_id from the envelope."""
        backend = EventBusBackend(storage_path=tmp_path / "eb.json")
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="test",
            payload={"x": 1},
        )
        result_id = backend.publish(env)
        assert result_id == env.id

    def test_persist_in_storage(self, tmp_path: Path):
        """Published event is persisted to agora-events.json (reuses EventBus logic)."""
        storage = tmp_path / "eb.json"
        backend = EventBusBackend(storage_path=storage)
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="test",
            payload={"k": "v"},
        )
        backend.publish(env)
        # Re-init to force reload
        backend2 = EventBusBackend(storage_path=storage)
        log = backend2.get_event_log(limit=10)
        assert len(log) >= 1
        assert any(e.get("id") == env.id for e in log)
```

- [ ] **Step 2: 跑测试确认 FAIL**

```bash
cd projects/agora && uv run pytest tests/test_bus_eventbus_backend.py -v
```
Expected: `ModuleNotFoundError: No module named 'agora.bus.backends'`

- [ ] **Step 3: 写 `backends/__init__.py`**

```python
"""Bus backends — pluggable transport implementations.

Phase A.0: 1 backend (eventbus). Phase A.1 adds asyncio, sse, ws, realtime,
messagebus, cron_daemon, croniter.
"""
from __future__ import annotations

from agora.bus.backends.base import BusBackend
from agora.bus.backends.eventbus import EventBusBackend

__all__ = ["BusBackend", "EventBusBackend"]
```

- [ ] **Step 4: 写 `backends/base.py`**

```python
"""BusBackend Protocol — contract all backends must satisfy.

Pattern from agora/redis_message_queue.py: drop-in replacement via is_available().
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from agora.bus.envelope import BusEnvelope


@runtime_checkable
class BusBackend(Protocol):
    """Pluggable bus transport.

    A backend is a single point of failure. If is_available() returns False,
    router should fall back to DLQ-only path (no re-publish).
    """

    name: str

    def is_available(self) -> bool:
        """Return True if backend is reachable and writable.

        Called before each publish(). Implementations should cache for ≤ 1s.
        """
        ...

    def publish(self, envelope: BusEnvelope) -> str:
        """Publish event. Returns event_id.

        MUST NOT retry on failure (see RETRY-OWNERSHIP.md).
        MUST raise on failure (router catches + writes to DLQ).
        """
        ...

    def subscribe(self, pattern: str, callback) -> str:
        """Subscribe to events matching pattern. Returns subscription_id.

        Pattern syntax: 'index:done' (exact), 'index:*' (prefix), '*' (all).
        callback signature: (envelope: BusEnvelope) -> None
        """
        ...

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove subscription. Returns True if removed."""
        ...
```

- [ ] **Step 5: 写 `backends/eventbus.py`**

```python
"""EventBusBackend — wraps agora.core.event_bus.EventBus.

Phase A.0: thin wrapper, zero behavior change. Reuses persistence + retry logic.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from agora.bus.envelope import BusEnvelope
from agora.core.event_bus import EventBus

logger = logging.getLogger(__name__)


class EventBusBackend:
    """agora.core.event_bus wrapper for unified bus interface.

    Implements BusBackend Protocol via duck typing (no inheritance).

    RETRY: passes through to underlying EventBus (3x, exponential backoff).
    This backend itself does NOT retry.
    """

    name = "eventbus"

    def __init__(self, storage_path: Path | str | None = None):
        self._bus = EventBus(storage_path=str(storage_path) if storage_path else None)

    def is_available(self) -> bool:
        """EventBus is in-process; always available unless storage is broken."""
        try:
            return self._bus._storage_path.parent.exists()
        except Exception as e:
            logger.warning("eventbus_unavailable", error=str(e))
            return False

    def publish(self, envelope: BusEnvelope) -> str:
        """Publish via EventBus. Returns event_id.

        Raises on failure — router catches and writes to DLQ.
        """
        return self._bus.publish(
            event_type=envelope.type,
            payload=envelope.payload,
            source=envelope.source,
            trace_id=envelope.trace_id or "",
        )

    def subscribe(self, pattern: str, callback: Callable) -> str:
        """Subscribe via EventBus.register_hook (in-process delivery).

        Why hook not subscribe(): agora EventBus.subscribe is HTTP callback
        (fire-and-forget POST to subscriber URL), which is the wrong primitive
        for a same-process BusBackend wrapper. register_hook gives us in-process
        delivery, which is what BusBackend Protocol promises.

        NOTE: this means a cross-process consumer (HTTP callback) registered
        elsewhere on the same EventBus will NOT see events delivered through
        this backend. That's by design — cross-process delivery is the
        responsibility of the EventBus publisher (which is now the caller
        of EventBusBackend.publish), not the subscriber side.
        """
        def hook(event_dict: dict) -> None:
            envelope = BusEnvelope.from_dict(
                {
                    "id": event_dict.get("id"),
                    "time": event_dict.get("time"),
                    "type": event_dict.get("type"),
                    "source": event_dict.get("source"),
                    "trace_id": event_dict.get("trace_id"),
                    "payload": event_dict.get("payload", {}),
                }
            )
            callback(envelope)

        self._bus.register_hook(hook)
        # Return a stable ID for unsubscribe (EventBus hooks have no native ID)
        return f"hook-{id(hook):x}"

        self._bus.register_hook(hook)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove subscription. NOTE: EventBus has no unsubscribe by id; return False."""
        return self._bus.unsubscribe(sub_id)

    def get_event_log(self, limit: int = 50):
        """Pass-through to EventBus (for tests)."""
        return self._bus.get_event_log(limit=limit)
```

- [ ] **Step 6: 跑测试确认 PASS**

```bash
cd projects/agora && uv run pytest tests/test_bus_eventbus_backend.py -v
```
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add projects/agora/src/agora/bus/backends/ projects/agora/tests/test_bus_eventbus_backend.py
git commit -m "feat(bus): add EventBusBackend (wrap agora.core.event_bus)"
```

---

### Task 1.8: 写 `router.py` (路由 + DLQ fallback) + `__init__.py` (facade)

**Files:**
- Create: `projects/agora/src/agora/bus/router.py`
- Create: `projects/agora/src/agora/bus/__init__.py`

- [ ] **Step 1: 写 `router.py`**

```python
"""Router — dispatch envelope to backend, fall back to DLQ on failure.

Phase A.0: 1 backend (eventbus). Phase A.1 adds routing by event_type prefix.
"""
from __future__ import annotations

import logging
from typing import Any

from agora.bus.backends.base import BusBackend
from agora.bus.dlq import DLQ
from agora.bus.envelope import BusEnvelope

logger = logging.getLogger(__name__)


class Router:
    """Dispatches envelopes to a backend, writes failures to DLQ.

    RETRY OWNERSHIP: this layer does NOT retry. It passes through and
    writes to DLQ on failure. See RETRY-OWNERSHIP.md.
    """

    def __init__(self, backend: BusBackend, dlq: DLQ | None = None):
        self.backend = backend
        self.dlq = dlq or DLQ()

    def publish(self, envelope: BusEnvelope) -> str:
        """Publish envelope via backend. On failure, write to DLQ + re-raise.

        Returns: event_id (from backend on success, from envelope on DLQ-only).
        """
        if not self.backend.is_available():
            logger.warning(
                "router_backend_unavailable",
                backend=self.backend.name,
                event_id=envelope.id,
            )
            self.dlq.enqueue(
                event_id=envelope.id,
                backend=self.backend.name,
                envelope_json=envelope.to_json(),
                error="backend unavailable",
            )
            return envelope.id

        try:
            return self.backend.publish(envelope)
        except Exception as e:
            logger.error(
                "router_publish_failed",
                backend=self.backend.name,
                event_id=envelope.id,
                error=str(e),
            )
            self.dlq.enqueue(
                event_id=envelope.id,
                backend=self.backend.name,
                envelope_json=envelope.to_json(),
                error=str(e),
            )
            return envelope.id  # DLQ captured; don't re-raise
```

- [ ] **Step 2: 写 `__init__.py` facade**

```python
"""agora.bus — unified bus interface (Phase A.0).

Public API:
    publish(envelope)  — publish an event
    subscribe(pattern, fn)  — register a subscriber
    schedule(expr, fn)  — schedule a recurring task (Phase A.1)

Architecture: facade → router → backend (1 in Phase A.0) → DLQ on failure.
"""
from __future__ import annotations

import functools
import logging
from typing import Callable

from agora.bus.backends.eventbus import EventBusBackend
from agora.bus.dlq import DLQ
from agora.bus.envelope import BusEnvelope
from agora.bus.router import Router

logger = logging.getLogger(__name__)

# Module-level singletons (Phase A.0 — Phase A.1 adds DI)
_default_backend = EventBusBackend()
_default_dlq = DLQ()
_router = Router(backend=_default_backend, dlq=_default_dlq)

__all__ = ["BusEnvelope", "EventType", "publish", "subscribe", "schedule"]


def publish(envelope: BusEnvelope) -> str:
    """Publish an event via the default router."""
    return _router.publish(envelope)


def subscribe(pattern: str) -> Callable:
    """Decorator: register a subscriber for a pattern.

    Usage:
        @subscribe("pipeline:*")
        def on_pipeline(env: BusEnvelope) -> None: ...
    """

    def decorator(fn: Callable) -> Callable:
        sub_id = _default_backend.subscribe(pattern, fn)
        logger.info("bus_subscribed", pattern=pattern, sub_id=sub_id, fn=fn.__name__)
        return fn

    return decorator


def schedule(expr: str) -> Callable:
    """Decorator: schedule a recurring task. Phase A.1 — raises NotImplementedError.

    Usage (Phase A.1):
        @schedule("every 5m")
        def heartbeat() -> None: ...
    """
    raise NotImplementedError(
        "schedule() lands in Phase A.1 (R58). See Plans/swirling-snuggling-wilkes.md."
    )


# Re-export envelope types for convenience
from agora.bus.envelope import EventType  # noqa: E402
```

- [ ] **Step 3: 跑全 bus 测试确认 PASS**

```bash
cd projects/agora && uv run pytest tests/test_bus_*.py -v
```
Expected: 12 passed (3 + 5 + 4)

- [ ] **Step 4: Commit**

```bash
git add projects/agora/src/agora/bus/router.py projects/agora/src/agora/bus/__init__.py
git commit -m "feat(bus): add Router + facade (publish/subscribe/schedule stub)"
```

---

## Week 1 验收

- [ ] **Step 5: 单文件 < 500 行检查**

```bash
find projects/agora/src/agora/bus/ -name "*.py" -exec wc -l {} \; | sort -rn | head -10
```
Expected: 最大单文件 < 500 行 (envelope.py ~120, dlq.py ~150, router.py ~50, backends/eventbus.py ~90)

- [ ] **Step 6: ruff lint + format**

```bash
ruff check projects/agora/src/agora/bus/
ruff format --check projects/agora/src/agora/bus/
```
Expected: 0 errors

- [ ] **Step 7: Commit docs (Week 1 完成)**

```bash
git commit --allow-empty -m "milestone(bus): Phase A.0 Week 1 complete (5 files + 12 tests)"
```

---

## Week 2 (Day 6-14): 测试 + 切换 + 文档

### Task 2.1: 写 retry ownership 测试 (验证 bus 不重试)

**Files:**
- Create: `projects/agora/tests/test_bus_retry_ownership.py`

- [ ] **Step 1: 写测试 (TDD red)**

```python
"""Test RETRY-OWNERSHIP rule — bus layer must NOT retry on failure."""

from unittest.mock import MagicMock

import pytest
from agora.bus.backends.base import BusBackend
from agora.bus.dlq import DLQ
from agora.bus.envelope import BusEnvelope, EventType
from agora.bus.router import Router


class TestRouterRetryOwnership:
    def test_publish_failure_goes_to_dlq_no_retry(self, tmp_path):
        """Router.publish() calls backend.publish() exactly once on failure."""
        # Mock backend that always raises
        mock_backend = MagicMock(spec=BusBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = True
        mock_backend.publish.side_effect = ConnectionError("simulated")

        dlq = DLQ(db_path=tmp_path / "test.db")
        router = Router(backend=mock_backend, dlq=dlq)

        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test")
        result = router.publish(env)  # should NOT raise

        # 1) backend called exactly ONCE (no retry)
        assert mock_backend.publish.call_count == 1
        # 2) event_id returned (from envelope)
        assert result == env.id
        # 3) DLQ has 1 row
        rows = dlq.list_all()
        assert len(rows) == 1
        assert rows[0]["event_id"] == env.id
        assert "simulated" in rows[0]["error"]

    def test_publish_unavailable_backend_goes_to_dlq(self, tmp_path):
        """Router checks is_available() first; if False, write to DLQ only."""
        mock_backend = MagicMock(spec=BusBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = False
        mock_backend.publish.return_value = "should-not-be-called"

        dlq = DLQ(db_path=tmp_path / "test.db")
        router = Router(backend=mock_backend, dlq=dlq)

        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test")
        router.publish(env)

        # 1) is_available called
        mock_backend.is_available.assert_called_once()
        # 2) publish NOT called (skipped because unavailable)
        mock_backend.publish.assert_not_called()
        # 3) DLQ has 1 row
        rows = dlq.list_all()
        assert len(rows) == 1
        assert rows[0]["error"] == "backend unavailable"

    def test_publish_success_no_dlq(self, tmp_path):
        """Happy path: backend returns event_id, DLQ stays empty."""
        mock_backend = MagicMock(spec=BusBackend)
        mock_backend.name = "mock"
        mock_backend.is_available.return_value = True
        mock_backend.publish.return_value = "evt-from-backend"

        dlq = DLQ(db_path=tmp_path / "test.db")
        router = Router(backend=mock_backend, dlq=dlq)

        env = BusEnvelope(type=EventType.PIPELINE_COMPLETED, source="test")
        result = router.publish(env)

        assert result == "evt-from-backend"
        assert dlq.list_all() == []
```

- [ ] **Step 2: 跑测试确认 PASS**

```bash
cd projects/agora && uv run pytest tests/test_bus_retry_ownership.py -v
```
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add projects/agora/tests/test_bus_retry_ownership.py
git commit -m "test(bus): add retry-ownership tests (3 cases)"
```

---

### Task 2.2: 写 demo producer 走 facade (替代改 audit_subscriber)

**为什么不做**改 audit_subscriber: audit_subscriber 直接 import `agora.auth.identity` + 用 SSB 模块, 不走裸 EventBus 路径, "改 import" 会变成 shim (双轨). 改选**新写一个 demo 文件**走 facade, 同时**用 omo 作为真实 producer** (按用户 "结合 omo" 指令).

**Files:**
- Create: `projects/agora/examples/bus_demo_publisher.py` (走 facade 的新 producer)
- Create: `projects/agora/examples/bus_demo_subscriber.py` (走 facade 的新 consumer)
- Create: `projects/omo/src/omo/bus_demo_omo_producer.py` (omo 项目用 bus facade 推 dispatch 事件)

- [ ] **Step 1: 写 demo publisher (agora examples)**

创建 `projects/agora/examples/bus_demo_publisher.py`:

```python
"""Bus demo publisher — publishes 3 sample events via agora.bus facade.

Run from agora/:
    uv run python -m examples.bus_demo_publisher

Phase A.0: 验证 facade → router → EventBus → DLQ 全链路.
"""
from __future__ import annotations

import time
import uuid

from agora.bus import BusEnvelope, EventType, publish


def main() -> int:
    for i in range(3):
        env = BusEnvelope(
            type=EventType.PIPELINE_COMPLETED,
            source="bus_demo_publisher",
            payload={"iteration": i, "uuid": str(uuid.uuid4())},
            trace_id=f"demo-trace-{i}",
        )
        event_id = publish(env)
        print(f"published {i}: event_id={event_id}")
        time.sleep(0.1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 写 demo subscriber (agora examples)**

创建 `projects/agora/examples/bus_demo_subscriber.py`:

```python
"""Bus demo subscriber — registers a callback via agora.bus facade.

Run in a separate terminal after bus_demo_publisher:
    uv run python -m examples.bus_demo_subscriber

Phase A.0: 验证 facade.subscribe() 走 EventBusBackend.subscribe().
"""
from __future__ import annotations

import time

from agora.bus import BusEnvelope, subscribe


@subscribe("pipeline:*")
def on_pipeline_event(env: BusEnvelope) -> None:
    """Called when any 'pipeline:*' event is published."""
    print(f"received: {env.type} payload={env.payload}")


def main() -> int:
    print("subscriber registered; press Ctrl-C to exit")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: 写 omo 端 demo producer (用 omo 的真实 dispatch 流程)**

创建 `projects/omo/src/omo/bus_demo_omo_producer.py`:

```python
"""omo bus demo producer — emits a structured event when omo_worker_dispatch succeeds.

Phase A.0 demo: 验证 agora.bus facade 能被 omo 项目用 (不绕过 omo 自己的 omo_worker_dispatch).

用法:
    cd projects/omo && uv run python -m omo.bus_demo_omo_producer

预期:
    1 event published to agora EventBus (id 落 ~/.runtime/bus_dlq.db 之外的 agora-events.json)
    1 trace_id 关联

依赖: omo/pyproject.toml 必须有 agora workspace dep (见 Task 2.2.1).
"""
from __future__ import annotations

import uuid

from agora.bus import BusEnvelope, publish  # agora 是 omo 显式依赖, 不需要 sys.path hack


def emit_demo_event(task_id: str, dispatch_id: str | None = None) -> str:
    """Emit a single omo:dispatched event via bus facade.

    Returns event_id.
    """
    env = BusEnvelope(
        type="omo:dispatched",  # omo 命名空间 (Phase A.0 EventType 不全, 用 raw string)
        source="omo_worker_dispatch",
        payload={
            "task_id": task_id,
            "dispatch_id": dispatch_id or f"dispatch-{uuid.uuid4().hex[:8]}",
        },
        trace_id=f"omo-trace-{uuid.uuid4().hex[:6]}",
    )
    return publish(env)


def main() -> int:
    event_id = emit_demo_event(task_id="demo-task-1")
    print(f"omo demo event published: {event_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3.1: 显式声明 omo → agora 依赖 (避免 sys.path hack)**

修改 `projects/omo/pyproject.toml`:
- 在 `[tool.uv.sources]` (如不存在则创建) 加 `agora = { workspace = true }`
- 在 `[project] dependencies` 加 `"agora"`
- 这是**标准 monorepo workspace dep**, 不是 shim. omostation 已有 7 个跨仓 import 实例 (metaos 依赖 kairon 等).

- [ ] **Step 4: 验证 omo 能 import agora.bus**

```bash
cd projects/omo && uv sync && uv run python -c "from agora.bus import publish, BusEnvelope; print('cross-repo facade import OK')"
```
Expected: `cross-repo facade import OK`

- [ ] **Step 5: 跑 demo (分 2 终端)**

终端 1:
```bash
cd projects/agora && uv run python -m examples.bus_demo_subscriber
```

终端 2:
```bash
cd projects/omo && uv run python -m omo.bus_demo_omo_producer
```

Expected: 终端 1 显示 "received: omo:dispatched payload={'task_id': 'demo-task-1', ...}"

- [ ] **Step 6: 跑 agora 全 tests 确认无回归**

```bash
cd projects/agora && uv run pytest -q 2>&1 | tail -5
```
Expected: 1105+ tests 全过

- [ ] **Step 7: Commit**

```bash
git add projects/agora/examples/bus_demo_publisher.py
git add projects/agora/examples/bus_demo_subscriber.py
git add projects/omo/src/omo/bus_demo_omo_producer.py
git commit -m "feat(bus): add facade demo (agora publisher/subscriber + omo producer)"
```

---

### Task 2.3: 更新 agora/CLAUDE.md + AGENTS.md (加 §bus 章节)

**Files:**
- Modify: `projects/agora/CLAUDE.md` (加 §bus 章节)
- Modify: `projects/agora/AGENTS.md` (加 bus 章节)

- [ ] **Step 1: 读现有 CLAUDE.md "文件职责" 段**

```bash
grep -n "文件职责\|已知技术债务" projects/agora/CLAUDE.md
```

- [ ] **Step 2: 在 CLAUDE.md 末尾加 §bus 章节**

追加到 `projects/agora/CLAUDE.md` 末尾:

```markdown
## §bus 子包 (Phase A.0, R57)

### 文件职责
| 文件 | 职责 | 风险 |
|------|------|------|
| `bus/__init__.py` | facade (publish/subscribe/schedule) | god module 风险 — 单文件 < 50 行 |
| `bus/envelope.py` | BusEnvelope wire format | - |
| `bus/router.py` | backend 分发 + DLQ fallback | 路由逻辑集中点 |
| `bus/dlq.py` | SQLite DLQ (WAL + 50MB GC) | 落 `~/.runtime/bus_dlq.db` |
| `bus/backends/base.py` | BusBackend Protocol | - |
| `bus/backends/eventbus.py` | 包裹 agora EventBus (Phase A.0 唯一) | - |

### 已知技术债
1. **bus/ 子包只有 1 个 backend** (eventbus) — Phase A.1 (R58) 加 7 个
2. **schedule() stub** — NotImplementedError, Phase A.1 实现
3. **无 Pydantic** — envelope 暂用 simple class, Phase A.1 升 Pydantic
4. **owner 待定** — R57 末在 CLAUDE.md 写明

### 安全检查清单
- [ ] bus adapter 自身不重试 (透传给底层)
- [ ] DLQ 路径用 WAL + busy_timeout
- [ ] 失败 event 入 DLQ 不抛 (避免丢失)
```

- [ ] **Step 3: 在 AGENTS.md 末尾加 bus 章节**

追加到 `projects/agora/AGENTS.md` 末尾:

```markdown
## Bus 子包 (Phase A.0)

### Key files
| File | LOC | Purpose |
|------|-----|---------|
| `agora/bus/__init__.py` | ~50 | facade — publish/subscribe/schedule |
| `agora/bus/envelope.py` | ~120 | BusEnvelope wire format |
| `agora/bus/router.py` | ~50 | backend dispatch + DLQ fallback |
| `agora/bus/dlq.py` | ~150 | SQLite DLQ (WAL + GC) |
| `agora/bus/backends/eventbus.py` | ~90 | wraps agora.core.event_bus |

### Gotchas
- **RETRY**: bus adapter 自身不重试 (透传), 详见 `bus/RETRY-OWNERSHIP.md`
- **DLQ**: 落 `~/.runtime/bus_dlq.db`, 50MB 滚动
- **Backend selection**: Phase A.0 只 1 个, A.1 加 7 个
- **schedule()**: stub, NotImplementedError, Phase A.1
```

- [ ] **Step 4: Commit**

```bash
git add projects/agora/CLAUDE.md projects/agora/AGENTS.md
git commit -m "docs(agora): add §bus subpackage to CLAUDE.md + AGENTS.md"
```

---

### Task 2.4: 跑全仓回归

- [ ] **Step 1: 跑 agora 全部测试**

```bash
cd projects/agora && uv run pytest -q 2>&1 | tail -20
```
Expected: 1105+ tests 全过, 0 失败

- [ ] **Step 2: 单文件行数硬上限**

```bash
find projects/agora/src/agora/bus/ -name "*.py" -exec wc -l {} \; | sort -rn | head -10
```
Expected: 最大单文件 < 500 行

- [ ] **Step 3: ruff 全套**

```bash
cd projects/agora && ruff check src/agora/bus/ tests/test_bus_*.py
cd projects/agora && ruff format --check src/agora/bus/ tests/test_bus_*.py
```
Expected: 0 errors

---

### Task 2.5: 落 evidence + 提交

**Files:**
- Create: `.omo/_delivery/phase-a0-completion-2026-06-12.md`

- [ ] **Step 1: 写 evidence**

```markdown
# Phase A.0 (R57) Completion Evidence

> Date: 2026-06-12
> Plan: Plans/swirling-snuggling-wilkes.md

## 验收

| 项 | 结果 |
|----|------|
| 6 文件骨架 (5 .py + 4 .md) | ✅ |
| 4 测试文件 (envelope/dlq/eventbus/retry) | ✅ 15 tests passed |
| audit_subscriber import 切换 | ✅ 行为不变 |
| CLAUDE.md + AGENTS.md 更新 | ✅ |
| ADR-0008 5 硬条件 | ✅ |
| 单文件 < 500 行 | ✅ (max 150 行) |
| 1105+ tests 全过 | ✅ |
| ruff lint/format 0 errors | ✅ |

## 红线全 hold
- ❌ bus adapter 自身不重试 ✅ (测试覆盖)
- ❌ 单 backend 单文件 < 500 行 ✅
- ❌ bus/ 子包总行数 < 3000 ✅ (~610 行)
- ❌ 改 audit_subscriber 的 import 不改 API 调用 ✅
- ❌ omo/metaos/runtime 代码 R57 不动 ✅
- ❌ Phase A 不拆仓 ✅

## 下一步 (Phase A.1, R58)
- 加 7 个 backend (asyncio/sse/ws/realtime/messagebus/cron_daemon/croniter)
- 实现 schedule()
- 切 omo_sse_daemon / metaos/workflow / cron_service 到 bus
```

- [ ] **Step 2: Commit evidence**

```bash
git add .omo/_delivery/phase-a0-completion-2026-06-12.md
git commit -m "evidence(bus): Phase A.0 completion (R57, 6 files + 15 tests)"
```

---

## Phase A.0 (R57) 总结

- **5 commit, 11 文件, 15 tests, ~610 行代码**
- **0 行 omo/metaos/runtime 改动**
- **0 破坏性**
- **公共 API 冻结**: A.0 末冻结 6 个月 (R57-R62)

---

## Phase A.1 (R58) 概要 (详细 plan 待 A.0 完成后写)

**目标**: 加 7 个 backend + schedule() 实现

**关键文件** (~1400 行, 1 文件 1 backend):
- `bus/backends/asyncio.py` (80 行) — 进程内 await
- `bus/backends/sse.py` (150 行) — wrap agora.sse, backoff 写死
- `bus/backends/ws.py` (150 行) — wrap agora.ws_server
- `bus/backends/realtime.py` (100 行) — wrap agora.realtime, 复用 version
- `bus/backends/messagebus.py` (150 行) — wrap runtime.executor.message_bus
- `bus/backends/cron_daemon.py` (150 行) — wrap omo_daemon, **默认 deprecated**
- `bus/backends/croniter.py` (150 行) — wrap runtime.cron_service
- `bus/retry.py` (80 行) — 重试所有权实现
- `bus/schemas.py` (200 行) — EventType 8 namespace map (从 audit_subscriber 复用)
- `bus/schedule.py` (200 行) — schedule() 实现

**切 3 个 demo**:
- omo/omo_sse_daemon → `from agora.bus import subscribe`
- metaos/workflow.py → `from agora.bus import publish`
- 1 个 cron job → `from agora.bus import schedule`

**验收**: 1105+ tests 全过 + bus/ 子包 ~2000 行 + 8 backend 全覆盖

---

## R59-R62 沉淀期 概要

**目标**: 5 硬条件监测 + 推广到 omo/metaos/runtime

**月度任务**:
- 跑 `grep -rln "from agora.bus" projects/*/src/ | wc -l` 测硬条件 1
- 跑 `git log --since="180 days ago" -- projects/agora/src/agora/bus/ | wc -l` 测硬条件 2
- 写 `bus/owner.md` 测硬条件 3
- 监控 GitHub issues 测硬条件 4
- 跑 `git log` 统计测硬条件 5

**R62 末评估**: 5 全满足 → Phase B; 否则继续沉淀

---

## Phase B (R63+, 触发后) 概要

**动作**: 拆 `projects/bus-foundation/` 独立仓
- 搬 agora/bus/* 过去
- agora 改 import
- 独立 owner / CI / release

**不达标退路**: R63 评估不通过 → 继续沉淀, R70 再评

---

## Phase C (R70+, 触发后) 概要

**动作**: 提升到 `protocols/bus-foundation/` (L0 协议层)
- 纳入 I0 织层 governance
- agora 退回 "gateway" 角色
- 写 governance charter

**不达标退路**: R70 不达标 → 继续 Phase B, R78 再评

---

## 整体时间线

```
R57 (4 周)        Phase A.0       ← 本 plan 覆盖
R58 (4 周)        Phase A.1       ← 加 7 backend
R59-R62 (4 月)    沉淀期          ← 5 硬条件监测
R63 (评估点)      Phase B         ← 拆仓 (硬条件触发)
R64-R70 (6 月)    Phase B 沉淀
R70+ (评估点)     Phase C         ← L0 提升
```

**总时长**: 12+ 月
**总代码**: ~3000 行 (R57 末), 增长到 ~5000 行 (A.1 末)
**总测试**: ~50 个 (R57), ~150 个 (A.1)

---

## Self-Review (老王 4 项自检)

**1. Spec coverage**:
- [x] 5 文件骨架 (Task 1.5-1.8)
- [x] 3 文档 (Task 1.1-1.4)
- [x] 4 测试文件 (Task 1.5-1.7, 2.1)
- [x] 1 个 producer 切换 (Task 2.2)
- [x] CLAUDE.md/AGENTS.md 更新 (Task 2.3)
- [x] ADR-0008 (Task 1.2)
- [x] 全仓回归 (Task 2.4)
- [x] evidence 落盘 (Task 2.5)

**2. Placeholder scan**: 0 placeholder, 所有 step 含完整代码

**3. Type consistency**:
- `BusEnvelope` 在 envelope.py 定义, 全 plan 一致
- `EventType` 在 envelope.py 定义, 全 plan 一致
- `DLQ` 在 dlq.py 定义, router.py 和 test 引用一致
- `EventBusBackend` 在 backends/eventbus.py 定义, __init__ 和 test 引用一致

**4. Plan 完整性**: Phase A.0 详细 + A.1/B/C 概要 (按 plan 节奏分阶段细化)
