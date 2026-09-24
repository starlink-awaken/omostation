---
type: operations
status: active
owner: governance-agent
created: 2026-09-24
last-reviewed: 2026-09-24
scope: workflow-requirement-iteration-waiver
---
# Workflow Waiver Record

**Date**: 2026-09-23（三次交付）/ 2026-09-24（本记录 + 修正交付）
**Agent**: governance-agent
**Escape hatch**: `AGCP_REQUIREMENT_ITERATION_GATE=0`（`requirement-iteration start requires --bet`）
**用于**: workflow `start` 与 `closeout`（后者同样因无 bet 而断 vision→retro 链）

## Reason

ADR-0203 的 requirement-iteration 门要求 `start --bet <BET-ID>`，但 **3Y-BET-LEDGER 当时 448 条 bet 全部
`status: done`，开放数为 0**（`docs/plans/3y-bet-ledger.yaml` 实测），不存在可绑定的 bet。
因此这不是"跳过门禁图省事"，而是**台账耗尽后的结构性必然**：只要继续交付，就必须走豁免。

> 本记录同时是该空档的可审计报告（"只报告，不处置"）：台账规划权属 principal，Agent 未增删任何 bet。
> 在补充新 bet 之前，**后续每一次交付都会需要同类豁免**——这是需要 principal 决策的点，不该被 env 变量静默抹平。

## Authorized Work

| PR | merged SHA | 内容 |
|----|-----------|------|
| #4244 | `b229a77da` | Agent Brief `resolve-failing-gates` 时效性提示 |
| #4245 | `b7052a2a6` | 两条治理踩坑固化（PITFALL-GAT-011 + pattern） |
| #4246 | `5b1564662` | `docs/operations/claims-activation-checklist.md`（只读） |
| #4266 | `af33a3e80` | 复盘 findings F1–F4 修正：豁免留痕、删除无消费方字段、Claims 数值指针化、修 `gen-knowledge-index.py` 前缀元数据丢失 + 重建知识索引 |
| #4275 | `a05524920` | 二次复盘 findings H1–H3：`submodule-reachability-gate.py` 网络工作加有界预算（超时降级为 unverified 而非 unreachable）、`hook-runner.sh` 死超时参数改名并说明真相、生成物（BRIEF.md / CLAUDE.md 注入段）去除主机绝对路径 |
| #4280 | `4f8a64705` | 把上一行 "PR 待登记" 占位符绑到真实 PR（#4275 / `a05524920`）——占位符本身就是 F1 要消灭的东西 |
| #4285 | `0a129eb13` | 固化本次复盘教训为 error-knowledge 条目 PITFALL-GAT-012（pre-rebase 缺执行位是保护而非缺陷）+ PITFALL-MEA-004（hook-runner 死超时参数）；同一豁免（`governance-state-mutation` run 20260924T072410Z） |

## User Confirmation

- "可以，依次推进吧"（授权按 #4 → #5 → #1 顺序推进）
- 既有常置授权链："pr 合并提交" / "我给你授权，推进吧"
- 复盘后选择："F1 补豁免留痕、F2 删死字段、F3 数值指针化、F4 补可发现性；F5 只报告不处置"
- 二次复盘："go"（授权处置 H1/H3；H2 经实测改判为**只报告**，见下）

## H2 改判（实测推翻初始假设）

初始报告称 `.githooks/pre-rebase` 缺执行位是缺陷。实测三点推翻：

1. `SWARM_ESCAPE_ID=rebase-ci bash .githooks/pre-rebase HEAD^ origin/main` → 仍 exit 1，文档宣传的逃生口是死的
   （`[ "$x" != rebase-* ]` 是字面串比较，只有 `[[ ]]` 才做模式匹配）。
2. git 的 `pre-rebase` 签名是 `<upstream> [<branch>]`，`$2` 是被 rebase 的分支名而**不是 onto**，
   所以脚本从未实现它声称的"拒绝 rebase onto main"。
3. 在落后于 main 的分支上 `git rebase origin/main` 会被该 hook exit 1 拦下——而这正是 PITFALL-GAT-007
   规定的 push 前动作。**补上执行位等于让全场 Agent 的 push 前 rebase 失败**。

因此 H2 不修：激活危害大于收益，且修复方向（重写判定逻辑 + 真正的逃生口 + 回归测试）超出本次"有界性"范围。
已作为需 principal 决策项上报。

## Boundary

- Claims Authority 激活保持 fail-closed，未由 Agent 代办；#4246 仅为只读文档。
- 未补录价值记录（30 条门保持 NOT_PROVEN）；未做 weekly-review（principal-only）。
- 台账未改动。

## Follow-up

本记录自身的存在即是 F1 的修正：此前三次豁免只落在 `.omo/_delivery/*`（gitignored），git 上零痕迹。

需要区分两套**互不相通**的 waiver 机制，避免误以为本记录会生效于门禁：

| 位置 | 消费方 | 契约 |
|------|--------|------|
| `docs/operations/workflow-waiver-<date>-<slug>.md` | 人 / git 审计痕迹（本文件） | 无机器读取方 |
| `.omo/_truth/governance-evidence/waiver-*.md` | `bin/gac/check-governance-ratio.py::_active_waivers()` | frontmatter `status: active` + `pr_numbers` 命中 `GITHUB_PR_NUMBER` |

`check-governance-ratio.py` 只认第二处，且是**治理配额上限**的单 PR 豁免，与 `AGCP_REQUIREMENT_ITERATION_GATE`
无关。本次交付未触配额上限，因此**未**创建第二类豁免记录——若后续需要，必须显式登记 `pr_numbers` 才有效。

