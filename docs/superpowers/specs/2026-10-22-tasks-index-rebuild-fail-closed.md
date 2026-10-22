---
schema_version: specification/v1
spec_version: 1.0.0
title: tasks/registry/INDEX.md 重建对「真源面缺席」必须 fail-closed
bet_id: BET-Y2Q4-T10-264
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-22
---

# tasks/registry/INDEX.md 重建对「真源面缺席」必须 fail-closed

> 范围：`projects/omo` 的 `omo state sync-tasks` 索引重建写者。不改 system.yaml 计数语义，
> 不改 `.gitignore`，不摘库，不动门禁判据本体。

## 1. 缺陷证据（实测，2026-10-21 / 2026-10-22 两次）

跟踪文档 `.omo/tasks/registry/INDEX.md` 的 Active/Planned/Blocked/Completed 四段是**派生段**，
由 `omo state sync-tasks` 从 `.omo/tasks/{active,planned,blocked,done}` 目录重算后整段重写
（写者：`projects/omo/src/omo/omo_state.py:_rebuild_tasks_registry_index`，
真源读取：同文件 `cmd_state_sync_tasks` 的 `files = sorted(d.glob("*.yaml")) if d.exists() else []`）。

而这三类面里 **planned 与 done 被 gitignore**（`.gitignore:401` `.omo/tasks/done/`、
`:402` `.omo/tasks/planned/`、`:131` `.omo/tasks/registry/done/`），
`git ls-tree -r --name-only origin/main .omo/tasks/planned/ | wc -l` = **0**。
⇒ 在**任何干净检出**（CI、新 worktree）里，planned 面物理缺席，而 INDEX.md 是被跟踪的、
带着某台机器写进去的 7 条 planned 行。

真源读取把「目录不存在」和「目录存在但为空」**折叠成同一个 `[]`**，
`_rebuild_tasks_registry_index` 的结构守卫（`if not (n_active and n_planned and n_blocked and n3): return False`）
只校验正则**是否匹配上**，不校验**输入面是否真的存在**，于是折叠后的 0 直接落进
`write_text_atomic(index_file, text)`。

实测后果（2026-10-21，一次 `make gac-local-gate` 在 worktree 内触发 sync）：

```diff
-## Planned Tasks (7 个)
+## Planned Tasks (0 个)
-| TASK-019B7FD6 | aetherforge 网关密钥轮换 | candidate |   （×7 行被删）
```

2026-10-22 在同一基线（`d7b2c0561`）的新 worktree 里逐面读数：
`planned` exists=**False**（文档却写 7）、`done` exists=True yaml=**13**（文档却写 331）、
`archived/done` yaml=290、`blocked` exists=True yaml=0、`active` yaml=1。
⇒ 一次 sync 会把 tracked 文档的 planned 段从 7 收缩为 0，并把 Completed 计数改写为 303。

危害不是「多一个脏文件」，而是：**一个被跟踪的治理文档的内容，取决于这台机器上有没有一个
被忽略的目录**，且收缩型重写会被 hook 顺手扫进任意交付 commit（AGENTS.md §7「生成态会被交付
动作扫进 commit」同族），把别人的任务清单静默删掉。

## 2. 契约

- **C1 缺席即不写**：`_rebuild_tasks_registry_index` 在它派生所依赖的四个面
  （`tasks/active`、`tasks/planned`、`tasks/blocked`、`tasks/done`）中**任一个不存在**时
  MUST 返回 `False` 且不写 INDEX.md。上报走调用方既有的
  `⚠️ tasks/registry/INDEX.md 未重建 (缺失或结构不符, 保留手维护)` 分支，不新增措辞、不新增出口。
- **C2 空面仍合法**：目录存在但为 0 个 yaml 时，仍按真源写 0 —— 那是真实状态，不是缺席。
  守卫的判别式是 `exists()`，不是计数。
- **C3 只挡文档写**：`system.yaml` 的计数重算与本守卫**无关**，一律照旧（它是 state 面文档，
  T235 起被 `.gitignore:297` 正向忽略；其空形语义由 T236 裁定，本轮不得触碰）。
- **C4 不新增根/环境名/路径逻辑**：本轮不碰 `repo_root`、不碰 `system_yaml_for`、
  不新增 env 名（ADR-0456 的定位链只有那三条）。
- **C5 不摘库**：INDEX.md 继续被跟踪。摘库需要逐个审计 `planned_tasks_ref` 一类读侧消费者，
  属 B5 的独立决定面，不在本 BET。

## 3. 实现点

| 面 | 改法 |
|---|---|
| `projects/omo/src/omo/omo_state.py` | `_rebuild_tasks_registry_index` 内，在 `index_file.exists()` 检查之后、任何 `re.subn` 之前，加四面 `exists()` 前置判定并 `return False`（返回类型不变，签名不变） |
| `projects/omo/tests/test_omo_cli_modules.py` | ① 反面：四面齐 + planned 有 1 行 → 删 `tasks/planned` 目录 → 跑 sync → 断言 INDEX **逐字节不变**且 system.yaml 计数**仍重算**（证明守卫只挡文档写）② 事故复刻：planned 段 7 行 + 面缺席 → 断言 7 行存活 ③ 正面：四面都存在（含存在但为空）→ 断言仍重建（防过宽） |
| `AGENTS.md` §7 | 固化一条：跟踪文档由忽略面派生 = 收缩型写者；INDEX.md 不是「纯时间戳脏项」，脏了要按 §1 判据分类处置 |

子模块 gitlink bump 走 `bin/ssot/submodule-pointer-transaction.sh` 的常规通道，
在父仓单独一个 commit（change-lane：omo 代码 / 父仓文档 / gitlink 分列）。

## 4. 验收

1. 三面反证用例在 omo 测试里跑绿，且**变异对照**：临时把守卫改回 no-op，用例 ① ② 当场红
   （AGENTS.md §7「扫源码的门禁必须自证」同族：空绿的代价是判据在写者没改完时就变绿）。
2. 干净 worktree（planned 面缺席）里跑一次 `materialize-system-state.py` + `sync-tasks`，
   `git diff -- .omo/tasks/registry/INDEX.md` 为**空**；改道前同一命令产生 7→0 收缩。
3. `make gac-local-gate`（或 `--scope staged`）绿；`git status --short` 除本轮 write_surfaces
   外无跟踪脏项。

## 5. 中止判据

- 若归零需要改 `system.yaml` 的计数或空形语义 → **停止**（T236 裁定面）。
- 若需要把 `.omo/tasks/registry/INDEX.md` 摘库、或动 `.gitignore` → **停止**（B5 决定面）。
- 若需要动 `bin/ssot/ssot-guardian.py:_count_tasks` 的判据本体才能过验收 → **停止**。
- 若既有用例因守卫转红，且只能靠改窄断言（而不是补物化真源面）转绿 → **停止并保留原判据**。
- 若需要新增 bin/ 脚本从而动 `script_baseline`（721）→ **停止**，另行登记。
- **不宣布 ADR-0456 B1/B3/B4/B5/B4b 或整个 plan 完成。**

## 6. 非目标

不 launchd / 不 crontab / 不写 `~/Library/LaunchAgents`；不改 `services.yaml`；
不把权威 ledger 翻到安装位；不做 B4b 批次 2 的 plist 改道；不同步任何检出的工作树。
