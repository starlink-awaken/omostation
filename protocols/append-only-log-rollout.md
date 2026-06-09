# AppendOnlyLog 模式 — 跨仓推广指南 (Round 16 P2)

> **状态**: 指南草稿 (Round 16 P0 落地)
> **目标读者**: 任何 L1 子项目 (kairon / gbrain / runtime / metaos) 的维护者
> **模式出处**: omostation Round 1-15 收口 (`projects/omo/src/omo/omo_io.py`)

---

## §0 何时需要本指南

如果你在 L1 子项目看到以下症状, 走"AppendOnlyLog 模式 + 写时 Pydantic 校验":

| 症状 | 模式提供的解 |
|------|--------------|
| 多处代码 `with open(p, 'a') as f: json.dump(rec, f)` 散在 N 处 | 1 个 `AppendOnlyLog` 类统一物理写盘 |
| 写入 record 字段名不一致 (e.g. `ts` vs `timestamp` vs `time`) | 1 个 Pydantic `BaseModel` schema 锁字段语义 |
| 老 record 缺字段 → 审计时 audit 报 drift 阻塞 CI | `baseline-init` 锁已知漂移, `baseline-check` 只查增量 |
| 跨进程并发写丢行 (多个 worker 同时 append) | `fcntl_lock` 注入锁策略 |
| 写完没法 tail / 没法按时间窗口查询 | `AppendOnlyLog.tail(n)` / `since(ts)` 走 O(1) + O(n) 真查询 |

---

## §1 接入 5 步 (新仓)

### Step 1: 拷贝 `omo_io` 抽象到目标仓 (10 行)

```python
# target_repo/src/target_pkg/io.py
import json
import threading
from pathlib import Path
from contextlib import contextmanager

class AppendOnlyLog:
    def __init__(self, path, *, lock=None):
        self.path = Path(path)
        self._lock = lock or threading.Lock()

    def append(self, record, *, schema=None, **json_kwargs):
        if hasattr(record, "model_dump"):
            record = record.model_dump()
        if schema is not None:
            schema.model_validate(record)  # fail-fast
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, **json_kwargs) + "\n")
        return record

    def read_all(self):
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def tail(self, n):
        return self.read_all()[-n:]

    def since(self, ts, *, field="ts"):
        return [r for r in self.read_all() if r.get(field, "") >= ts]
```

### Step 2: 定义 Pydantic schema (1 个 model per consumer)

```python
# target_repo/src/target_pkg/io_schemas.py
from pydantic import BaseModel, Field
from .io import ZTimestampModel  # 复用 omo 的 mixin

class TargetConsumerXRecord(ZTimestampModel):
    ts: str
    actor: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    payload: str = "{}"

SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "target_consumer_x": TargetConsumerXRecord,
}
```

### Step 3: 接入消费者 (3 行 import)

```python
# target_repo/src/target_pkg/consumer_x.py
from .io import AppendOnlyLog
from .io_schemas import TargetConsumerXRecord

DEFAULT_PATH = Path(".target/_knowledge/consumer_x.jsonl")

def record(event: dict) -> dict:
    return AppendOnlyLog(DEFAULT_PATH).append(event, schema=TargetConsumerXRecord)
```

### Step 4: 加 audit 命令 (CLI 1 个)

```python
# target_repo/src/target_pkg/cli.py
def cmd_audit(baseline_init=None, baseline_check=None):
    """走 SCHEMA_REGISTRY 校验, 报漂移 (baseline 机制同 omo)."""
    paths = sorted(DEFAULT_DIR.glob("*.jsonl"))
    drift_by_consumer = {}
    for p in paths:
        schema_name = infer_schema(p.stem)
        if not schema_name:
            continue
        records = AppendOnlyLog(p).read_all()
        required = set(SCHEMA_REGISTRY[schema_name].model_fields.keys())
        failures = sum(1 for r in records if not required.issubset(r.keys()))
        drift_by_consumer[schema_name] = drift_by_consumer.get(schema_name, 0) + failures
    # baseline-init / baseline-check 同 omo
    # ...
```

### Step 5: 加 CI 集成 (1 个 job)

```yaml
# .github/workflows/ci-lint.yml
target-audit:
  name: target audit (SSOT 漂移)
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.13" }
    - run: pip install uv
    - name: Run target audit (baseline-check)
      run: |
        cd target_repo
        uv run python -m target_pkg.cli audit --baseline-check .target/_knowledge/_audit_baseline.json
```

---

## §2 模式选择决策树

```
写 .jsonl?
├── 多 writer 共享 (≥2 个模块) → AppendOnlyLog 模式
│   ├── 需要并发安全 → 注入 fcntl_lock
│   ├── 字段需强约束 → Pydantic schema + SCHEMA_REGISTRY
│   └── 需要审计 / baseline → 走 cli audit + --baseline-{init,check}
└── 单 writer 一次写 → 直接 open + json.dump (无需抽象)
```

---

## §3 跨语言推广

| 语言 | 对应抽象 | 推广难度 |
|------|---------|---------|
| **Python** (omo) | `AppendOnlyLog` + Pydantic | ✅ 已实现 |
| **TypeScript** (gbrain) | `AppendOnlyLog` + zod | 🟡 部分 (gbrain 已有 audit-week-file, 缺 Pydantic-style schema) |
| **Go** (runtime 部分) | `AppendOnlyLog` + go-playground/validator | 🟡 待评估 |
| **Rust** (kairon) | `AppendOnlyLog` + serde + validator | 🟡 待评估 |

**TypeScript 推广路径 (Round 17 候选)**:
1. 把 gbrain `audit-week-file.ts` 抽象升级 — 加 zod schema 校验
2. 把"5 个 audit writer" 重构走 `AppendOnlyLog` 抽象 (zod 版)
3. 加 gbrain 自己的 `gbrain audit --baseline-check` CLI
4. CI 集成 gbrain-audit job

---

## §4 与 §11 SSOT 关系

- `append-only-log-pattern-2026-06-09.md` §11.6 P2 提到"把范式推广到其他 L1 子项目"
- 本文档是 P2 落地物 — 指南
- 推广后, 各仓的 audit 报告应汇聚到 `workspace/.omo/_delivery/audit-rollout-*.md` (待建)

---

## §5 不适用场景 (YAGNI)

- 一次性 init 写盘 (e.g. 配置文件生成): 直接 open + json.dump
- 高频低价值 telemetry (每秒 1000+ record): 用 ring buffer / 批量写, 不走 JSONL
- 二进制大对象 (e.g. 模型权重): JSONL 不适合, 用专门文件格式
- 强事务需求 (e.g. 关系数据库备份): 走真 DB, 不走 append-only log

---

## §6 验证清单 (新仓接入后跑)

- [ ] `AppendOnlyLog` 单元测试 (5+ cases: 写 / 读 / tail / since / 跨进程)
- [ ] Pydantic schema 校验测试 (合法 record pass, 非法 record fail)
- [ ] audit --baseline-init 创建 lock-file
- [ ] audit --baseline-check 当前 = baseline → exit 0
- [ ] audit --baseline-check 新增 drift → exit 1
- [ ] CI 工作流跑 audit job (硬 fail, 不走 warning)
- [ ] 文档 (本指南) 链接到目标仓的 README

---

## §7 已知债 (P2 范畴)

- gbrain 5 audit writer 还没走 Pydantic/zod 校验
- kairon meta-stub 缺真源码 (跨仓抽象代码 base)
- runtime / metaos 未探查 (Round 17 候选)
- 跨仓 audit 报告汇聚机制 (缺 .omo/_delivery/audit-rollout/ 目录)
