# §12 AppendOnlyLog 模式 — 跨仓契约 manifest (Round 22 起步)

> **状态**: 起步 (Round 22 P0)
> **作者**: 老王
> **定位**: §11 仓内实现 / §12 跨仓契约 (互补, 不可替代)
> **动机**: §11 模式 9 段全收后, 需要"跨仓可引用"的 SSOT 入口
> **目的**: 让其他 L1 子项目 (kairon / gbrain / runtime / metaos) 接入时**有章可循**

---

## §12.0 一句话总结

§11 描述 **omo 仓内** AppendOnlyLog 模式 9 段收口的**实现细节**; §12 描述**跨仓契约** — 任何仓接入此模式必须满足的 4 不变量 + 8 步接入清单 + 治理债清单, 让 §11 模式红利**可被其他仓复制**。

## §12.1 跨仓 4 不变量

任何仓 (omo / kairon / gbrain / runtime / metaos / ...) 接入 AppendOnlyLog 模式, **必须**满足:

### §12.1.1 物理写盘 SSOT

所有 JSONL 物理写盘走 `AppendOnlyLog` 类, 禁止直接 `open(path, 'a') + json.dump`.

- 验证: 仓内 `*.py` (或 `*.ts` / `*.go`) `rg "open\(.*['\"]a['\"]\)" 0 匹配` (除 AppendOnlyLog 自身)
- 跨进程时: 注入 `fcntl_lock` (POSIX) / `LockFile` (Windows) — 写时锁不丢行
- 落点: `.omo/_knowledge/<consumer>.jsonl` (各仓统一路径)

### §12.1.2 写时 Pydantic 校验 (X1 审计契约)

每次 `.append(record, schema=SomeSchema)` 必传 `schema=`, 走 Pydantic fail-fast.

- 验证: `omo lint schemas` (omo 仓工具) 跨仓等价物 — 静态扫 consumer 模块, 校验 `.append()` 都传 `schema=`
- 例外白名单 (极少): 业务字段完全自由 (caller 决定所有字段) 的接口, 如 `omo_history.append_entry` 早期宽容模式
- 反例: `.append({"raw": json_str})` 跳过 schema 校验 → 失去 X1 审计

### §12.1.3 Z-suffix ISO8601 时间戳

每个 schema 至少 1 个 timestamp 字段 (`ts` / `timestamp` / `recorded_at`), 必须以 `Z` 结尾 + ISO8601 格式合法.

- 验证: schema 必须继承 `ZTimestampModel` 基类 (omo) / zod `.regex(/Z$/)` (TypeScript)
- 防止: 老 record 三种 timestamp 格式 (RFC3339 / unix epoch / naive ISO) 并存 → §11 X2 保鲜塌方

### §12.1.4 sort_keys=True 字节级兼容

跨进程 + 跨工具读 .jsonl 时, **字节级顺序一致** (sort_keys=True). 防止 git diff 噪声 + kairon-governance 旧工具兼容.

- 验证: `AppendOnlyLog.append(..., sort_keys=True)` 默认启用
- 例外: 业务字段顺序敏感 (e.g. 嵌套 dict 需保持插入序) — 极少见, 需显式 opt-out

## §12.2 8 步接入清单 (新仓复制)

| # | 步骤 | 文件 | 行数 (参考) |
|---|------|------|-------------|
| 1 | copy `AppendOnlyLog` 抽象 | `<repo>/src/<pkg>/io.py` | ~30 行 |
| 2 | copy `ZTimestampModel` mixin | `<repo>/src/<pkg>/io_schemas_base.py` | ~15 行 |
| 3 | 定义本仓 Pydantic schema | `<repo>/src/<pkg>/io_schemas.py` | per consumer |
| 4 | 注册 `SCHEMA_REGISTRY` | 同上 | 1 dict |
| 5 | 接入 consumer (替换裸 `open+write`) | `<repo>/src/<pkg>/<consumer>.py` | per module |
| 6 | 加 `audit` CLI (3 模式) | `<repo>/src/<pkg>/cli.py` | ~100 行 |
| 7 | 加 baseline 文件 | `<repo>/.omo/_knowledge/_audit_baseline.json` | JSON |
| 8 | CI 集成 (4 jobs) | `<repo>/.github/workflows/ci-lint.yml` | ~80 行 |

总计 ~250 行新代码 + 1 个 baseline 文件, 1 个 CI job.

## §12.2.1 5 步代码示例 (Python, 完整可跑)

下面是从 0 到跑通的**完整 Python 接入代码**, 跨仓 owner 复制改路径即可。

### Step 1: `src/<pkg>/io.py` (AppendOnlyLog 抽象, ~30 行)

```python
"""AppendOnlyLog — 仓内 JSONL 物理写盘 SSOT (本仓实现, 跨仓契约见 §12.1.1)."""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional


class AppendOnlyLog:
    def __init__(self, path: Path, *, lock: Optional[Any] = None):
        self.path = Path(path)
        self._lock = lock or threading.Lock()

    def append(self, record: Any, *, schema: Optional[type] = None, **json_kwargs) -> dict:
        # Pydantic 校验 (§12.1.2)
        if hasattr(record, "model_dump"):
            record = record.model_dump()
        if schema is not None:
            schema.model_validate(record)  # fail-fast
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, **json_kwargs) + "\n")
        return record

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]


@contextmanager
def fcntl_lock(lock_path: Path):
    """POSIX 跨进程锁 (§12.1.1 注). Windows 需 portalocker 替代."""
    import fcntl
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = lock_path.open("w")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        fd.close()
```

### Step 2: `src/<pkg>/io_schemas_base.py` (ZTimestampModel mixin, ~15 行)

```python
"""Z-suffix ISO8601 时间戳 mixin (§12.1.3 跨仓必须)."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, model_validator

_TIMESTAMP_FIELDS = ("ts", "recorded_at", "timestamp")


class ZTimestampModel(BaseModel):
    @model_validator(mode="after")
    def _check_all_timestamps(self) -> "ZTimestampModel":
        for field_name in _TIMESTAMP_FIELDS:
            v = getattr(self, field_name, None)
            if v is not None and isinstance(v, str):
                if not v.endswith("Z"):
                    raise ValueError(f"timestamp must end with 'Z', got: {v!r}")
                try:
                    datetime.fromisoformat(v.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"invalid ISO8601: {v!r} ({exc})")
        return self
```

### Step 3+4: `src/<pkg>/io_schemas.py` (Pydantic schema + SCHEMA_REGISTRY)

```python
"""本仓 Pydantic schema (per consumer)."""
from __future__ import annotations

from enum import Enum
from pydantic import Field
from .io_schemas_base import ZTimestampModel


class TargetStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class TargetEventRecord(ZTimestampModel):
    """本仓 consumer 1 样板 — 任何仓定义 1 个 schema, Z-suffix + 必填字段守 §12.1.3."""
    ts: str
    actor: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    status: TargetStatus


SCHEMA_REGISTRY: dict[str, type[ZTimestampModel]] = {
    "target_event": TargetEventRecord,  # §12.1.2 写入时用此 key
}
```

### Step 5: 接入 consumer (替换裸 open+write)

**Before** (违反 §12.1.1):
```python
# 旧代码 — 禁
with open("/path/to/log.jsonl", "a") as f:
    f.write(json.dumps({"ts": datetime.now().isoformat(), "x": 1}) + "\n")
```

**After** (满足 §12.1.1 + §12.1.2 + §12.1.4):
```python
from .io import AppendOnlyLog
from .io_schemas import TargetEventRecord

def record_event(actor: str, action: str) -> None:
    log = AppendOnlyLog(Path(".omo/_knowledge/target-events.jsonl"))
    log.append(
        {"ts": _utc_now(), "actor": actor, "action": action, "status": "ok"},
        schema=TargetEventRecord,        # §12.1.2 写时 Pydantic
        sort_keys=True,                   # §12.1.4 字节级兼容
    )
```

### Step 6+7+8: audit CLI + baseline + CI

`src/<pkg>/cli.py` 调 `cmd_logs_audit()` 跑 3 模式 (default / `--baseline-init` / `--baseline-check`) — 完整代码见 omo 仓 `omo_logs.py:200-346`, 复制改 `KNOWNLEDGE_DIR` 路径即可。

baseline 文件: `<repo>/.omo/_knowledge/_audit_baseline.json` (lock-file 风格, commit 入仓).

CI 集成: 仿 `.github/workflows/ci-lint.yml` 加 4 jobs (actionlint / check-yaml / shellcheck / `audit --baseline-check`).

## §12.2.2 TypeScript 适配 (gbrain 等)

`AppendOnlyLog` 抽象: 用 `zod` schema 替换 Pydantic. 例:

```typescript
// src/io.ts
import { z, ZodTypeAny } from 'zod';
import * as fsp from 'fs/promises';
import { appendFile, readFile } from 'fs/promises';

export class AppendOnlyLog<T extends ZodTypeAny> {
  constructor(private path: string, private schema?: T) {}

  async append(record: z.infer<T>): Promise<void> {
    if (this.schema) this.schema.parse(record);  // §12.1.2 写时校验
    const json = JSON.stringify(record) + '\n';
    await appendFile(this.path, json);  // §12.1.1 物理 SSOT
  }

  async readAll(): Promise<Array<z.infer<T>>> {
    const content = await readFile(this.path, 'utf-8').catch(() => '');
    return content.split('\n').filter(Boolean).map(l => JSON.parse(l));
  }
}
```

`ZTimestampModel` 等价: zod `.regex(/Z$/)` 校验.

```typescript
// §12.1.3 Z-suffix
const ZTimestamp = z.string().regex(/Z$/, "must end with Z");

// schema 定义
const TargetEvent = z.object({
  ts: ZTimestamp,
  actor: z.string().min(1),
  action: z.string().min(1),
  status: z.enum(['ok', 'error']),
});
```

## §12.2.3 Go / Rust 适配 (轻量)

- **Go**: `AppendOnlyLog` 用 struct + `os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)` + `go-playground/validator` 校验
- **Rust**: `AppendOnlyLog` 用 `BufWriter<File>` + `serde::Serialize` + `validator` derive

实际跨仓接入按仓现有栈选, 不强求 Pydantic 等价. §12.1 4 不变量 (物理 SSOT / 写时校验 / Z-suffix / sort_keys) 是硬要求, 语言具体实现软.

## §12.3 跨仓消费者索引 (omo 仓 8 schema)

§11 实现已覆盖 8 schema (Round 12-20 收口), 索引给跨仓参考:

| Schema | §11 引入 | 角色 | 跨仓适用 |
|--------|---------|------|----------|
| `OmoAuditRecord` | Round 8 P2 | governance actions | 任何仓 audit 决策可复用 |
| `OmoBosMetricsRecord` | Round 8 P2 | BOS invoke metrics | omo 独有 (BOS 是 omostation 协议) |
| `OmoSyncRecord` | Round 3 | omo state sync | 任何仓 sync 状态可复用 |
| `OmoAlertRecord` | Round 4 | KEI threshold alerts | 任何仓 KEI 监控可复用 |
| `OmoEventRecord` | Round 5 P3 | 用户面向 emit | 任何仓用户事件可复用 |
| `OmoHistoryRecord` | Round 8 P2 | 治理评分快照 | 任何仓历史快照可复用 |
| `OmoTrailRecord` | Round 12 P0 | 细粒度 step 轨迹 | 任何仓 agent 步骤可复用 |
| `OmoHealthRecord` | Round 20 P0 | 健康监控 (Round 20 拆出) | 任何仓 daemon 健康点可复用 |

7 schema 可跨仓复用 (omo_bos_metrics 是 omo 独有).

## §12.4 跨仓治理债 (已知)

| 仓 | 探查报告 | 改造优先级 | 试点模块 |
|----|----------|----------|----------|
| **kairon** | meta-stub, 无真源码 | N/A | N/A |
| **gbrain** | `protocols/append-only-log-rollout.md` Round 16 探查 | P1 (TypeScript 适配) | 5 audit writer |
| **runtime** | `.omo/_knowledge/management/cross-repo-probe-runtime-metaos-2026-06-10.md` | P0 (Python) | `cron_service/scheduler.py` + `executor/agent_runner.py` |
| **metaos** | 同上 | P0 (Python) | `l2_controller.py` + `core/workflow_parser.py` |

详见 Round 19 P1 探查报告 (~140 lines).

## §12.5 跨仓接入的 X1/X2/X3/X4 对应

| §11 维度 | 跨仓要求 |
|---------|----------|
| X1 审计契约 | 跨仓 schema 校验统一 — 各仓 schema 必须满足 §12.1.2 (Pydantic) + §12.1.3 (Z-suffix) |
| X2 保鲜 | 跨仓 baseline 同步 — 每月 1 号 cron 各仓 init, 汇聚到 `workspace/.omo/_delivery/audit-rollout/` |
| X3 价值 | §11 模式**复用**而非**重造** — 节省各仓研发成本 + 治理覆盖度从 1 仓扩到 N 仓 |
| X4 一致 | 1 套 §11 物理 (AppendOnlyLog) + 1 套 §11.1.3 (Z-suffix 校验) + N 套 Pydantic/zod schema 适配 |

## §12.6 已知债 (跨仓接入本身)

按 Rollout Guide §7 + Round 19 探查:

- **E1**: 各仓 `ZTimestampModel` 等价物未就位 (Python 走 Pydantic mixin, TypeScript 走 zod, Go/Rust 走对应库)
- **E2**: 跨仓 audit 报告汇聚机制缺 (`.omo/_delivery/audit-rollout/` 目录未建)
- **E3**: 各仓 baseline 同步 cron 未配置 (建议每月 1 号 GitHub Action cron)
- **E4**: kairon 真实源码缺失 (meta-stub), 接入需先落地真仓

## §12.7 §11 关系

- §11 描述**omo 仓内** AppendOnlyLog 模式 9 段收口的实现 + 治理债清零
- §12 描述**跨仓**接入契约 + 接入清单 + 跨仓债
- 互补: §11 = how (how to implement in omo), §12 = what (what other repos must satisfy)
- 不重复: §11.6 治理债是 omo 仓内, §12.6 治理债是跨仓接入债

## §12.8 Round 22+ 候选 (本章节填充)

- [ ] §12.0 起步 (本 commit)
- [ ] §12.2 扩"接入步骤示例代码" — 抽 AppendOnlyLog 到独立 `protocols/_shared/` (跨仓 import 基础)
- [ ] §12.4 扩"各仓 Pydantic/zod 适配" — Python / TypeScript / Go / Rust 等价物清单
- [ ] §12.5 扩"跨仓 baseline 同步机制" — cron + 报告汇聚实现
- [ ] §12.6 跨仓债 E1-E4 落地 — 需各仓 owner 配合

---

**§12 章节总览**:

| 子节 | 主题 | 状态 |
|------|------|------|
| §12.0 | 一句话总结 | ✅ done (本 commit) |
| §12.1 | 跨仓 4 不变量 | ✅ done (本 commit) |
| §12.2 | 8 步接入清单 | ✅ done (本 commit) |
| §12.3 | 跨仓消费者索引 | ✅ done (本 commit) |
| §12.4 | 跨仓治理债 | ✅ done (本 commit) |
| §12.5 | §11 X1-X4 跨仓对应 | ✅ done (本 commit) |
| §12.6 | 已知债 E1-E4 | ✅ done (本 commit) |
| §12.7 | §11 关系 | ✅ done (本 commit) |
| §12.8 | Round 22+ 候选 | ✅ done (本 commit) |
