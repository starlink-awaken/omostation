---
type: ephemeral
status: completed
lifecycle: history
date: 2026-09-22
scope: 2026-08-22 → 2026-09-22 月度复盘
author: governance-agent
session: monthly-retro-0922
last-reviewed: 2026-09-22
---

# 月度复盘：2026-08-22 → 2026-09-22

> **执行摘要**：窗口内 GitHub 合并 **1959** 个 PR（100% 单账号 agent 交付）；BET 台账窗口关闭 **321** 条（done_at ≥ 08-22）；门禁快照 **11/11 PASS**（截至 2026-09-22T08:43Z）；主线债务为 Claims Authority 待授权、价值证明缺口、`meta.total_bets` 漂移与 T10-154 blocked。

---

## §0 范围与口径

| 项 | 值 |
|----|-----|
| 时间窗 | 2026-08-22 → 2026-09-22（UTC，按 `mergedAt` / `done_at`） |
| 主口径 | GitHub `starlink-awaken/omostation` 已合并 PR **1959**（三段 gh 查询，快照 2026-09-22） |
| 辅口径 | 本地 worktree `origin/main` 上 `--since=2026-09-18` 可见 **216** 条 commit（**shallow 仓，09-18 前本地不可见**；与全月 PR 口径不可直接相加） |
| 状态快照 | `runtime/dashboard/agent-brief.json` generated_at **2026-09-22T08:38:05Z**；本节复核时刻 **2026-09-22T08:43:52Z** |
| 作者边界 | 窗口内 PR 作者 100% 为 `starlink-awaken`（agent 批量 squash 工作流），**不作人力/工时结论** |

**证据命令（原样）**：

```bash
# PR 三段计数（各段 limit=1000）
gh pr list --state merged --search 'merged:>=2026-08-22 merged:<2026-09-04' --limit 1000 --json number,title,mergedAt
gh pr list --state merged --search 'merged:>=2026-09-04 merged:<2026-09-14' --limit 1000 --json number,title,mergedAt
gh pr list --state merged --search 'merged:>=2026-09-14 merged:<=2026-09-22' --limit 1000 --json number,title,mergedAt
# 求和 920 + 641 + 398 = 1959

git log --since='2026-09-18' --pretty='%ad|%s' --date=short origin/main
git log --since='2026-09-18' --shortstat --pretty=format: origin/main

python3 -c "import json; json.load(open('runtime/dashboard/agent-brief.json'))"
# BET: yaml.safe_load docs/plans/3y-bet-ledger.yaml → entries / meta.total_bets / done_at
```

**数值纪律**：下文计数均为「截至上述快照」；易变项以指针为准，不作永久断言。

---

## §1 交付链

### 1.1 PR 大盘（主口径，1959）

**类型分布（严格标题前缀）**：

| 类型 | 数量 | 占比 |
|------|-----:|-----:|
| feat | 601 | 30.7% |
| fix | 418 | 21.3% |
| chore | 401 | 20.5% |
| docs | 308 | 15.7% |
| other/无前缀 | 174 | 8.9% |
| test | 20 | 1.0% |
| ci | 14 | 0.7% |
| governance | 9 | 0.5% |
| refactor / perf / ops / hardening 等 | 14 | 0.7% |

- 治理 scope（标题含 `(governance)` 等）约 **207**（≈10%）
- feat+fix 合计 ≈52%：**功能交付与修复迭代并重**，非纯重构月

**高峰日 Top5**：

| 日期 | 合并 PR 数 |
|------|----------:|
| 2026-08-28 | 127 |
| 2026-08-30 | 126 |
| 2026-08-29 | 106 |
| 2026-09-11 | 96 |
| 2026-09-05 | 96 |

**月段**：08-22→08-31 = **827**；09-01→09-22 = **1132**；合计 **1959**。

### 1.2 重要 PR 指针表

| PR# | 日期 | 标题（摘） | 主题 |
|-----|------|-----------|------|
| #3703 | 09-12 | feat(gate-evidence): A1-A9+RF0 9 gate digest-bound receipt | 门禁证据链（T10-164） |
| #3787 / #3815 | 09-15/16 | A8 外部事务生命周期 spec + ledger complete | A8 收口 |
| #3893 | 09-17 | feat(gac): Ruflo RF0 read-only admission verifier | RF0 验证器 |
| #3904 | 09-17 | feat(panorama): project scheduled launchd runtime health | Panorama 运行健康 |
| #4081 | 09-20 | docs(governance): ADR-0402 声明/执行鸿沟多尺度信号 | ADR 新增 |
| #4093 | 09-20 | fix(governance): A4 Scheduler — 补登 debt-review + clash-probe 孤儿 | A4 门禁 |
| #4115 | 09-21 | feat(gac): 过期雷达 — SLA 越界提前可见 | 治理可观测 |
| #4127 | 09-21 | fix(gac): semantic-gate 移出 SOFT_CHECKS | 门禁真阻断 |
| #4138 | 09-21 | feat(gac): test-collection 守卫 | 孤儿测试腐化检测 |
| #4152 | 09-21 | feat(bet): T5-01/02/03 team-mailbox 链插入 | T5 编排链 |
| #4175 | 09-22 | fix(security): remove write-capable checkout tokens | 安全 |
| #4194 | 09-22 | feat(ledger): T10-154 A9 strategy retro repair + PASS evidence | A9 证据 |
| #4199 / #4200 | 09-22 | A4：登记 mimo-models-sync（job / known_orphans 双路径） | A4 修复（本会话） |
| #4202 | 09-22 | chore(retros): auto-fix-loop frontmatter + resident promote | retro 卫生（本会话） |

> 本会话三 PR 已核对在列；#4189→#4201 的 `meta.total_bets` 回归链见 §2.4 / §3.2。

### 1.3 本地 git 细分（辅口径，09-18 → 09-22，shallow）

> **边界**：仅 `origin/main` 在本 worktree 可见窗口；**不可**解读为「全月只有 216 提交」。

| 日期 | commits |
|------|--------:|
| 09-18 | 26 |
| 09-19 | 60 |
| 09-20 | 40 |
| 09-21 | 57 |
| 09-22 | 33 |
| **合计** | **216**（其中 211 条带 shortstat） |

| 类型 | 数量 |
|------|-----:|
| fix | 95 |
| docs | 40 |
| feat | 39 |
| chore | 36 |
| 其他（test/governance/ops/refactor/ci） | 6 |

**变更规模（有 shortstat 的 211 条）**：约 **1658** files changed，**+140,792 / −10,635** — 净增以知识/证据/台账为主，删除量小。

**路径 Top（二级目录聚合）**：

| 次数 | 路径 |
|-----:|------|
| 901 | `.omo/_knowledge` |
| 109 | `.omo/_truth` |
| 70 | `docs/scene-cards` |
| 46 | `docs/plans` |
| 45 | `bin/ssot` |
| 42 | `bin/gac` |
| 41 | `.omo/tasks` |
| 39 | `bin/panorama` |

**解读**：状态/知识面（`.omo/`）与治理工具（`bin/gac`、`bin/ssot`）主导，符合治理 SSOT 仓定位；`fix` 高占比对应门禁/证据链持续打补丁。

### 1.4 演进主题（10 条）

1. **Panorama / dashboard 统一**：agent-brief、launchd 运行健康、写操作诚信（T8-02/03/04）；主题词 panorama 高频（#3904 等）。
2. **A1–A9 执行环境恢复收尾**：A8 closeout、A9 strategy retro 修复（#4194）、A1–A9+RF0 receipt（#3703）。
3. **Claims Authority 影子运行**：`shadow-active` 但 activation **BLOCKED**，待 operation-specific 人工授权；preflight 高水位对齐 spec 绑定（#4204/#4206）。
4. **team-mailbox（Y2Q2-T5-ORCH）**：#4152 插入链 → T5-01/02/01 持久化投递 → done + fork-join retro（期间状态曾两连回退 #4187/#4191 再关闭）。
5. **价值证明**：value-proof 长期 `NOT_PROVEN`，需再收 **30** 条合格真实样本（冻结基线、禁止回填）。
6. **治理门禁与教训**：PITFALL-GAT-001～009 成体系落地（见 §3.1）；semantic-gate 真阻断、test-collection 守卫、过期雷达。
7. **知识模式沉淀**：patterns 目录可见 p75–p99 系列及 `pipe-mask-failure` / `pre-push-ssot-path-drift` 等持续追加。
8. **季度评估**：Q3/Q4 quarterly-evaluation 契约文档仍在 `docs/reports/` 维护（lifecycle: contract）。
9. **场景卡升档**：`docs/scene-cards` 高活跃（辅口径 70 次路径命中）；升档/校准按 lifecycle 标准推进。
10. **安全与 CI 卫生**：#4175 移除 write-capable checkout tokens；cron 兼容、测试债、子模块 init 假红（GAT-001/008）持续修复。

---

## §2 目标达成分析

### 2.1 BET 关闭总览（截至 2026-09-22 快照）

| 指标 | 值 | 来源 |
|------|----|------|
| 台账 entries | **442** | `docs/plans/3y-bet-ledger.yaml` |
| status=done | **441** | 同上 |
| status=blocked | **1**（`BET-Y2Q2-T10-154`） | 同上 |
| candidate（brief） | **1** | agent-brief bets.counts |
| `meta.total_bets` | **439**（与 entries 漂移 **−3**） | ledger meta |
| 窗口 done（done_at ≥ 2026-08-22） | **321** | done_at 过滤 |
| Y2Q2 完成率 | **87.5%**（14/16，remaining 2） | brief milestones |
| 其余历史窗口 | 100%（brief 内 Y1Q1–Y1Q4、Y2Q1、Y2Q3–Y2Q4、Y3H1/H2） | brief |

### 2.2 主题链表

| 主题链 | 代表 BET | 状态（快照） |
|--------|----------|--------------|
| T5 team-mailbox 编排 | BET-Y2Q2-T5-01/02/03 | done（含状态回退再关闭） |
| A9 / T10-154/155 | BET-Y2Q2-T10-154、T10-155 | **T10-154 blocked**；T10-155 done |
| T10-170～174 执行环境链 | T10-170…174 | done（09-20～21 密集 closeout） |
| T4 价值循环 | BET-Y2Q1-T4-01/02/03 | done |
| T8 dashboard 诚信 | BET-Y2Q2-T8-02/03/04 | done |

### 2.3 ADR 轨

| 动作 | 证据 |
|------|------|
| ADR-0402 新增（声明/执行鸿沟多尺度信号，关闭 DECL_EXEC_GAP） | #4081 |
| ADR-0402 重复编号让号 → **ADR-0453** | e7e912d / #4092 链 |
| 0453-gate-shift 引入后认定重复并回退 | #4110 → #4113 修复 |
| 债务复审收尾带 ADR/INDEX 更新 | #4087 |

> 探索期曾记「#3904 批量导入 415 ADR」：本快照 `git log` 显示 #3904 标题为 `feat(panorama): project scheduled launchd runtime health`；**ADR 批量导入以库内 decisions 目录实际历史为准**，不在此断言错误 PR 号。

### 2.4 治理门禁与权威状态（动态节）

| 项 | 快照值 | 备注 |
|----|--------|------|
| Gates | **11 / 11 PASS**，failing `[]` | agent-brief @ 2026-09-22T08:38Z；本会话曾修 A4/RF0（#4199/#4200 + 机器态 turn-credit） |
| Claims Authority | activation_allowed=**false**，readiness=**BLOCKED** | 只读等待 operation-specific 授权 |
| next_actions | claims-authority-wait；triage-high-alerts；collect-qualifying-value-evidence；plan-candidate-bets | 见 brief |
| value_proof | **NOT_PROVEN**（qualifying 样本不足 30） | 见 brief value_proof_readiness |
| meta.total_bets 回归 | #4189：439→**443**；#4201：改回 **439**；当前 entries=**442** | 并行覆盖型回归 |

---

## §3 风险与教训

### 3.1 PITFALL-GAT-001～009（门禁类）

| ID | 标题（摘） | sev |
|----|-----------|-----|
| GAT-001 | fresh worktree 子模块未 init → gate 环境性假红 | medium |
| GAT-002 | 多文档 yaml `safe_load` → 规则数假零 | medium |
| GAT-003 | test fixture 泄漏 drafts 进真实 decision inbox | medium |
| GAT-004/005 | GaC 反复豁免（自动采集） | medium |
| GAT-006 | **交付已被 main 等价合并/自愈 — 过期 base 重复造轮子**（含 total_bets 回退例） | **high** |
| GAT-007 | CI 假失败分诊：同命令本地绿 CI 红 | medium |
| GAT-008 | completion_evidence 引用须主仓 tracked（CI 无子模块检出） | medium |
| GAT-009 | unbound 治理修复应走 governance-state-mutation（G8） | medium |

路径：`.omo/_knowledge/pitfalls/gate/`。

### 3.2 并发与回归

- **`meta.total_bets` 振荡**：#4189 修 443 后 #4201 写回 439，entries 442 — meta 与 entries 未同事务校验；对应 GAT-006 形态。
- **ADR 让号回归链**：0402 重复 → 0453 → gate-shift 重复品回退（#4110/#4113）。
- **T5-03 状态回退**：#4187 revert status、#4191 revert completion_evidence，再完成关闭 — closeout 证据过早写入风险。

### 3.3 快照漂移风险

本会话窗口内 gates 曾出现 A4/RF0 红 → 修复后 11/11 → 探索中一度记录 A7 挂红 → 复核又为 11/11。**任何复盘/gate 叙述必须携带时间戳**；以 `agent-brief.json` `generated_at` 为准。

### 3.4 辅口径误读风险

shallow 仓 09-18 前 commit 不可见；216 ≠ 全月提交量。全月交付以 **PR 1959** 为主口径。

### 3.5 本会话实操教训（补充）

- **直推 main 被保护分支拒绝** → 必须 worktree + PR；`gh pr merge` 遇 GraphQL EOF 需重试且先确认远端分支仍指向目标 commit。
- **并行 agent 同题双修**：A4 同时出现 #4199（登记 job）与 #4200（known_orphans）— 功能上双保险，但反映「动手前未查 main/远端是否已修」（GAT-006 教训仍需习惯化）。

---

## §4 后续债务（P0 / P1 / P2）

> 本复盘**只记录与建议**，不在此执行修复。

### P0（权威/安全阻塞）

| # | 债务 | 证据指针 | 建议动作 | 不做的原因 |
|---|------|----------|----------|------------|
| 1 | Claims Authority 激活仍 BLOCKED | agent-brief `claims_activation_blockers` | 按 authorization_packet 补 operation-specific 人工授权；保持只读 | 需真人授权，非 agent 可单方解锁 |
| 2 | 高危告警 triage | brief `triage-high-alerts` | 分类真债 vs 陈旧 fixture | 本任务边界=只写文档 |
| 3 | （条件）若写文档时 A4/A7 等 gate 再红 | 快照 failing 列表 | 按 GAT 分诊：环境假红 vs 真回归 | 快照时为 11/11；监控即可 |

### P1（真理值漂移 / 价值证明）

| # | 债务 | 证据指针 | 建议动作 | 不做的原因 |
|---|------|----------|----------|------------|
| 4 | `meta.total_bets` 439 vs entries 442 | ledger + #4189/#4201 | meta 由 entries 派生并加 gate；禁止手改单字段 | 需 ledger 写路径变更+测试 |
| 5 | 价值证明 NOT_PROVEN（差 30 合格样本） | brief value_proof_readiness | 冻结基线采集真实使用记录，禁止回填 | 需长期观测 |
| 6 | BET-Y2Q2-T10-154 blocked | ledger status=blocked | 解除阻塞或改状态并补证据 | 需任务 owner 决策 |
| 7 | Y2Q2 窗口 87.5% remaining 2 | brief milestones | 清 candidate/blocked 收口 Y2Q2 | 同上 |

### P2（卫生 / 文档）

| # | 债务 | 证据指针 | 建议动作 | 不做的原因 |
|---|------|----------|----------|------------|
| 8 | 本 ephemeral 文档完成后归档 | AGENTS.md §2 T6-17 | `completed` 后移入 `.omo/_knowledge/design/plans/archive/reports-2026-09/` 并指针化 | 需用户点头 |
| 9 | worktree 子模块浅 init/代理失败残留 | 本会话 claim 日志（proxy 7890） | 修复代理或 claim 慢路径；GAT-001 指引 | 环境问题另开 |
| 10 | 场景卡/校准样本与升档节奏 | scene-cards 活跃、lifecycle 标准 | 按 3-sample/30-sample 门槛推进 | 非本任务 |

---

## §5 附录

### A. 证据命令

见 §0 代码块；另：

```bash
python3 bin/scheduler-compile.py --check          # A4 等价（本会话修后 ok=true）
python3 bin/gac/ruflo-rf0-verify.py --json        # RF0（本会话修后 ok=true）
make doc-ssot-lint
make gac-local-gate
```

### B. 指针表

| 指针 | 含义 |
|------|------|
| `runtime/dashboard/agent-brief.json` | 门禁/BET/告警/next_actions 权威快照 |
| `docs/plans/3y-bet-ledger.yaml` | BET 台账 SSOT |
| `docs/reports/2026-09-09-session-retrospective-0903-0909.md` | 周复盘结构样例 |
| `.omo/_knowledge/design/plans/archive/2026-09-14-governance-deep-retro-0903-0914.md` | 深复盘样例 |
| `docs/reports/2026-Q3-quarterly-evaluation.md` | 季评 P0–P2 惯例 |
| `.omo/_knowledge/pitfalls/gate/` | GAT-001～009 |
| 本文快照 | PR 查询 2026-09-22；brief 2026-09-22T08:38Z |

### C. 未覆盖边界

- 未拉全月逐日 **CI 红单**全量、未做全月 **LOC**（仅 shallow 辅口径窗口）。
- 1959 计数范围 = 主仓 `gh pr list`（**不含**未并入本仓的子模块仓独立 PR，除非其 squash 进主仓）。
- 单作者口径限制；不评价个体贡献差异。
- 演进主题 10 条为主题词+代表 PR 综合，非穷举全部 1959 标题。

---

*文档类型 ephemeral；已按 T6-17（2026-09-05）归档至 `.omo/_knowledge/design/plans/archive/reports-2026-09/`。*
