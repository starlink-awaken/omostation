# AGENTS.md — OMO 引擎开发规范

> **⚠️ 注意：你现在身处的是 OMO OS 内核源代码仓库 (projects/omo)。**  
> 这里是系统的底层执行引擎（Engine），它不同于工作区根目录下的 `.omo/` 实例。

## 定位与边界

1. **这里是什么**：
   - 这里的代码构成了 OMO 的命令行工具 (`omo_worker.py`, `cli.py` 等)。
   - 它是管理各个 L1-L4 Organism（如 Kairon, GBrain）的“操作系统层”的基础设施。
2. **这里绝对不是什么**：
   - 这里**绝对没有**具体的业务任务池 (`tasks/`)、工作态快照 (`workers/`) 或者项目真相库 (`_truth/`)。
   - 不要在这个仓库下生成任何 `.omo/` 的运行时数据。

## 开发与行为准则

- **纯代码环境**：在这个项目中，你的角色是**系统内核开发工程师**。请专注于编写、重构和测试 Python 代码（特别是并发安全、状态流转逻辑）。
- **工具链**：本项目使用 `uv` 进行依赖管理和构建。如果你需要添加新依赖，请使用 `uv add <package>`。
- **架构心智**：修改调度代码（如 `omo_worker.py`）时，务必牢记你的修改将影响所有未来挂载的 `.omo/` 实例的生死存亡。**并发安全（SQLite Locks）**和**原子性**是第一要义。

## AppendOnlyLog (Round 1-13 收口)

本仓 `omo_io.AppendOnlyLog` 是 L0 JSONL 物理写盘 SSOT (Round 1-5 收口 + Round 12-13 扩展).
**7 个 consumer** 共享同一物理层 (Round 5 后 Round 12 又加 2 个, 证明模式 OCP):

| # | Consumer | 加入轮次 | 角色 | 落点 .jsonl |
|---|----------|---------|------|-------------|
| 1 | `omo_audit` | R1 | governance actions | `~/runtime/audit/governance-audit.jsonl` |
| 2 | `omo_bos_metrics` | R2 | BOS invocations | `.omo/_knowledge/bos-metrics.jsonl` |
| 3 | `omo_sync` | R3 | omo state sync | `.omo/_knowledge/omo-sync.jsonl` |
| 4 | `omo_alert` | R4 | KEI threshold alerts | `.omo/_knowledge/omo-alerts.jsonl` |
| 5 | `omo_event` | R5 P3 | 用户面向 emit | `.omo/_knowledge/omo-events.jsonl` |
| 6 | `omo_history` | R12 (Round 5 漏登) | 治理评分历史快照 | `.omo/_knowledge/governance-history.jsonl` |
| 7 | `omo_trail` | R12 P0 | 细粒度 step-by-step 操作轨迹 | `.omo/_knowledge/omo-trail.jsonl` |

修改 AppendOnlyLog 时, 外部 API 0 破坏 (append/read_all/tail/since/clear + lock= 参数),
新增 consumer 加 import 就完事 (样板 = 2 行 `AppendOnlyLog(p).append(rec, schema=...)`).
Round 12 加 `omo_trail` 真·OCP 验证: 改 0 行既有代码, 仅 1 文件新增 + 1 schema + SCHEMA_REGISTRY 1 行.

**Audit 机制 (Round 13 P0)**:
```bash
uv run --directory projects/omo python -m omo.cli logs audit                           # fail on any drift
uv run --directory projects/omo python -m omo.cli logs audit --baseline-init PATH     # 写 baseline (lock-file)
uv run --directory projects/omo python -m omo.cli logs audit --baseline-check PATH    # pre-commit 用, 增量 fail
```

完整设计见 `.omo/_knowledge/management/append-only-log-pattern-2026-06-09.md` (§11 Round 12-13 扩展).
