---
type: retro
bet_id: BET-Y2Q1-T7-07
status: completed
owner: governance-team
last-reviewed: 2026-09-16
pr: https://github.com/starlink-awaken/omostation/pull/3803
merge_commit: f49c76eb70ef5d81837ad277d4c4aa5c6e022ebb
---

# BET-Y2Q1-T7-07 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 0.5 day；同会话内完成状态机修复、journey 补齐、影子台账删除与 T10-151/146 虚假 done 回退，PR #3803 已 squash 合入。未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- approve(退回) 后 dispatch 拒绝；同意路径仍可 dispatch — PASS（`test_doc_pipeline` neg-return-dispatch）
- journey 文件存在且 scene-card related 可解析 — PASS
- T10-151 不再标 done — PASS（回退为 `candidate` + reopen_reason）
- 不再跟踪 `.omo/plans/3y-bet-ledger.yaml` — PASS（`git rm`，#3803）

## Q3 过程中发现的与 plan 不符的事实（打假）？
1. T10-151 标 done 时 A8 实现不可达于当前 `projects/omo` pin；父 BET T10-146 也被标 done，虚假完成向上传染。
2. 影子台账 `.omo/plans/3y-bet-ledger.yaml` force-tracked，与 SSOT 冲突。
3. 场景卡在 T7-06 done 时已引用不存在的 journey 文件。
4. 校准叙述声称 6 类熔断进 F1，实现只注入登记/版式缺陷；已改为叙述与实现一致。
5. `gac-worktree submit` 现为 proposal-only（需 clone-lifecycle）；本交付以 direct push + `gh pr merge` 完成。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
- 代码：`doc_pipeline.py` / `test_doc_pipeline.py` 小幅净增（状态机分流 + 负例）
- 文件：+1 journey spec；+1 remediation spec；+1 retro；-1 影子台账
- GaC / ADR / 脚本：0

## Q5 下一个认领本 track 的 agent 需要知道什么？
- T10-151 / T10-146 现为 `candidate`：必须先把 A8 实现合入 `projects/omo` pin 再 closeout。
- 退回语义：`returned` 可 `draft_opinion` 重入；不可 `dispatch`/`export_package`。
- verify 统一 `uv run --with reportlab`，不要依赖「.venv 已装」叙述。
