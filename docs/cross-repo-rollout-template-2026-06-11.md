# Cross-Repo Rollout Template — §19.2 R45 跨仓 lint-metrics 接入 (2026-06-11)

> **状态**: 模板 (Round 45 P0)
> **作者**: 老王
> **定位**: §19 生态圈路线图 (R45-R56 12 Round) 短期实施模板
> **目的**: kairon / gbrain / runtime / metaos 各仓 owner 拿到模板后照做, 跨仓 lint-metrics 接入
> **链接**: §12 跨仓契约 + §13 omo_lint + §17 度量 + §19 路线图

---

## §19.2.1 适用仓

| 仓 | 类型 | 接入路径 | 优先级 |
|----|------|----------|--------|
| **kairon** | Python (meta-stub) | §19.2.3 Python 5 步 | R48 P0+ (P0+ = 短期优先) |
| **metaos** | Python (L2 编排) | §19.2.3 Python 5 步 | R49 (中期) |
| **gbrain** | TypeScript (真仓) | §19.2.4 TypeScript 5 步 | R50 (中期) |
| **runtime** | Python (L1 运行时) | §19.2.3 Python 5 步 | R51-R53 (长期) |

## §19.2.2 通用要求 (§12.1 4 不变量)

任何仓接入前, **必须**满足:

1. **物理 SSOT** (§12.1.1): 所有 JSONL 物理写盘走 `AppendOnlyLog` (Python) / `zod` (TS), 禁裸 `open+write`
2. **写时 Pydantic** (§12.1.2): `.append(record, schema=...)` 必传 schema kwarg
3. **Z-suffix** (§12.1.3): timestamp 字段以 `Z` 结尾, schema 继承 `ZTimestampModel` (Python) / zod regex `/Z$/` (TS)
4. **sort_keys=True** (§12.1.4): `.append(..., sort_keys=True)` 默认, 字节级兼容

## §19.2.3 Python 仓 5 步接入 (kairon/metaos/runtime)

### Step 1: copy `AppendOnlyLog` 抽象 (~30 lines)

```python
# <repo>/src/<pkg>/io.py
class AppendOnlyLog:
    def __init__(self, path, *, lock=None):
        self.path = Path(path)
        self._lock = lock or threading.Lock()
    def append(self, record, *, schema=None, **json_kwargs):
        if hasattr(record, "model_dump"):
            record = record.model_dump()
        if schema is not None:
            schema.model_validate(record)  # fail-fast
        # ... (完整代码见 §12.2.1 Step 1)
```

### Step 2: copy `ZTimestampModel` mixin (~15 lines)

```python
# <repo>/src/<pkg>/io_schemas_base.py
class ZTimestampModel(BaseModel):
    @model_validator(mode="after")
    def _check_all_timestamps(self):
        for field_name in ("ts", "recorded_at", "timestamp"):
            v = getattr(self, field_name, None)
            if v and not v.endswith("Z"):
                raise ValueError(...)
        return self
```

### Step 3: 定义本仓 Pydantic schema (per consumer)

```python
# <repo>/src/<pkg>/io_schemas.py
class TargetEventRecord(ZTimestampModel):
    ts: str
    actor: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    status: TargetStatus

SCHEMA_REGISTRY = {"target_event": TargetEventRecord}
```

### Step 4: 接入 consumer (替换裸 `open+write`)

```python
from .io import AppendOnlyLog
from .io_schemas import TargetEventRecord

def record_event(actor, action):
    log = AppendOnlyLog(Path(".omo/_knowledge/target-events.jsonl"))
    log.append(
        {"ts": _utc_now(), "actor": actor, "action": action, "status": "ok"},
        schema=TargetEventRecord,
        sort_keys=True,
    )
```

### Step 5: 加 `audit` CLI + baseline + cron

```python
# <repo>/src/<pkg>/cli.py
def cmd_audit(baseline_init=None, baseline_check=None):
    """§13 P0 3 模式: default / baseline-init / baseline-check"""
    # 完整代码见 §12.2.1 Step 6
    pass
```

```yaml
# <repo>/.github/workflows/audit-baseline-monthly.yml
name: audit-baseline-monthly
on:
  schedule: [{cron: '0 0 1 * *'}]
  workflow_dispatch:
jobs:
  refresh-baseline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.13"}
      - run: pip install uv
      - run: cd <repo> && uv run python -m <pkg>.cli logs audit --baseline-init .omo/_knowledge/_audit baseline.json
```

## §19.2.4 TypeScript 仓 5 步接入 (gbrain)

### Step 1: copy `AppendOnlyLog` (zod 适配)

```typescript
// <repo>/src/io.ts
import { z, ZodTypeAny } from 'zod';
import { appendFile, readFile } from 'fs/promises';

export class AppendOnlyLog<T extends ZodTypeAny> {
  constructor(private path: string, private schema?: T) {}
  async append(record: z.infer<T>): Promise<void> {
    if (this.schema) this.schema.parse(record);  // §12.1.2 写时校验
    const json = JSON.stringify(record) + '\n';   // TS 缺 sort_keys
    await appendFile(this.path, json);
  }
  async readAll(): Promise<Array<z.infer<T>>> {
    // ...
  }
}
```

### Step 2: ZTimestamp 校验

```typescript
const ZTimestamp = z.string().regex(/Z$/, "must end with Z");
```

### Step 3-4: schema + consumer (类似 Python)

### Step 5: gbrain cron + lint-metrics

```yaml
# gbrain/.github/workflows/audit-baseline-monthly.yml
# 类似 Python 版, 跑 ts-node 或 bun test 触发
```

## §19.2.5 lint-metrics 集成 (跨 Python/TS)

任何仓接入后, 加 `audit --metrics` flag:

```python
# Python (omo_logs.py 已就位, R39 P0)
def cmd_audit(metrics: bool = False, exclude_locked: bool = True):
    # 跑 §17 健康度评分
    if metrics:
        density = new_debt_drift / total_records
        if density <= 0.01: grade = "R0"
        # ...
```

```typescript
// TypeScript (gbrain 需 zod 重写 §17.6 公式)
```

## §19.2.6 跨仓 audit-rollout 接入 (R46)

各仓 baseline 文件就位后, omostation 根 `omo audit-rollout` 扩 `--repos`:

```bash
uv run python -m omo.cli audit-rollout \
  --repos "omostation:.,kairon:projects/kairon,metaos:projects/metaos,gbrain:projects/gbrain" \
  --include-metrics \
  --output .omo/_delivery/audit-rollout/2026-07-01.json
```

R46 P0 加 `--include-metrics` flag + §17 metrics 跨仓聚合报告.

## §19.2.7 验证清单 (跨仓 owner 接入后跑)

- [ ] `AppendOnlyLog` 抽象 copy 到 `<repo>/src/<pkg>/io.py`
- [ ] `ZTimestampModel` 继承 mixin (Python) / zod regex (TS) 就位
- [ ] 本仓 Pydantic schema 注册到 `SCHEMA_REGISTRY`
- [ ] 旧 `open+write` 全部替换为 `AppendOnlyLog.append(..., schema=..., sort_keys=True)`
- [ ] `audit --baseline-init` 写 baseline 文件
- [ ] `audit --baseline-check` 0 增量 PASS (pre-commit 接入)
- [ ] `audit --metrics` R0 优秀 (R0 健康度评分)
- [ ] cron `audit-baseline-monthly.yml` 月度自动 refresh
- [ ] omostation 根 `omo audit-rollout` 跨仓聚合报告就位 (1+N 仓)

## §19.2.8 已知债 / 风险

- **E1 各仓 ZTimestampModel 等价物**: TS 仓需 zod 适配, Go 仓需 validator, Rust 仓需 validator derive — §19.7 R50 实施
- **E2 跨仓 audit 报告汇聚**: 需 §19.3 R46 实施
- **E3 各仓 baseline 同步 cron**: 需各仓 owner 配合
- **E4 kairon 真实源码缺失 (meta-stub)**: 需 meta-stub → 真仓扩

## §19.2.9 Round 45+ 实质化路径

- **R45 P0** (本 commit): 模板就位 (本文件)
- **R45 P1**: 文档收口 (§11.36 + §19.12)
- **R46 P0**: 扩 `omo audit-rollout` 加 `--include-metrics` flag
- **R47 P0**: 加 ci-lint.yml 第 6 守门点 (§17 metrics 输出)
- **R48 P0+**: kairon owner 接入 (依赖 owner 配合)
- **R49 P0**: metaos owner 接入
- **R50 P0**: gbrain owner TS 适配

## §19.2.10 跨仓 owner 行动项 (具体)

### kairon owner (R48):
1. `cp omo/_shared/append_only_log.py <kairon>/src/kairon/io.py` (copy 抽象)
2. `cp omo/_shared/z_timestamp_model.py <kairon>/src/kairon/io_schemas_base.py`
3. 写 `kairon/src/kairon/io_schemas.py` (Pydantic schema)
4. 改 5 处 `.append()` 调用 (如 §12.2 5 步接入清单)
5. 跑 `python -m kairon.cli logs audit --baseline-init .omo/_knowledge/_audit baseline.json`
6. 写 `.github/workflows/audit-baseline-monthly.yml` (cron)

### metaos owner (R49):
类似 kairon, 加上 §12.2.1 Step 6 (audit CLI)

### gbrain owner (R50):
TS 适配, 用 zod 替换 Pydantic

---

**本模板** 让任何仓 owner 5 分钟内看懂接入步骤, 跨仓实施 §19 路线图短期 (R45-R47) + 中期 (R48-R50) 12 Round 计划.

**§19 路线图 + 跨仓模板** = 完整治理闭环, 让"治理债"在多仓间持续流动.
