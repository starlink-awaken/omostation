---
schema: md/v1
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: doc
review-state: metadata-fresh
title: BET Ledger Closeout SOP — 5 步标准流程 (A2)
---

# BET Ledger Closeout SOP — 5 步标准流程

> **Status**: ACTIVE · **Owner**: governance-team · **Last updated**: 2026-09-19
> 来源: `docs/OMOSTATION-FORWARD-PLAN.md` A2 — 跨 repo 流程模板化
> 目标: 把 5+ 种 closeout 工作流 (PR #3585/#3703/#3715/#3730/#3753/#3766/#3768/#3791/#3805/#3823/#3958) 收敛成统一 SOP

## 0. 概述

BET closeout = 把完成的 BET (从台账 `docs/plans/3y-bet-ledger.yaml`) 闭环：retro → ledger status flip → done_at → evidence matrix → PR merge。 本 SOP 强制 5 步顺序, 防止"closeout 跳步漏 retro"或"retro 写完不绑台账"两类典型 bug。

## 1. 适用场景

- BET done_when 已实现 (代码 + 测试 + retro 草稿齐备)
- 台账条目仍处于 `status: in_progress` 或 `status: started`
- 需要在 `docs/plans/3y-bet-ledger.yaml` 把 status flip 到 `done`

## 2. 5 步标准流程

### Step 1 · Worktree claim (隔离 + 顺序锁)

```bash
# 必用 PASW (Parallel Agent Safe Worktree) 入口
bash bin/gac/gac-worktree.sh claim <bet-id>

# 自检: claim exit 0 + next-adr-hint 输出
cd ws-<bet-id>
git log --oneline -1 origin/main  # 必须显示 base = main HEAD
git submodule update --init       # 防指针回退 (PITFALL-SW-002)
```

**失败信号**: claim exit != 0 → 检查 `gac-worktree.sh status <session>` 看锁; submodules 未 init → 跑 `git submodule update --init` 后再继续。

### Step 2 · Implement / Verify / Retro (3 子步骤)

#### 2.1 Implement — 实现 + 测试

- 改 done_when 列出的文件 (不允许扩大范围)
- 跑 targeted tests (见 `AGENTS.md §8`)
- 收尾本地提交 (后续 closeout PR 不混入未交付代码)

#### 2.2 Verify — 落 evidence

```bash
python3 bin/ssot/doc-governance-check.py --no-new-warnings
python3 bin/ssot/script-registry.py validate
python3 bin/plan/bet-ledger.py lint  docs/plans/3y-bet-ledger.yaml
make gac-local-gate
```

#### 2.3 Retro — 写 retro

- 路径: `.omo/_knowledge/retros/<bet-id>.md`
- frontmatter 必填: `bet_id`, `status`, `lifecycle: history`, `owner`, `last-reviewed: <UTC 当天或更早>`, `type: ephemeral`
- 四问结构: Q1 intended / Q2 happened / Q3 changed / Q4 lessons (P73 truth-driven)
- 末尾"相关": receipt / ledger / 前置 PR

### Step 3 · Closeout (改台账 + 完成证据)

```bash
# 3.1 改台账条目: status → done, done_at, completion_evidence
python3 bin/plan/bet-ledger.py status <bet-id> --done
# 或手工编辑 docs/plans/3y-bet-ledger.yaml 的对应 bet 段:
#   status: done
#   done_at: "<UTC datetime>"
#   completion_evidence:  {schema_version, axes: {engineering/operational/value}, overall_state}

# 3.2 验台账
python3 bin/plan/bet-ledger.py lint

# 3.3 workflow closeout (一次性元数据)
uv run --with pyyaml python bin/agent-workflow.py closeout <run-id> \
  --status ok --evidence "PR #<n> merged as <sha>; <验证摘要>" --from-diff
```

**失败信号**: `BET_DONE_AT_REQUIRED` → done_at 缺失; `SPEC_BINDING_REQUIRED` → 缺 spec 绑定; `missing_retro` → retro 未落盘。

### Step 4 · Commit-Push-Rebase (PR 准备)

```bash
# 4.1 一次性 commit (含台账 flip + retro + CE matrix)
git add docs/plans/3y-bet-ledger.yaml .omo/_knowledge/retros/<bet-id>.md
git status  # 必须显式列路径, 禁 git add -A (PITFALL-COO-003)
git commit -m "fix(<scope>): close <bet-id> — done_at + retro + CE"

# 4.2 防并发 main 演进: 先 rebase
git fetch origin main
git rebase origin/main
# 冲突处理: 优先保留 main 版 (并行 agent 权威, PITFALL-GAT-006)

# 4.3 push
git push -u origin agent/governance-agent/<bet-id>

# 注意: agent/governance-agent/<x> 格式才能 push; feat/... 需先 PR
```

**电路保险** (circuit breaker):
- rebase 遇冲突 → 取 main 版 + `[bet-conflict: <reason>]` 注释
- push 遇 gitlink regress → 自动 forward-sync (脚本: `bin/ssot/submodule-pointer-bump.sh`)
- 不允许 `--no-verify` 跳过 pre-commit

### Step 5 · PR + Merge (admin squash)

```bash
# 5.1 开 PR (admin 权限, protected branch 必须)
gh pr create \
  --title "fix(<scope>): close <bet-id> — <一句话>" \
  --body-file docs/reports/<date>-<bet-id>-closeout.md   # 或 inline heredoc

# 5.2 等 CI 全绿 (gac-gate / governance-verify / interface-check 必须 pass)
gh pr checks <pr-num> --watch

# 5.3 squash 合并 (保留单 commit 历史)
gh pr merge <pr-num> --admin --squash --delete-branch

# 5.4 清理 worktree
cd ../.. && git worktree remove --force ws-<bet-id>
git branch -D agent/governance-agent/<bet-id>
```

**失败信号**: CI fail → 跑 `bin/gac/ci-red-triage.py` 分诊 (skill `ci-red-triage`); PR mergeStateStatus=BLOCKED → 修冲突后 rebase; mergeStateStatus=DIRTY → 同上。

## 3. 跨 repo 适配 (A2 关键)

| repo | 工具 | 差异 |
|------|------|------|
| `omostation` (主仓) | `bin/gac/gac-worktree.sh` | 5 步全适用 |
| `omostation-cockpit-ui` | `gac-worktree.sh` 自带 | pre-commit 配置不同, 跳过 cockpit-ui 自有 checks |
| `omostation-omlxc` | 同上 | 改完需 `git submodule update --init` 后再 gitlink bump |
| `omostation-runtime` | 同 omostation | 缺 `bin/gac/`, 用原生 git worktree + push |
| `omostation-family-hub` | 同 omostation | 需要额外跑 yarn lint (subtree 关系) |

**统一入口**: 任何 repo closeout 都遵循 5 步框架, 第 4 步 push 路径可能不同 (`agent/governance-agent/<x>` 是主仓强制; 子仓可 `feat/<x>`)。

## 3.5 Closeout-branch Skip (A3, 2026-09-19)

- **机制**: `bin/gac/auto-fix-loop.py` v2 新增分支检测
- **触发**: 分支含 `-closeout`/`-retro`/`-ledger`/`a[1-9]-`/`bet-execution-` 任一模式
- **效果**: 跳过 `FRONTMATTER-MISSING` 对 `.omo/_knowledge/retros/*.md` 的修复
- **强制启用**: `SKIP_FIX_LOOP_BRANCH=1` 环境变量
- **原因**: closeout PR 携带 retro 时, auto-fix 把 `last-reviewed` 改成今天会产生
  第二个 commit, 与本地 ledger 不同步 (PITFALL-COO-005, 复盘 batch 31)

```bash
# 验证 (在 closeout 分支):
$ python3 bin/gac/auto-fix-loop.py --json | jq '.drifts[].kind'
"PATH-DRIFT"
"FRONTMATTER-MISSING-RETRO-SKIPPED"   # ← A3 新增, retro 跳过
"FRONTMATTER-MISSING"                  # ← 非 retro 仍正常修复
```

## 4. 常见坑速查

| 症状 | 根因 | 修复 |
|------|------|------|
| `SPEC_BINDING_REQUIRED` | closeout 步 3 没绑 spec | 步 1 加 spec_ref / content_digest |
| `missing_bet_binding` | closeout 步 2 没 start | `agent-workflow.py start ... --bet <id>` |
| `BET_DONE_AT_REQUIRED` | 台账 flip 时漏 done_at | 步 3.1 加 `done_at: <UTC>` |
| `missing_retro` | retro 文件不存在 | 步 2.3 先写 retro |
| `gitlink-ancestry fail` | closeout 期间 main 演进快 | 步 4.2 rebase 后 bump submodule |
| `pre-commit auto-fix-loop` | 步 4 commit 后 auto-fix 改 retro frontmatter | A3 (skip on closeout branch) |
| `mergeStateStatus=BLOCKED` | rebase 不彻底 | 重做步 4.2 + 重 push |
| URL 漂移 | kairon/oaiffer 子模块 origin 错 | `bin/ssot/fix-remotes.sh` (T10-169 模式) |

## 5. 自动化候选 (P2)

- `bin/plan/bet-closeout-auto.sh <bet-id>` — 把步 3-4-5 打包成单脚本
- pre-commit skip-flag: closeout branch 检测 → 跳过 auto-fix-loop (A3)
- ledger 改完自动验台账 + lint + gh-pr-create

## 6. 相关

- `docs/OMOSTATION-FORWARD-PLAN.md` §A2 — 任务来源
- `.agents/skills/bet-closeout-chain/SKILL.md` — 8 步详细版 (含 spec binding)
- `.agents/skills/git-discipline/SKILL.md` — git 纪律补充
- `.agents/skills/ci-red-triage/SKILL.md` — CI 失败分诊
- `.agents/skills/worktree-ci-isolate/SKILL.md` — worktree 隔离
- `.omo/_knowledge/retros/LESSONS-LEARNED-2026-09-16.md` — 14 节实战经验
- `.omo/_knowledge/patterns/p104-ledger-closeout-reuse-existing-work.md` — 0 行新代码 closeout

## 7. 验证清单

- [ ] Worktree claim exit 0 + 路径 `ws-<bet-id>` 创建
- [ ] `git submodule update --init` 跑过
- [ ] retro 落 `.omo/_knowledge/retros/<bet-id>.md`, frontmatter 七件套齐
- [ ] 台账 `status: done` + `done_at` + `completion_evidence`
- [ ] `python3 bin/plan/bet-ledger.py lint` PASS
- [ ] `make gac-local-gate` PASS
- [ ] `gh pr create` 成功
- [ ] CI 全绿 (gac-gate / governance-verify / interface-check / test)
- [ ] `gh pr merge --admin --squash --delete-branch` 成功
- [ ] Worktree 清理 (`git worktree remove`)