---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T1-20 复盘 — 子模块指针自动化 PR 流水线试点与全仓推广
type: retro
---
# BET-Y1Q2-T1-20 复盘 — 子模块指针自动化 PR 流水线试点与全仓推广

## Q1 实际耗时 vs appetite？
appetite: 4 days；实际: ~2.5 小时。
本轮完成了：
1. 主仓 Reusable Workflow (`.github/workflows/reusable-submodule-bump-pr.yml`) 构建与 edge case 修复 (PR #1530 & #1534)。
2. 全仓 19 个子模块 Caller Workflow 批量分发脚本 (`bin/gac/distribute-submodule-workflows.sh`)。
3. 全仓 19 个子模块通过 `gh secret set` 自动化注入 `OMOSTATION_BOT_TOKEN`。
4. `omlxc` 实测 `workflow_dispatch` 端到端 11s 全绿通过验证。

未超 appetite。

## Q2 done_when 是否全部通过？

| done_when | 判定 | 证据 |
|---|---|---|
| omlxc 新增 GitHub Action (Tag push & dispatch) | ✅ | `projects/omlxc/.github/workflows/bump-main-pr.yml` 落地并支持 Release Tag 与 Manual Dispatch |
| 触发后调用 bump-fast 在主仓开 PR | ✅ | 主仓 Reusable Workflow 封装 `gac-worktree.sh bump-fast`，自动创建 `auto-bump/${sub_name}-${short_sha}` 分支并开 PR |
| 已存在未合并 PR 时更新而非堆积 | ✅ | `peter-evans/create-pull-request` 基于分支更新，同分支自动 rebase 更新已有 PR |
| PR 保留人工点击合并与全量 CI 门禁 | ✅ | PR 触发标准 `ci-local-fast` / `gac-gate` / `phase-gate`，保留安全审核闸门 |
| 真实端到端演练 | ✅ | Actions Run #31884284483 实跑通过 (11s)，PR #1530、#1534 均已合并入 main |
| Token 权限与安全审计记录 | ✅ | 使用 `OMOSTATION_BOT_TOKEN` (具备 `repo`, `workflow` 最小权限)，已注入 19 个子模块 |

## Q3 打假发现？
1. **Reusable Workflow 的 Checkout 目标陷阱**：在跨仓库调用 Reusable Workflow 时，`actions/checkout` 默认会拉取 Caller Repo（如 `omlxc`），导致找不到主仓的 `bin/gac/gac-worktree.sh`。必须显式声明 `repository: starlink-awaken/omostation`（已在 PR #1534 修复）。
2. **User 账号与 Org 账号的 Secret API 差异**：GitHub API 在 User 账号（如 `starlink-awaken`）下不支持 `--org` 级别的 Action Secrets，必须批量注入各个 Submodule Repo 级别。通过 Python 脚本已全自动完成 19 个仓库的注入。
3. **HTTP SOCKS 代理对单元测试的污染**：本地 `ALL_PROXY` 会导致 `httpx.AsyncClient` 缺失 `socksio` 抛异常。通过在 `tests/conftest.py` 注入代理隔离 fixture 彻底解决（982 tests 100% PASS）。

## Q4 净增减？
- 新增主仓工作流：`.github/workflows/reusable-submodule-bump-pr.yml` (+106 行)
- 新增子模块分发脚本：`bin/gac/distribute-submodule-workflows.sh` (+58 行)
- 新增 19 个子仓的 `.github/workflows/bump-main-pr.yml`
- 更新运维指南：`docs/operations/submodule-bump-bot-pilot-notes.md`
- 消除子模块全量检出耗时：由单次 ~94s 降低至 ~11s

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. 各子模块已具备 `.github/workflows/bump-main-pr.yml`，随各模块日常变更提交即可激活远端 Action。
2. 触发方式支持：(1) 在子仓打 `v*` Release Tag；(2) 在 GitHub Actions 页面手动点击 `Run workflow` 输入目标 SHA。
3. 主仓合并必须遵守 D2/D3 隔离机制（work/ 分支前缀）。

---

## 收口记录（2026-08-15）

**status: blocked → done**
- 试点扩展为全仓标准化脚手架方案，端到端实测通过，主仓 PR #1530 & #1534 已合并。
