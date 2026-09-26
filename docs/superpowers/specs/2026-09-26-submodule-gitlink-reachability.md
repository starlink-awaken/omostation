---
schema_version: specification/v1
spec_version: 1.0.0
title: Submodule Gitlink Must Land On Child Default Branch
bet_id: BET-Y2Q4-T10-204
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
adr: ADR-0456
---

# 子模块 gitlink 落位契约（B1 内核侧回归复盘）

## Problem

B1（ADR-0456 profile root convergence, `BET-Y2Q4-T10-203`）的内核侧改动写在
`projects/omo`，主仓 gitlink 被指向子仓 **agent 分支**上的 commit `0790f897`。
主仓 CI 全绿、PR #4406 正常合并 —— 然后下一波 freshness 自动化把 pin 倒回
`c91b203e`，改动从 main 上消失，且没有任何门禁报错。

实测证据链：

| 事实 | 测量 |
|---|---|
| 倒回动作 | `28158b9bc` = `chore(submodule): freshness bump ecos+omo (#4405)` |
| 倒回是**有意的** | commit body 带 `[gitlink-regress: parent pin 0790f897 sits only on omo feature branch … freshness gate requires the pin to be the child main tip]` |
| 规则来源 | freshness gate 要求 pin == child `origin/main` tip |
| CI 为什么不报 | #4209 于 2026-09-22 从 `gac-gate.yml` 的可达性步骤删掉 `--require-main`（理由：cross-repo PR pattern），该步骤现在只跑 `--source head --fetch` |
| 净后果 | 内核侧 seam 丢失 4 天，靠人工比对才发现 |

不是 harness 漏判，而是**交付侧违反了契约却拿不到反馈**：pin 落在未合并的子分支上，
按既有规则注定被倒回。

## Contract

1. **任何主仓 commit 里出现的 `projects/<sub>` gitlink，必须已经是该子仓默认分支
   （`origin/main`）的祖先。** "push 到子仓 agent 分支" 不构成合法落位。
2. 子仓改动先经 PR 合并进 child main，再改主仓 pin；顺序不可颠倒。
3. 主仓 pin 变更一律走 `bin/ssot/submodule-pointer-transaction.sh`（唯一入口，
   `:105` `:114` 已内置 `--source worktree --require-main`），不手工 `git add projects/<sub>`。
4. `[gitlink-regress: <理由>]` 豁免标签只用于**降级确实不可用的 pin**（孤儿/悬空 SHA），
   不得用来降级"内容有效但尚未落入 child main"的 pin —— 后者是本文契约的违规，不是豁免。

## Adjacent finding（登记，不在本 bet 处置）

`tests/test_gac_gate_workflow_purity.py::test_reachability_and_generators_are_check_only`
自 #4209 起在 main 上恒红：它断言 CI 步骤等于
`… --source head --fetch --require-main`，而 #4209 有意移除了 `--require-main`。
测试与决策二者必有一处过期；改哪一侧属 principal 判断（涉及 #4209 的 cross-repo 授权边界），
本 bet 只登记不处置。恒红也说明该文件未被任何 CI surface 收集（`gac-local-gate` 本地绿）。

## Verification

- `git -C projects/omo merge-base --is-ancestor <root pin> origin/main` → exit 0
- `python3 bin/ssot/submodule-reachability-gate.py --source head --fetch --require-main` → 全绿
- 主仓 `projects/omo` pin 的内容可证：`git -C projects/omo show <pin>:src/omo/omo_paths.py`
  含 `STATE_ROOT_ENV` / `STATE_ROOT`（B1 seam 回归的判据）

## Out of scope

不改 `gac-gate.yml` / hook / `governance-checks.yaml`；不改 freshness gate 的 child-main-tip
要求；不动 crontab 与已安装 plist。
