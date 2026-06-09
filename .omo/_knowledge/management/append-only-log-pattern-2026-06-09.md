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
