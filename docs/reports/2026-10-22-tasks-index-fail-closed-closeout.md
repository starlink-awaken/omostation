---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-22
bet_id: BET-Y2Q4-T10-264
---

# BET-Y2Q4-T10-264 收口 receipt — tasks/registry/INDEX.md 重建对「面缺席」fail-closed

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-264`
规格：`docs/superpowers/specs/2026-10-22-tasks-index-rebuild-fail-closed.md`（spec_version 1.0.0，
digest `sha256:685f5519c35bf4e6b9eec8b9bd73b5aa2a02b5e4dae6cf27094fb36afa3d6207`，台账 `content_digest`
与该字节逐字一致 — 交付前用 `hashlib.sha256(spec.read_bytes())` 复核过）
交付：工程腿两仓两次合并 —— 子仓 omo PR #221 squash 为 `980b9cbfb05cdb178af8f19acc8794b2f8a01b61`；
父仓 PR #4857 squash 为 `76602956f14bdbcfbcdc27c86f108b0706c198b3`（含 AGENTS.md §7 固化、spec、台账
`in_progress` 条目、`projects/omo` gitlink bump）

## 1 缺陷与实测证据

`_rebuild_tasks_registry_index()`（`projects/omo/src/omo/omo_state.py:210`）从
`tasks/<plane>/*.yaml` glob 派生四张面，兜底写法是 `… if dir.exists() else []`。
于是 **「目录不存在」与「目录存在但没有 YAML」在返回值上逐字节同形**，函数无法区分，照常重建。

真实后果（2026-10-22 本机会话实测）：一次 `omo state sync-tasks` 在**没有 `tasks/planned/` 的检出**上运行
（该面被 `.gitignore:402` 忽略，fresh/detached 检出按构造不含它），把**被跟踪的**
`.omo/tasks/registry/INDEX.md` 从 `## Planned Tasks (7 个)` 重写成 `(0 个)`，
连 `TASK-019B7FD6` 在内 7 行规划任务被删除。判据：`git check-ignore -v .omo/tasks/planned`
命中 `.gitignore:402`。

规范检出（`/Users/xiamingxing/Workspace`）四张面齐全（active 1 / planned 6 / blocked 0 / done 50，
另有 archived+done 290），INDEX 读数本就正确 —— 所以这不是「本机坏了」，而是**任何一次在别处检出的
sync 都会写坏并作为交付回流**。

## 2 修复与验证读数

修复（子仓 `980b9cb`）：重建前要求 `active/planned/blocked/done` 四目录**全部存在**，
任一缺席即 `return False`（调用方保留 INDEX 原字节并打印「未重建」）。目录存在但为空仍照常重建。

| 验证项 | 命令 | 读数 |
|---|---|---|
| 目标用例 | `uv run --no-dev --with pytest --with pyyaml python -m pytest projects/omo/tests/test_omo_cli_modules.py -q` | `67 passed` |
| 变异反证 | 摘掉新增守卫后同文件重跑 | `2 failed, 5 passed`（缺席面两条用例当场红）|
| 格式 | `ruff check` / `ruff format --diff` | 自身新增处已 format，无残留 |
| 子仓 CI (#221) | `gh pr checks 221` | `lint` / `test` / `test-cov` 全 pass，`mergeStateStatus=CLEAN` |
| 父仓 CI (#4857) | `gh pr checks 4857` | 全部 resolved，无 fail，`mergeStateStatus=CLEAN` → 已合并 |
| 本地门禁 | `make gac-local-gate` | 逐条 `[PASS]`；残余为环境类 soft warn（`test-mcp-kos` exit 78 = KOS 库是未跟踪运行态产物；`agent-workflow-status stale_locks=9` 属全机共享协调面，未按 prune-locks 处置）|
| 交付面 | `git diff --name-status origin/main..HEAD` | 恰好 4 条（AGENTS.md / 台账 / spec / `projects/omo`），无生成态、无反向 `D` |
| 安全 | L3 deep review（两仓、最终 commit set 各一次） | `findings_count: 0` |
| **干净 worktree 实跑**（done_when-4） | `PYTHONPATH=projects/omo/src python3 -m omo.cli state sync-tasks` | rc=0，打印「INDEX.md 未重建（缺失或结构不符，保留手维护）」；INDEX sha256 前后均 `de46c946194233fd…`，`git diff -- .omo/tasks/registry/INDEX.md` 为空 |
| 同轮的 system.yaml 侧（done_when-3） | 同上命令的 stdout | 计数仍被重算：`completed_tasks: 303 → 303`、`planned_tasks: 0 → 0`、`active_tasks: 1 → 1` —— 守卫只挡文档写，不挡计数面 |

新增三条命名用例（AGENTS.md §7 判据要求「先跑一次再写进契约」）：
`test_cmd_state_sync_tasks_leaves_index_untouched_when_a_plane_is_absent`、
`test_cmd_state_sync_tasks_still_rebuilds_index_when_plane_exists_but_empty`、
`test_rebuild_tasks_registry_index_refuses_absent_plane_and_accepts_present_ones`。

## 3 回滚

单提交回滚即可，无需数据恢复：子仓 `git revert 980b9cb`（守卫撤除，行为回到 glob 兜底），
父仓 `git revert 76602956f` 并回指 `projects/omo` 至 `36c64babc893f76afaa8a4d9b0ac7d6cf3946315`。
本修复**不写任何运行态**，故无运行面回滚项；被删的 7 行在本机上已由 INDEX 的历史版本保全
（缺陷是**未来的重写**，非既成数据损失）。

## 4 过程披露（两条与判据有关）

1. **浅历史 worktree 给出假「非祖先」读数**：在 `ws-index-shrink-guard/projects/omo`（`--is-shallow-repository=true`，
   `rev-list --count` = 2）上 `merge-base --is-ancestor 36c64ba 980b9cb` 返回 NO，且在 `--depth` 检出上
   `merge-base` 直接输出空。换到规范检出（深，792 commit）复测为 **YES**（`36c64ba → 4810186 → 980b9cb` 线性）。
   这是 AGENTS.md §7「可达性判据只在 canonical 或 `claim --full` 上做」的第四次实证，本轮据此才没有把
   re-pin 误判成需要另造提交。
2. **gitlink bump 顺带携带了 `4810186`**（子仓 Phase 11 multimodal/voice bridge，由另一 lane 在子仓合并）。
   未用 cherry-pick 造一条「只含我的改动」的合成提交 —— 那会让父仓指针脱离子仓 main 线性史。
   该事实写进 PR 正文，不在台账里掩蔽。

## 5 清理与边界

- 一次性装置 `runtime/affected/264-receipt.json`（affected-graph receipt）已在提交前删除，未进任何 commit。
- 未触碰：`~/Library/LaunchAgents`、crontab、`services.yaml`、权威 ledger 位置、`.gitignore`。
- 未宣布 ADR-0456 B1 / B3 / B4 / B5 或整个 plan 完成；本 BET 仅覆盖 B5 摘库留下的这一处写侧缺陷面。
