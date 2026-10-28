---
schema_version: specification/v1
spec_version: 1.0.0
title: 代码子模块内部长出第二棵 .omo/state —— 写面锚点错位数了两级 parents，profile 因此对其完全失明
bet_id: BET-Y2Q4-T10-277
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-10-28
---

# BET-Y2Q4-T10-277 — `omo.resident` 写面锚定错位收敛到 state 根（ADR-0456 B1 剩余阻塞项）

> 范围：8 个写者的**锚点解析**（5 处 `parents[3]` 错位 + 3 处 CWD/标记上溯），
> 以及每条写目标迁移所配的正向落点断言。
> **不含**：既有运行时数据的改道与合并（§5，需 principal 逐次授权）、launchd/plist/crontab、
> `.gitignore` 覆盖面（那是已结项的 BET-Y2Q4-T10-276）。

## 1. 缺陷的可测形状

`nimble-bay-asp.md` 决策 2 的落地判据是「`state_root` 由 profile 声明，所有 `RUNTIME_*`/`STATE_*`
路径改挂 `state_root`」；B1 的 verify 是「`OMOSTATION_PROFILE=dev … resident daemon --once` 只写
dev state root」。2026-10-28T07:12Z 实测（检测器与源码 base：`origin/main` = `bd9e9e62a`，
`projects/omo` gitlink = `980b9cb`）声明 `OMOSTATION_STATE_ROOT` 后逐个求值：

| 写者 | 锚点写法 | 实测落点 |
|---|---|---|
| `resident/cell_state.py:12` | `ROOT = Path(__file__).resolve().parents[3]` | `…/Workspace/projects/omo/.omo/state/agent-cell` |
| `resident/cell_governance.py:21` | 同上 | `…/projects/omo/.omo/state/agent-cell/governance-audit.jsonl` |
| `resident/cell_memory_network.py:19` | 同上 | `…/projects/omo/.omo/state/agent-cell/memory-network` |
| `resident/memory_pipeline.py:12` | 同上 | `…/projects/omo/.omo/state/agent-cell-memory` |
| `resident/replay.py:12` | 同上 | `…/projects/omo/.omo/state/agent-cell-replay` |
| `resident/refine_rollback.py:52` | `Path(".omo/state/refinements")`，`__init__` 即 `mkdir` | **进程 cwd** 下（state 根为空） |
| `resident/sema_crystallizer.py` `DEFAULT_RULES_REL` | `.omo/state/hard-negative-rules.jsonl`（相对量） | 进程 cwd |
| `pipeline_supervisor.py:30` `_ws()` | 沿 `parents` 找 `docs/project-registry.yaml`，兜底 `Path.cwd()` | `/Users/xiamingxing/Workspace`（检出根，不读 profile） |

`parents[3]` 的错位是**数错两级**：文件在 `…/projects/omo/src/omo/resident/x.py`，
`parents[0]=resident`、`[1]=src/omo`、`[2]=src`、`[3]=projects/omo`，而工作区是 `parents[5]`。
同一个包里 `resident/__init__.py:18` 用的正是 `parents[5]` —— 也就是说缝的锚点在这些模块里被各自
重算了一遍，且算错。`state_root()` 与 `write_path()` 在 `resident/**` 里被 31 个文件调用（实测计数），
这 5 个文件**一次都不调用**。

## 2. 后果：代码树里长出第二棵状态树，且与真面分叉

`projects/omo/.omo/state/` 实测存在，10 个文件约 1.07 MB：

```
agent-cell/cell_states.json                  2B        ← 根面同名文件是 906,816B
agent-cell/governance-audit.jsonl            757B
agent-cell/memory-network/{published,subscriptions}  1,918B / 139B
agent-cell-memory/{memories,candidates,conflicts}.jsonl  53,364B / 50,032B / 432,364B
agent-cell-replay/{episodes,eval_results}.jsonl          27,314B / 855B
refinements/                                           (空目录，mkdir 留下)
```

三种损坏方式同时成立：

1. **读写各读一份**（同名分叉）：`agent-cell/cell_states.json` 在检出根面 906,816B、在子模块面 2B，
   两者 `cell_states` 语义相同。`cell_state.py` 对 2B 的桩做读—改—写，真状态在另一棵树里滚动。
2. **只有代码面存在**：`agent-cell-memory/**` 与 `agent-cell-replay/**` 在根面 `ABSENT`。任何按
   `state_root()` / 检出根解析的读者**读不到**这些积累数据。
3. **数据住在代码仓里**：这些文件在 `projects/omo` 的工作树内、该子模块 `.gitignore` 未覆盖
   `daemon|healer|memory|notification` 那批兄弟目录，`git -C projects/omo status --porcelain
   --untracked-files=all .omo/state` 实测 15 行 `??`。它们随每次 `submodule update` / `git clean` /
   worktree 释放处于可被销毁的位置。

对 ADR-0456 的直接后果：**B4b 的正确性前置**。`~/.local/opt/omostation` 与 `~/Workspace` 是两棵独立
clone；只要写者锚在代码树内，两棵 clone 各带一份 `projects/omo/.omo/state/**`，运行时代码一改道
就当场分叉出两套 agent-cell 记忆与回放。

## 3. 契约（8 处，一律调用时刻解析）

- C1 五个 `parents[3]` 模块的目录常量改为经 `omo_paths.state_root()` 派生（`STATE_DIR` 同族的
  既有写法是 `omo_paths.py:140 STATE_DIR = STATE_ROOT / ".omo" / "state"`，本轮不新造形状）。
- C2 三个 CWD/标记上溯的写者（`refine_rollback` 两处、`sema_crystallizer`、`pipeline_supervisor._ws()`）
  同样经 `state_root()`；显式传入的 `store_dir` / `snapshot_dir` 参数优先级不变（测试隔离面保留）。
- C3 写落点若需要绝对化，仍走 `resident.write_path()` 缝（实测它把检出冻结路径正确重定位到 state 根，
  且解析无副作用）。
- C4 **不许写半份镜像**：state 根那份不存在时不得凭空造出一份只含自己键的树（AGENTS.md §7
  「harness-omo-bridge.py:193」那条不变式在这里同样成立）。
- C5 未声明 profile 时 `state_root() == 检出根`，除 §5 的改道效应外逐字节复现历史路径；
  这条不变量由既有 `tests/unit/test_repo_root_profile.py` 钉住，本轮不放宽它。

## 4. 验收（每条都配正向落点断言，先跑一次再写进契约）

- V1 声明 `OMOSTATION_STATE_ROOT=<tmp>` 后求值 8 个写者的落点，全部 `startswith(<tmp>)`。
- V2 从**与检出无关的 cwd** 实例化 `RefinementStore`/`SnapshotManager` 与 `sema_crystallizer` 默认路径，
  产物不落 cwd（当前实测会落，见 §1 表）。
- V3 `git -C projects/omo status --porcelain --untracked-files=all .omo/state` 在修后的一次运行里
  **不新增**行（存量文件的处置见 §5）。
- V4 变异对照：把缝的任一侧改窄，对应断言当场红；「绿」不得来自检测器没命中。
- V5 判据与被检对象不同源：落点断言一律用 `state_root()` 的**返回值**比较，不用 `__file__` 反推。

## 5. 明确不做（需 principal 单独授权的动作）

- **不迁移、不删除** §2 那 10 个文件。改道后写者会开始写 `state_root()` 那份，`cell_states.json`
  的 2B 与 906,816B 谁覆盖谁是**数据决定**，不由本轮代码替人做出。
- **不碰** launchd、plist、crontab、权威 ledger 翻转。
- 若需要旧值：显式取快照（`omo ledger snapshot` 一族，B4b 批次 1 已有契约），不在代码里加静默兜底。
