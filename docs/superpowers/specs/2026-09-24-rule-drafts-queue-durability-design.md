---
schema_version: specification/v1
spec_version: 1.0.0
title: 事故→规则管道人审队列耐久性与治理演进 start 门对称豁免
bet_id: BET-Y2Q3-T10-202
status: accepted
lifecycle: contract
owner: governance-team
created: '2026-09-24'
last-reviewed: '2026-09-24'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
type: ssot
---

# 事故→规则管道人审队列耐久性与治理演进 start 门对称豁免

## 1. 问题

`.omo/standards/incident-to-rule-pipeline.md` 定义的五段管道是
①事故 → ②`error-knowledge.py record` → ③`times_encountered ≥ 5` → ④`_promote_rule_draft` 写
`.omo/_delivery/rule-drafts/CR-PITFALL-*.json` → ⑤人审 + 入册 `governance-checks.yaml`。

本 spec 由两组实测驱动，全部在 `origin/main@4cb9a70fe` 上重跑得到：

| # | 实测 | 后果 |
|---|---|---|
| E1 | `find ~ -type d -name rule-drafts` → 0 命中；`.omo/_delivery/` 下只有 calibration / collab-scenarios / evalsets / events / scene-outcomes / schedule-harness / x3-batch2 | ④ 的产物落在 `.gitignore:12` 的 `.omo/_delivery/*` 里，队列既不可见也不持久 —— ⑤ 从来没有东西可审 |
| E2 | 37 个 pitfall 条目里恰好 3 条越过阈值：PITFALL-GAT-004 (46 次)、PITFALL-GAT-005 (18 次)、PITFALL-COO-003 (5 次) | 三条逾期草案从未生成；最高一条被观测 46 次仍停留在「记录」段 |
| E3 | `feed_from_escapes` 的症状匹配 `symptom_overlap >= 3` 无 category 过滤，且命中即 `break` | 与已修的 `cmd_record` 同源缺陷仍在计数入口：`pointer-drift`/`submodule` 逃逸可给 `gate` 类坑加分，而该计数直接驱动 ③→④ 晋升 |
| E4 | `.omo/_truth/governance-evidence/` 下 136 个 waiver 文件，其中 70 个记录 `AGCP_REQUIREMENT_ITERATION_GATE=0`；`git log` 区间内仍在增加（09-22: 5、09-23: 3、09-24: 1） | `start_requires_bet` 只豁免 `observer-audit`，而 `evaluate_closeout` 对 `GOVERNANCE_EVOLVE_WORKFLOWS` + `_has_governance_bet` 明确放行（G8）。治理自进化在出口无债、在入口被拦，唯一合规出路退化成一次性豁免 —— 70 条 waiver 是这个不对称的价格 |
| E5 | 台账 458 条 bet（`4cb9a70fe`）全部 `status: done`，open = 0；rebase 时在同一文件上复核（`3dcf73a1c`）得 459 条、1 条 `in_progress`（`BET-Y2Q3-T9-01`，并发交付自持） | 入口没有任何**属于本次交付**的可绑定 bet：借他人 in-flight bet 绑定正是 F1 要消灭的纸面绑定，且构成抢坑。E4 的不对称因此每次都要重新撞 |

E1/E2 是「管道后半段看不见」，E4/E5 是「管道前半段进不去」。二者同源：治理证据的存放位置与门的对称性没有对齐它们声称的闭环。

## 2. 目标

- **G1** 人审队列持久：`.omo/_delivery/rule-drafts/` 入仓，与 `calibration/events/scene-outcomes` 同构。实测「入仓」要同时解两道锁（`.gitignore:12` 的 `.omo/_delivery/*`，以及 `check-runtime-artifacts.py` 对 `.omo/_delivery/` 的提交黑名单）——只做前者会在 `git commit` 时被确定性地拦下（见 §4）。
- **G2** 补齐逾期草案：用 `_promote_rule_draft` 本身（不手写）为 E2 的三条生成 `CR-PITFALL-*.json` 并入库，使 ⑤ 首次具备可审对象。
- **G3** 计数入口同类限定：`feed_from_escapes` 的 fuzzy 匹配加 category 过滤，杜绝跨类加分；保持 `break` 语义不变（同类内首个命中）。
- **G4** 队列可观测：`stats` / `check` 报告「阈值已过但无草案」的条目，**不改变 `check` 的退出码**。`check` 已作为 `error-knowledge-check` 接在 `gac-local-gate.py` 上，收紧它会把所有并发 agent 的门一起变红（I1 教训）。
- **G5** start 门对称豁免：`start_requires_bet` 对 `GOVERNANCE_EVOLVE_WORKFLOWS` 在 `_has_governance_bet` 为真时放行，与 `evaluate_closeout` 同一条件、同一常量，不新增豁免名单、不动 `observer-audit` 语义。
- **G6** 回归测试覆盖 G3/G5，且断言「不放宽」的那一半（非治理演进 workflow 仍必须带 bet）。

## 3. 非目标

- 不修改 `ESCALATION_THRESHOLD`、不改 `>= 3` 词阈值判据本身（该判据是否合理属 principal 裁决）。
- 不把草案自动合入 `governance-checks.yaml` —— ⑤ 人审是 HITL 边界，本次只让队列可见。
- 不放宽 `error-knowledge check` 的退出码，不接线任何新增强门。
- 不触碰 PITFALL-GAT-004 的证据质量问题（其 symptom 是一段 PASS 日志摘录、标题停留在 "(8x)"、`last_confirmed_at: 2026-08-30`）：只报告，不处置。
- 不改 run 记录的 gitignore 语义（`.omo/_delivery/agent-workflows/runs/` 是否入仓另案）。
- 不动台账里任何既有条目，只按 `ledger-safe-insert.py` 新增本 bet。

## 4. 设计

**G1**：`.gitignore` 在既有 `!` 组后追加 `!.omo/_delivery/rule-drafts/`。落盘后用 `git check-ignore -v` 与 `git status --porcelain` 双向核验（忽略规则是前缀匹配，负向规则必须放在 `.omo/_delivery/*` 之后）。

**G1 的第二道锁（实施时实测，非推测）**：`.gitignore` 改完后 `git add` 能看到草案，但 `git commit` 被 pre-commit 的 `runtime-artifacts` 检查确定性地拦下——`bin/gac/check-runtime-artifacts.py:31-34` 的 `BLACKLIST_PREFIXES` 含 `.omo/_delivery/`，而同文件 `WHITELIST_PREFIXES:37-41` 正是为 `calibration/events/scene-outcomes` 三个同构目录开的既有例外机制（注释即写明 "tracked .gitkeep placeholders (not runtime output)"）。同一黑名单在 `bin/gac/ci-local-fast.py::run_runtime_artifact_gate()` 有第二份同源实现（前者 docstring 自述移植关系），且**两份已经漂移**：`WHITELIST_PREFIXES` 只存在于 hook 那份。实测后果有限定：ci-local-fast 那份扫 `git diff --cached`，CI 无暂存区故当前不显形，但本地跑它的任何人连那三个目录都提交不了。因此本次不只加一条白名单，而是把 4 条前缀同步进第二份实现，使两处收敛为一个语义。


**G2**：给 `error-knowledge.py` 增加一次性的「按阈值补生成草案」路径，复用 `_promote_rule_draft(entry)` 本体而不复制判定逻辑；产出 `status: awaiting_human_review` 的 JSON 草案。草案内容必须由工具测得（计数、类别、症状、review_before 继承 0431 的 90 天），不得手写占位。

**G3**：`feed_from_escapes` 在 `symptom_overlap(...) >= 3` 的同一谓词上并列 `entry_category == _SURFACE_CATEGORY.get(surface, ...)`；无类别映射的 surface 保持现状不新增推断。

**G4**：`cmd_stats` 增 `overdue_rule_drafts` 计数与明细；`cmd_check` 增同名只读段落，输出后不改 `return`。

**G5**：`start_requires_bet(workflow_id, bet_id, *, env=None, workspace=None)` —— 保持位置参数与既有返回契约不变，新增对 `GOVERNANCE_EVOLVE_WORKFLOWS` 的分支：无 bet 且 `wf in GOVERNANCE_EVOLVE_WORKFLOWS` 且 `_has_governance_bet(workspace or DEFAULT_WORKSPACE)` → `BindVerdict(True, ["governance_evolve_exempt"])`，即豁免谓词与 closeout 完全同一条，不更宽。`DEFAULT_WORKSPACE = Path(__file__).resolve().parents[2]` 让 chain_bind 自锚到所在工作树；实证（2026-09-24）两个调用点（`bin/agent-workflow.py`、`projects/omo/src/omo/workflow/cli.py`）都从 `<root>/bin/plan/chain_bind.py` 加载模块，已天然拿到正确根，故**不改动任何调用点**（`projects/omo` 是子模块，本就不在本次交付面内）。`bin/plan/chain-bind-check.py self-check` 与 `tests/test_chain_bind.py` 原样钉住旧的更严契约，必须同步改为双向钉（有治理 bet 放行 / 无治理台账仍拦），否则契约反转只落在一处。`bin/agent-workflow.py` 的拦截提示行仅枚举 `observer-audit` 与 ENV 豁免，G5 后不完整，一并更正。

## 5. 验收

1. `git check-ignore -v .omo/_delivery/rule-drafts/<任一>.json` 无输出，且 `git ls-files` 含 3 份草案；草案的 `git add` **和** `git commit` 都放行（后者由 pre-commit 的 `runtime-artifacts` 检查实测，不是只看 `.gitignore`），两份同源实现的白名单前缀集合相等（回归测试断言）。
2. `python3 bin/gac/error-knowledge.py stats --json` 报告 3 条 overdue → 修复后为 0，且明细含三条 PITFALL id。
3. `python3 bin/gac/error-knowledge.py check` 在草案齐备前后 exit code 恒为原值（用 `echo $?` 前后对拍）。
4. 新回归测试：跨类 escape 不给 `gate` 坑计数；`governance-audit` 无 bet start 在治理台账存在时放行、`project-code-change` 无 bet 仍 `missing_bet_id`；`python3 bin/plan/chain-bind-check.py self-check` exit 0，且 `tests/test_chain_bind.py` + `tests/unit/gac/test_chain_bind_start_gate.py` 全绿（start/closeout 对称性用同一批 workflow id 对拍）。
5. `make gac-local-gate` 与本仓 `tests/unit/gac/test_error_knowledge_recall.py` 通过；每个 commit 单 lane。
6. 改动面在 start 前一次算全并写入 `write_surfaces`：本轮实证 `refresh-packet` 对「自己改台账的 bet」结构上不可用（它拿工作区字节比 `origin/main`），事后补面只能重开 run。

## 6. 回滚

改动全部落在可独立 revert 的面：`.gitignore`、`bin/gac/error-knowledge.py`、`bin/gac/check-runtime-artifacts.py` + `bin/gac/ci-local-fast.py`（G1 第二道锁的两份实现）、`bin/plan/chain_bind.py` + `bin/plan/chain-bind-check.py` + `tests/test_chain_bind.py`（G5 契约三件套）、`bin/agent-workflow.py`（提示行）、`tests/unit/gac/*`、`.omo/**` + `docs/**`。回滚 = revert 对应 commit；草案 JSON 是人审输入而非运行态，删除草案不影响任何 gate。
