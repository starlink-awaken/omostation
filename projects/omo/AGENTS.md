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

## AppendOnlyLog (Round 1-5 收口)

本仓 `omo_io.AppendOnlyLog` 是 L0 JSONL 物理写盘 SSOT (5 轮全景方案产物).
5 个 consumer 共享: omo_audit / omo_bos_metrics / omo_sync / omo_alert / omo_event.

修改 AppendOnlyLog 时, 外部 API 0 破坏 (append/read_all/tail/since/clear + lock= 参数),
新增 consumer 加 import 就完事 (样板 = 2 行 `AppendOnlyLog(p).append(rec)`).
完整设计见 `.omo/_knowledge/management/append-only-log-pattern-2026-06-09.md`.
