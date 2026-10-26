---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-26
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: 口径归一 — 日历 / 台账 / 目标覆盖三读数分离并在 Agent Brief 显式并列
bet_id: BET-Y2Q4-T1-05
created: 2026-10-26
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
related: ADR-0456
---

# 口径归一 — 日历 / 台账 / 目标覆盖三读数分离并在 Agent Brief 显式并列

## 背景：同一天，三个读数，三套互相矛盾的答案

读数来源：`cd ~/Workspace && python3 bin/plan/bet-ledger.py list --json`（2026-10-26 实测，measured_from = mini / omostation@origin/main c885c25e2）。

| 读数 | 今天是什么 | 出处 |
|---|---|---|
| **日历层** | 「今天在 Y1Q1」（Y1Q1 = 2026-08→10） | `docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md` 的窗口表 |
| **台账层** | 活窗口是 **Y2Q4**（Y2Q3 只剩 1 条在跑） | `bet-ledger.py surface` 可认领列表首个窗口 |
| **目标覆盖** | 台账把**日历还没到的窗口**的 bet 也记成 done：Y2Q1+ 共 **189** 条，其中 **179** 条已 done | 台账 `meta.windows`（Y1Q1–Y3H2 共 10 个窗口）对蓝图窗口表 |

**脱节点**：日历表的 6 个窗口（Y1Q1、Y2Q2–Y3H2）在台账 `meta.windows` 里有对应行，但蓝图那张表本身没有 ⇒ **两个口径的窗口集合根本不是同一套**。谁按哪个口径读，都会算出不一样的「还剩多少活」。

**更致命的是读数没有出处**：入口层 Agent Brief 的 `generated_at` 停在 `2026-09-21T12:26:20Z`（停更 35 天），而台账机读出口 `bet-ledger.py list --json` 在今天之前**直接崩**（`TypeError: Object of type date is not JSON serializable`）⇒ **两个读数都不可信，而没有任何一处报错**。

## 本单要做什么

把三个读数**分开命名、分别标注出处与截至时间**，并在 Agent Brief 里**显式并列**（**不合并成一个数**）：

- `calendar_window` —— 日历口径（当前窗口）
- `ledger_window` —— 台账口径（当前活跃窗口）
- `goal_coverage` —— 目标覆盖（按窗口的剩余条数）

每个读数带：值 / 成色（provenance）/ 截至时间 / 分母。**可比性由消费方判定，本单不合并口径**。

## 本波交付（PR-1 立单 + PR-2 接线 + PR-3 读数可判）

1. **台账机读出口可被机器消费**：`bet-ledger.py list --json` 不崩，且日期字段是 **ISO-8601**（`date`/`datetime` ⇒ `isoformat()`，**不用裸 `default=str`** —— 裸 str 出来是空格分隔 `2026-09-06 09:50:00+00:00`，不是 ISO）。
2. **入口层 Agent Brief 由活的 projection revision 原样物化**（新脚本 `bin/panorama/materialize-agent-brief.py`）：**不重新打 `generated_at`**（保留数据的真实时间），附 `provenance`（`source_path` / `revision_id` / `manifest_sha256` / `copied_at` / `data_generated_at`）；源缺失或不可解析 ⇒ **不写、退出码非 0**，绝不写空壳或半截文件。
3. **入口层 TTL 刷新退役**：`auto-pruner.prune_brief()` **不再改这份文件的 `generated_at`** ⇒ 停更就如实报停更。（⚠ 保留 TTL 而不加物化 = 拿 34 天前的快照冒充今天 = 假绿。）
4. **work-agent 探针能正确判定 launchd 作业**：`planning_probe.py` 的 launchd 分支必须读 `ProgramArguments` ⇒ 否则任何 launchd 方案都会被判成 `SCHEDULED_BUT_WRONG_ARTIFACT` + `SCHEDULED_BUT_INTERPRETER_UNKNOWN`，**今天的「绿」是假的**。

## 验收判据（全部机检）

见 bet `BET-Y2Q4-T1-05` 的 `verify` 段（逐条对应 A1 / B1 / B5 …）。核心三条：

- `python3 bin/plan/bet-ledger.py list --json` ⇒ exit 0、合法 JSON、`done_at` 全为 ISO 字符串。
- `runtime/dashboard/agent-brief.json` 的 `generated_at` **逐字等于**源 revision 那份的 `generated_at`（没被打戳）＋ `provenance.revision_id` 非空。
- `python3 scripts/planning_probe.py --mode all` ⇒ 入口层 `verdict = SCHEDULED_OK`，且 `age_days` **等于数据真实年龄（不是 0）**。

## 不做

- **不改日历层那张 markdown 表**（6 个季度错位留下一波；本单只让读数可信，不改日历表）。
- **不派生新 bet**（蓝图 ≤5 条；两处代码/接线是本单的交付内容，不另开）。
- **不碰投影载荷与 driver**（`BET-Y2Q4-T10-237` 是需人工到场的 bet）。
- 不排 `panorama-collect.py`（今天不写 brief ＋ 会 `git checkout -- .omo/`）。
- 不动 §5.39/43/44/60/80 的小节序号残留。

## 风险

- **物化作业与投影发布管线的耦合**：源是 revision，revision 由 `zhixing-refresh.sh` 每 30 min 更新 ⇒ 物化频率取 1800 s 与之对齐。
- **日历层与台账窗口的 6 个季度错位**在本单**不被修** ⇒ 本单让三读数各自可信、并列呈现；**一旦日历层被修，本单需要第二次迭代**。
- `services.yaml` 是**多文档 YAML**，追加位置错了会让 `--validate` 失败。
