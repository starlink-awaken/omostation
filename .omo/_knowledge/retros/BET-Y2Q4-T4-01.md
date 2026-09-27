---
schema: md/v1
status: blocked
lifecycle: evidence
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
bet_id: BET-Y2Q4-T4-01
run_id: 20260926T113309Z-project-doc-change-820fd680
---

# BET-Y2Q4-T4-01 复盘（阻断，非 done）

## Q1 实际耗时 vs appetite？超出比例？

2026-09-26 11:33–11:43 UTC 约 10 分钟；appetite 1 工作日，尚未超时。分析与一张决策卡已在隔离 worktree 暂存，未完成全套验收，不记作 BET done。

## Q2 done_when 是否全部通过？哪条没过，为什么？

1. `docs/plans/2026-09-26-business-first-delivery-shortlist.md` 含 3 个按序候选及 1 个备选，各有目标草案、≤3 天工作量假设、价值判据与风险；已暂存。**内容通过，正式门禁未过**。
2. `.omo/tasks/planned/BET-Y2Q4-T4-01-DECISION.yaml` 由 OMO ingress broker 创建并暂存，`needs-human: true`；planned-task schema 与该卡 workorder 字段检查均无错误。**内容通过，正式门禁未过**。
3. `uv run --with pyyaml python bin/mof/generate-brief.py` 的只读输出包含本卡；但 Spec 中的字面命令 `python3 bin/mof/generate-brief.py` 在本机使用 Python 3.9，因 `datetime.UTC` 不存在而失败。**按原 verify 合同未通过**。
4. 卡已列明三天内、完整 BET 流程和不先建基建。**内容通过，正式门禁未过**。

`bet-ledger.py verify --execute` exit 1；`bet-ledger.py lint` 有 7 个既存错误（两个历史 BET 缺证据/状态不符、在途 Dashboard BET 的 Spec 摘要不匹配）；不将它们记成本 BET 新增。文件范围 GaC 的硬失败是 `change-lane-check: mixed lanes=docs,governance_state`：当前 `project-doc-change` workflow 只允许 `docs,governance_code,config`，但 accepted Spec 与 Ledger 要求同时交付 docs 分析和 `.omo/tasks/planned` 决策卡。GaC 还因新卡与旧 state 计数不同产生 `current-state-coherence` soft warning。全套 gate 未通过，不得 closeout 为 ok。

## Q3 过程中发现的与 plan 不符的事实（打假）？

- Spec 所述 `docs/plans/ vision-roadmap（4 YAML + 5 MD）` 并非一个现成同名文件夹；本轮显式核对 4 张场景 YAML、5 份愿景/战略/组合 MD 和当前 Ledger。`.omo/goals/current.yaml` 标明 `deprecated-use-bet-ledger`，不能作为进度权威。
- 4 张场景卡中的 `vault://redacted/...` 样本引用无法证明真实业务输入或采纳；候选仅是人类选择输入，不是 E4/E5 Outcome。
- `claim-check` 提示的 `project-doc-change` 与 accepted Spec 的跨 lane 写面矛盾；现有 `bet-execution` workflow 可允许两个 lane，但不能偷偷把活动 Run 改成另一 workflow 或用环境变量放过门禁。应由 BET/Spec owner 作受控合同修订后再安排续行，保留本轮证据，不重复创建卡或 Run。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

本分支目前新增候选分析、决策卡和本复盘共 **3 文件**；代码/规则/ADR/脚本均 0。新增内容是本 BET 明确要求的决策输入与证据，不扩张执行系统。`python3 bin/plan/bet-ledger.py surface` 的仓库总量显示 `test_loc` 较 2026-08 基线为正；该总量不能归因于本次改动。详细文件差异以 `git diff --cached --numstat` 为准。GaC 运行产生的 `.omo/state/system.yaml` 纯时间戳变化经逐字比对 HEAD 后已还原，未纳入交付。

## Q5 下一个认领本 track 的 agent 需要知道什么？

worktree `/Users/xiamingxing/ws-bet-y2q4-t4-01`；已启动 Run `20260926T113309Z-project-doc-change-820fd680`。必须先处理 `project-doc-change` 与跨 `docs/governance_state` 合同冲突，以及原 Spec 的 `python3` 运行时命令；不要改写 accepted Spec 而不更新其 Ledger digest，不要创建第二张同义决策卡，不要因 BRIEF 可见就宣称真实价值。恢复前重新核对并发、Ledger、锁与当前 Dashboard 来源。


## child-run update 2026-09-26T12:27Z

The continuation run `20260926T120602Z-bet-execution-b39d93bd` fixed the workflow-lane mismatch by using `bet-execution` and claimed the same three deliverables; no second decision card or BET was created. Its verification still exits 1: `current-state-coherence` and `ssot-guardian` detect the derived task projection at planned=0/total=303 while the task directories contain planned=1/total=304 (active=1, done=302). Official OMO module dry-run reports planned 0→1 and total 303→304. Applying it would also rewrite `.omo/state/system.yaml` and `.omo/tasks/registry/INDEX.md`, neither of which is in this accepted WorkPacket's write surfaces; no projection write was made.

`bet-ledger.py lint` was rerun independently and exits 1 with 7 existing errors: two historical BETs each have missing engineering-test and operational-replay references plus mismatched derived completion state, and the active Dashboard BET has a declared/current accepted-Spec digest mismatch (`043305…` vs `9ce5cd…`). It also reports one non-blocking phantom report-path warning. The new decision card itself is visible in the generated BRIEF inbox and passes its focused schema check; this does not clear the repository-wide gate failures.

This BET remains **blocked, not done**. A future continuation must first reconcile the accepted BET/Spec scope for derived task projections or use a separately claimed, authorized state-sync workflow; preserve the staged three-file deliverables, do not mark the ledger BET complete, and do not reinterpret the root Dashboard's empty active-run projection as evidence that this isolated-worktree run was absent.

---

# 接管交付补记（2026-09-27，run 20260927T013145Z-project-doc-change-20114808）

原会话（run 20260926T113309Z）完成分析后中断于交付前：候选清单 + 决策卡已暂存于
其 worktree（mtime 09-26 19:37–20:38），13 小时无进程、零提交、零 PR（三信号核查 +
mtime 取证后判定为陈旧占用）。本会话按「谁先交付谁赢」以独立 run 正规交付：

- **内容署名采用**：`docs/plans/2026-09-26-business-first-delivery-shortlist.md`
  与 `.omo/tasks/planned/BET-Y2Q4-T4-01-DECISION.yaml` 一字未改采用（owner:
  portfolio-steward 署名保留）；上方 blocked 复盘全文保留（lesson 12：旧内容不覆盖）。
- **本会话补齐的验收**：门禁（gac-local-gate）+ 决策卡渲染验证
  （generate-brief 决策收件箱）+ workorder schema 校验 + evidence 矩阵 + complete。
- 复用本 retro 双段记录两轮 run 的完整链条。

## Q1-Q5（接管轮）

- 耗时：约 15 分钟（内容审阅 + 通道合规 + 验收），appetite 1 天内。
- done_when：候选清单 ✅（3+1 候选带 done_when 草案）、决策卡 ✅（needs-human: true
  且落 .omo/tasks/planned/）、收件箱渲染 ✅（见验证）、盘点原则 ✅（"排序是建议，
  不是 Principal 决定"——选择权显式留给人）。
- 失败/教训：中断会话的暂存产物在共享机器上裸奔 13 小时（wip-guard 只护主工作区，
  agent worktree 无快照兜底）——丢弃即丢一整轮分析。教训：agent 会话中断前
  "staged ≠ safe"，重要中间产物应尽早 commit 到自己分支。
