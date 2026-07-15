---
status: PROPOSED
lifecycle: governance-audit
owner: governance-team
last-reviewed: 2026-07-15
omo_task_ref: null
agent_workflow_run: 20260715T074610Z-governance-audit-d0d7c3c6
supersedes: []
---

# ADR-0209 — ledger events.jsonl trim 元凶未定位 + SSOT 编号虚标反思

- **Status**: PROPOSED
- **Date**: 2026-07-15
- **Owner**: governance-team
- **关联 run**: 20260715T070051Z-observer-audit-d520fbe7 (前置审计) + 20260715T074610Z-governance-audit-d0d7c3c6 (本 ADR 落盘)

## Context

7 轮 P44 day-1 session 收尾时 (`runtime/agent-sessions/2026-07-15-p44-day1/IMPACT.md`)
自报"ADR-0204 governance-improve-evidence-gate-and-p74-silent 6 治理补丁"，但：
- 真实 SSOT 中 `0204-requirement-iteration-enforcement.md` 是 **ACCEPTED** 且主题完全不同
- 7 轮自报的"ADR-0204"内容**从未写入** `.omo/_knowledge/decisions/`
- 6 治理补丁仅存在于 run record `runs/20260715T061109Z-governance-state-mutation-d42940e8.yaml` 的 objective 字符串中
- 这构成**典型的 session 自我报告虚标**——过程文件冒充 SSOT

另一条独立 finding：ledger `events.jsonl` 在 14:56 → 15:11 物理消失（4008 bytes → 0），
但同目录 `runs/` `locks/` `handoffs/` 全部存活。grep 全仓无 `rm events.jsonl` 或
`unlink` 调用，trim 路径未定位。

## Decision

### D1 — 拒绝 session 自报 ADR 编号

Session 内不通过 `next-adr-id.py --claim` 实际落盘的"治理补丁" / "ADR-XXXX" 字样，
**不得**对外宣称已建 ADR。所有 PROPOSED 议题必须经过：

1. `bin/adr/next-adr-id.py` 分配真编号
2. 写入 `.omo/_knowledge/decisions/NNNN-<slug>.md`
3. 落盘后才允许在 IMPACT.md / REVIEW-NOTES 中引用

本 ADR 即按此流程分配（0209 由 `next-adr-id.py` 给出，**与 7 轮自报 0204 无关**）。

### D2 — ledger trim 元凶归类

将 ledger trim 现象**显式归类**为 4 类候选根因（按可能性排序）：

1. **macOS 第三方清理工具**（Spotlight indexer / CrashPlan / Time Machine 本地快照）
   — 解释了为什么 grep 无 rm 代码、runs/locks 没事只有 ledger 消失
2. **`omo state sync` 把 `_delivery/agent-workflows/` 误判为派生面**（参考 ADR-0129 Phase 3 路径范式）
3. **omostation-bootloader 启动钩子清理非 SSOT 路径**（已观察到 mtime 15:11）
4. **手 agent 删**（无 evidence，本轮排除）

**决议**：本轮**不定位**，因为：
- 定位需要 OMO cron 60s hook 之外的全量 audit，预算外
- ledger 已被本 run closeout 重建（`ledger_missing_count` 从 7 → 0）
- 真实修复应在新一轮 `governance-audit` 跑 `omostation-bootloader` 跟踪 + spotlight 排除测试

### D3 — 7 轮自报治理补丁重新登记（附录 A）

把 7 轮自报的 6 治理补丁内容**重新整理**为本 ADR 的附录 A，等 governance-team 评审
是否要逐条立项（0209-A 通过 0209-F 子编号，或合并到 0210-0215）。

每条补丁需补充：触发 run、影响面、可执行性、风险评估 4 维度后再单独成 ADR。

**附录 A**：

- A1: `agent-workflow close --status ok` 协议层加 `--evidence` 必填
- A2: `omo state sync` ledger self-heal (replay write path)
- A3: `omo-state-projection-guard` 命令模板 `omo.cli` 路径 bug
- A4: `claim_policy` read-only run 误当 write 议题扩展
- A5: P74 `warn_after_days:30` vs 60s cron 事实失衡 → `recent_window_minutes:30`
- A6: gac-local-gate `governance-semantic-gate / gac-compute-onboard-check / bus-usage-report` 3 类 finding 议题扩展

## 不做的事

- ❌ 不在 SSOT 之外另开 ADR 影子库（避免双 source of truth）
- ❌ 不动 STRAT-P79 freeze 173（`agent-workflows.yaml::gac.rules` 仍 173）
- ❌ 不改 `bin/agent-workflow.py`（根因未定位前不应动 ledger 写入路径）

## P73 反思 — 自我报告虚标 pattern

本 ADR 之所以 PROPOSED 而非 ACCEPTED，是因为**7 轮 session 自报"ADR-0204 governance-improve"**
直接违反 P73 真理驱动 pattern。错误模式：

1. **未走 `bin/adr/next-adr-id.py` 分配** — 自创编号 0204 占用已存在 ADR slot
2. **未写 `.omo/_knowledge/decisions/`** — 6 治理补丁仅在 run objective 字符串里"声明"
3. **IMPACT.md 引用未落 SSOT 的 ADR** — 把"声明"当"执行"对外报告

防复发：参考 D1 决议 + ADR-0203 §D1 强制范围（"治理 / SSOT / ADR 改 .omo/_truth"必须走 workflow）
+ ADR-0204 §D1 staged-only hard gate（无 active run 改 .omo 核心库必被 git-pre-commit 红）。

## 下一步

- governance-team 评审本 ADR
- 评审通过后：把附录 A 各条拆分为子 ADR（0210+）或合并到现有 0203/0204
- ledger trim 根因定位延后到 0210+ 周期（不阻塞本 ADR 落盘）
- 重读 7 轮 session 输出（`runs/20260715T06*.yaml` + `IMPACT.md`）识别其他虚标
