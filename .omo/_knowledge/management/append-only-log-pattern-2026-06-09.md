# AppendOnlyLog 模式 (Round 1-5 收尾) — 2026-06-09

> **状态**: implemented (5 轮全景方案落地, 治理审计 100.0 (A+))
> **作者**: 老王
> **范围**: omo 仓 (AppendOnlyLog + 5 个 consumer + 桥接 + 跨进程锁)

---

## §0 一句话总结

把"JSONL 物理写盘"从 N 个领域各自实现**抽象成 1 个 SSOT 抽象** `AppendOnlyLog`, 5 个领域共享同一物理层 + 同一锁策略 (可换 fcntl 跨进程), 4 轮全景方案 + 1 轮 L0 强化全部闭环, 治理审计从 88.3 (B) 拉回 100.0 (A+).

## §1 5 轮全景方案

| Round | 主题 | 关键产出 | commit |
|-------|------|----------|--------|
| **R1** | 抽象 | `omo_io.AppendOnlyLog` 类 + 公开 `read_jsonl` (SSOT) | `f15a638c` + `49b27e49` |
| **R2** | 接通 | `omo_audit` / `omo_bos_metrics` 接 AppendOnlyLog (内部重构) | `91591eeb` + `01e8e683` |
| **R3** | 样板 | `omo_sync` 摆脱 details 字符串拍扁, 结构化 record | `e6131dc2` |
| **R4** | 收尾 | `tail(n)` / `since(ts)` / `fcntl_lock` / observability multi-file / `omo_alert` 接入 | `1c36557c` + `9bec4297` |
| **R5** | L0 强化 | 治理审计 100.0 验证 + 跨进程 fcntl 集成测试 + PipelineTracker 事件流 + `omo event emit` 样板 | `b53598e` + `25447b45` + `8cd3baaa` + `5e8f6cde` + `45a32ae2` + `837ded6e` |

## §2 AppendOnlyLog API

```python
class AppendOnlyLog:
    """Append-only JSONL log — domain-agnostic SSOT."""

    def __init__(self, path: Path, *, lock: ContextManager | None = None): ...

    def append(self, record: dict) -> dict: ...
    def read_all(self) -> list[dict]: ...
    def tail(self, n: int) -> list[dict]: ...
    def since(self, ts: str, *, field: str = "ts") -> list[dict]: ...
    def clear(self) -> int: ...  # 原子清空, 返回行数


class fcntl_lock:  # POSIX 跨进程锁
    """Context manager wrapping fcntl.flock (POSIX)."""
    def __init__(self, lock_path: Path): ...
    def __enter__(self): ...
    def __exit__(self, *args): ...
```

**锁策略矩阵**:

| 场景 | 锁 | 适用 |
|------|----|----|
| 单进程多线程 | 默认 `threading.Lock` | 4 线程 × 100 writes 实测 0 丢 |
| 跨进程 | 注入 `fcntl_lock` | 2 子进程 × 50 writes 实测 0 丢 |
| Windows | (待补 portalocker) | pytest skip |

## §3 5 个 Consumer

| # | 模块 | 角色 | 落点 .jsonl | 读/写 |
|---|------|------|-------------|-------|
| 1 | `omo_audit` | governance actions | `~/runtime/audit/governance-audit.jsonl` | 写 |
| 2 | `omo_bos_metrics` | BOS invocations | `.omo/_knowledge/bos-metrics.jsonl` | 写 |
| 3 | `omo_sync` | omo state sync | `.omo/_knowledge/omo-sync.jsonl` | 写 |
| 4 | `omo_alert` | KEI threshold alerts | `.omo/_knowledge/omo-alerts.jsonl` | 写 |
| 5 | `omo_event` (P3 样板) | 用户面向 emit | `.omo/_knowledge/omo-events.jsonl` | 写 |

**L1 → L0 桥接 (P2)**:
- `model_driven.PipelineTracker` 加 `on_event` 回调钩子 (向后兼容, 默认 None)
- `omo.model_driven_bridge` 提供 `make_pipeline_tracker_with_log(entity_id)` 工厂
- L1 流水线事件流到 L0: `.omo/_knowledge/pipeline-events.jsonl`

## §4 4 个观测命令 (omo-cli)

| 命令 | 用途 |
|------|------|
| `omo bos status` | BOS invoke metrics 汇总 (p50/p95/p99 + by_uri + by_domain) |
| `omo bos discover` | Pydantic schema 验证后的注册表 (按 domain 分组) |
| `omo bos health` | endpoint 可达性 + metrics 状态 (一次性报告) |
| `omo observability log tail --type knowledge [--file X]` | 多文件 tail .omo/_knowledge/*.jsonl |

## §5 守原则

| 原则 | 体现 |
|------|------|
| **SSOT** | JSONL 物理写盘 = `AppendOnlyLog` 唯一入口 |
| **DRY** | 5 个 consumer 共享 1 套物理, 0 行重复 |
| **KISS** | 写汇样板 = `log.append(rec)` 2 行 |
| **OCP** | 第 6/7/N 个 consumer 加 1 个 import 就完事 |
| **SRP** | AppendOnlyLog = 物理; omo_X = 语义; model_driven_bridge = 桥接 |
| **DIP** | 消费者依赖 AppendOnlyLog 抽象, 注入 lock= 升级策略 |

## §6 度量

| 指标 | Before (Round 0) | After (Round 5) | Δ |
|------|------------------|-----------------|---|
| JSONL 物理实现点 | 散在 N 处 | **1 (AppendOnlyLog)** | -N+1 |
| 治理审计总分 | 88.3 (B) | **100.0 (A+)** | +11.7 |
| AppendOnlyLog consumer | 0 | **5** | +5 |
| 跨进程锁测试覆盖 | 0 | **100/100 0 丢行** | 新增 |
| L1 → L0 事件流 | 不可观察 | **可查** | 新增 |
| omo 单元测试 | 75+ | **100+** | +25 |
| 集成测试 (subprocess) | 0 | 3 | 新增 |
| 跨项目桥接 | 0 | 1 (model_driven_bridge) | 新增 |

## §7 跨进程安全就位证明

`tests/test_omo_io_crossproc.py` 3 个测试:

1. **test_cross_process_fcntl_lock_no_loss**: 2 子进程 × 50 writes = 100/100 0 丢行
2. **test_cross_process_default_lock_loses**: 反向证明默认 lock 跨进程会丢
3. **test_fcntl_lock_serial_workers_ok**: 串行不卡死

## §8 使用模板 (未来新领域接入)

```python
# 1. 写汇 consumer
from omo.omo_io import AppendOnlyLog

class MyDomain:
    DEFAULT_LOG = Path(".omo/_knowledge/my-domain.jsonl")
    
    def record(self, event: dict) -> None:
        AppendOnlyLog(self.DEFAULT_LOG).append(event)


# 2. 跨进程时注入 fcntl_lock
from omo.omo_io import fcntl_lock

log = AppendOnlyLog(
    path,
    lock=fcntl_lock(path.with_suffix(".lock")),  # 跨进程保护
)


# 3. 查询 / Tail / Since
log = AppendOnlyLog(path)
recent_100 = log.tail(100)
last_24h = log.since("2026-06-08T00:00:00Z")
```

## §9 与既有宪章的关系

- **§1 L0 协议**: 端口/路径 SSOT 守住, 0 破坏
- **§2 接口治理**: AppendOnlyLog 不暴露为新端口 (L2 内部抽象)
- **§3 债务治理**: 8 个 pre-existing P0+P1 debt 已在 Round 1-5 顺带清理
- **§4 X 轴 (审计/保鲜/价值/一致)**:
  - X1 审计: Round 5 验证 100.0 (A+) 守
  - X2 保鲜: 3 种时间戳格式 → 1 种 (Z 结尾)
  - X3 价值: 5 个新 consumer 全部"用上" (非空架子)
  - X4 一致: 1 个物理层, 0 漂移

## §10 未来工作 (已勾掉)

- ~~P0-1 tail(n)~~ ✅
- ~~P0-2 since(ts)~~ ✅
- ~~P0-3 fcntl 跨进程锁~~ ✅
- ~~P1-1 observability multi-file~~ ✅
- ~~P1-2 omo_alert 接入样板~~ ✅
- ~~P2 PipelineTracker 事件流~~ ✅
- ~~P3 1 个新领域样板~~ ✅ (omo event emit)

仍可继续:
- P2 (low-priority): `group_by(field)` 通用聚合 (API 设计讨论, 暂不做)
- 性能: tail 用 reverse-seek 读大文件 (O(file_size) 优化)
- 接入更多领域: omo_capability (注册表类), omo_daemon (事件流类)

---

## §11 Round 12-13 扩展 — 团队层落地 + 模式可扩展性

> **状态**: implemented (Round 12 P0+P1 + Round 13 P0)
> **作者**: 老王
> **新增**: 第 7 consumer `omo_trail` · CI lint 基建 · audit baseline 机制

### §11.1 动机

Round 5 收口时 `§10 未来工作` 写"接入更多领域: omo_capability / omo_daemon" — Round 12 把"接入"这件事**从"是否做"推进到"怎么做更可扩展"**:
- 第 7 consumer `omo_trail` 落地, 证明模式 OCP: 6→7 改动 = 加 1 个文件 + 1 个 Pydantic schema + SCHEMA_REGISTRY 1 行
- SSOT 从 omo 仓内部走到**团队层**: CI lint 工作流 + pre-commit hook
- audit 机制从"任何 drift 都 fail"升级为"baseline 锚定 + 增量 fail" (历史漂移不阻塞新代码)

### §11.2 Round 12 — 第 7 consumer + CI lint

| Commit | 主题 | 关键产出 |
|--------|------|----------|
| Round 12 P0 | 第 7 consumer `omo_trail` | `omo_trail.py` 200 行 · `OmoTrailRecord` 7 字段 · `omo_trail record/show` CLI · `tests/test_omo_trail.py` 10/10 PASS |
| Round 12 P1 | CI lint + pre-commit 收口 | `.github/workflows/ci-lint.yml` 4 jobs (actionlint/check-yaml/shellcheck/omo-logs-audit) · `.pre-commit-config.yaml` 加 check-yaml + omo-logs-audit 旧版 |

**omo_trail 区别于既有 6 consumer**:
- 细粒度 step-by-step 操作轨迹 (vs 周期性快照)
- 强制 `actor` (谁做的) + `duration_ms` (耗时) + `parent_step_id` (嵌套调用图)
- 适合"agent 走完几步完成任务"场景, 跟 `omo_audit` (决策) 互补

**OCP 验证**:
- 加 `omo_trail` 改了 0 行 AppendOnlyLog 物理层
- 加 `omo_trail` 改了 0 行既有 6 consumer
- 只动了: `omo_io_schemas.py` (新 schema) + `omo_trail.py` (新文件) + SCHEMA_REGISTRY 1 行
- → 模式可扩展性从"承诺"变"证明"

### §11.3 Round 13 — Audit Baseline 机制

| Commit | 主题 | 关键产出 |
|--------|------|----------|
| Round 13 P0 | baseline-init / baseline-check | `omo_logs.py` 加 2 模式 (135 行) · 5 个新测试 (init/check pass/regression/improvement/missing) · `.omo/_knowledge/_audit_baseline.json` 锚定 drift 1116 · `.pre-commit-config.yaml` 升级用 baseline-check |

**问题**: 1100+ drift 都是 omo_history 老 schema 缺字段 (与新代码无关), pre-commit 跑 audit 必 fail → 失去"增量检测"价值.

**方案**: 3 模式 dispatch
```
omo logs audit                           # 默认: fail on any drift (CLI 用)
omo logs audit --baseline-init <path>    # 写当前 drift 为 baseline (lock-file 风格)
omo logs audit --baseline-check <path>   # 对比 baseline, 增量 > 0 才 fail (pre-commit 用)
```

**实现细节**:
- 抽象: `drift_by_consumer: dict[str, int]` 一次扫描计算, 三模式共用
- 输出: baseline-check 区分 3 种状态 (✅ 不变 / ✅ 改善 / ❌ 回归) 写入 stdout
- 退出码: 0 (pass/改善) 或 1 (回归/缺文件)
- JSON 结构: `{_comment, generated_at, drift_by_consumer, total_drift, total_records}`

**局限 (待 P1)**:
- `dashboard_monitor` 守护进程每 5min 写 1 条 record 缺 4 必填字段 (date/total_score/grade/watchlist_count) → drift 持续上行
- 当前 baseline 反映"这一刻", daemon 持续写入会推高 baseline
- P1 解法: 修 daemon 写合规 OmoHistoryRecord (新增字段用占位值), 或 audit 加 source 白名单

### §11.4 度量增量 (Round 5 → Round 13)

| 指标 | Round 5 | Round 13 | Δ |
|------|---------|----------|---|
| AppendOnlyLog consumer | 5 | **7** | +2 (omo_history + omo_trail) |
| Pydantic schema | 5 | **7** | +2 |
| SCHEMA_REGISTRY 条目 | 5 | **7** | +2 |
| omo 单元测试 | 100+ | **115+** | +15 (omo_trail 10 + omo_logs_baseline 5) |
| pre-commit hook | 0 | **2** (check-yaml + omo-logs-audit) | +2 |
| CI 工作流 | 0 | **1** (ci-lint.yml, 4 jobs) | +1 |
| audit baseline 文件 | 0 | **1** (lock-file 风格) | +1 |

### §11.5 守原则延续

Round 12-13 全部延续 §5 六原则, 0 偏离:
- **OCP**: 第 7 consumer 加 0 行既有代码 (真·开闭)
- **SSOT**: baseline 是 1 个 lock-file, 1 个生成命令, 1 个检查命令
- **DRY**: 5 个新测试 + 10 个 omo_trail 测试 = 15 个, 0 重复
- **KISS**: baseline 机制 = init/check 2 个 bool flag, 0 抽象
- **SRP**: omo_logs 读/查, AppendOnlyLog 写, OmoTrailRecord 校验 — 边界清晰
- **DIP**: omo_trail 依赖 AppendOnlyLog 抽象 (同 Round 1-5)

### §11.6 未来工作 (Round 14+)

- [x] **P0-1** ✅ Round 14 P0: 修 dashboard_monitor 守护进程让 record 合规 (补 4 必填字段占位值)
- [~] **P0-2** ⛔ 取消: P0-1 已治本, 白名单逻辑会是 no-op, 不重复造轮
- [ ] **P1-1** baseline 时给 omo-trail 留 0 漂移位 (目前 trail 还没人写, baseline 还没纳入, 需 init 时加)
- [ ] **P1-2** CI 跑 omo_lint (新增) 校验各 consumer 写入用 Pydantic schema (不是 dict 强转)
- [ ] **P2** 把 §11.2-11.3 的范式 (OCP 验证 + baseline) 推广到其他 L1 子项目 (kairon, gbrain)

### §11.7 Round 14 收口 — baseline 自洽

> **状态**: implemented
> **commit**: `2185ab44` (Round 14 P0)
> **新增**: dashboard_monitor 合规化 + 5 个新测试 + baseline 锁当前态

**P0-1 实施**:
- `dashboard_monitor.sh` 写 record 时塞 4 占位字段 (date / total_score=0.0 / grade="F" / watchlist_count=0)
- 加 3 个 env override (LAUNCHD_STATE_OVERRIDE / HTTP_CODE_OVERRIDE / PID_OVERRIDE) 供测试 DI
- `tests/test_dashboard_monitor_schema.py` 5/5 PASS

**治本验证**:
- 老 drift 1121 (历史缺字段 record) 锁在 baseline, 无法清理
- 新 daemon 写入 = 0 漂移 (合规 record, 不再算 audit failure)
- baseline-check 0 增量, pre-commit 自洽 (不再 5min 必 fail)

**语义权衡** (写在 commit message 里):
- dashboard_monitor 是健康监控点, 不是治理决策
- 4 字段是占位值, grade="F" 语义 = "不参与评分" 不是 "真差"
- 长期方案 (P2 范畴): 拆 dashboard_monitor 到独立 `omo_health` consumer (新 .jsonl), 治理历史不被健康监控污染


