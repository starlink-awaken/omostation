---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-30
---
# BET-Y1Q3-T4-07 Retrospective — Product P0 WP5 Human Adjudication to Principal-Bound Value

- date: 2026-08-30
- bet: BET-Y1Q3-T4-07 (T4-OUTCOME, human_gate, **value_indicator_policy=true**)
- status: engineering VERIFIED / operational PROVEN / **value NOT_PROVEN** → **blocked（等人类裁决）**

## 关键差异：本 BET 的 value 轴无法自动化

`value_indicator_policy: true` → 推导要求 `outcome_accepted`，即 value 轴必须 **ACCEPTED**，
四键证据全部绑定一条**真实 non-test** 的人类裁决：

| 证据键 | 内容 | 能否自动化 |
|--------|------|-----------|
| `real_signal` | 真实外部信号（非 fixture/合成/agent 自报） | ❌ 需真实信号进入 |
| `human_verdict` | principal 对真实 Decision Inbox 候选的 adopt/edit/ignore | ❌ **需人亲自操作** |
| `revision` | 人类改了什么（edit_diff） | ❌ 依附于真实裁决 |
| `time_burden` | 审阅耗时 | ❌ 依附于真实裁决 |

自动化能做到的止步于 `overall_state: blocked`。这是诚实状态，不是失败。

## 交付（实现已在 main）

- omo `75abeb3`（PR #119）WP5 authority-bound 合同骨架，`is_qualifying_outcome` 判定矩阵
- 主仓落地 commit：`c3f7cff179e46433f0fded42dd14337ae427fd84`
- omo verify 126 passed（test_personal_episode 1711 行 + test_engineering_delivery_consumer 953 行）
- **本次补齐**：cockpit 侧 `src/cockpit/tests/test_api_outcomes.py`（13 用例）
  —— verify 第 2 条此前指向一个**根本不存在的文件**，必然失败

## 本轮新增：机制 canary

`bin/ssot/human-adjudication-canary.py`，报告
`docs/reports/2026-08-30-human-adjudication-canary.json`，`scope: mechanism`：

1. `qualifying_happy_path` — real_human + authority receipt + persisted decision + lineage 全通过
2. `negatives_not_qualifying` — 7 类负例全部拒绝并给出原因：
   synthetic source_class / 空或非法 authority digest / principal 格式错 /
   decision 未持久化 / 缺 scene / 缺 episode
3. `append_only_semantics` — 同 decision 二次裁决追加而非覆盖，effective verdict 取最新
4. `cleanup` — 临时日志回收

## 过程中的一次误判（值得记）

第一版 canary 把「相同裁决重放产生第二条 adjudication 记录」断言为 bug
（`records_after_replay: 2`）。**实际是设计**：裁决日志 append-only，
accept→reject 后 effective verdict 取最新（`test_effective_verdict_accept_then_reject` 已覆盖）。
**计数去重不在这一层** —— 由 `PersonalEpisodeService.verdict_distribution` 承担。

教训：看到与 done_when 字面不符的行为，先查测试是否已覆盖该语义，再断言是缺陷。

## 陷阱

1. `value_indicator_policy: true` 与 `false` 的推导分支完全不同：
   true → 必须 `outcome_accepted`（value ACCEPTED）；false → `delivery_accepted`（value NOT_PROVEN）。
   写台账前先确认该字段，否则 `overall_state` 必然 mismatch。
2. verify 指向的文件可能根本不存在（本 BET 就是），跑之前先 `ls` 确认。
3. `merged_reachable_commit` 必须是主仓 bump commit，子仓 commit 在主仓对象库不存在。

## 解除 blocked 的路径（需 principal 到场）

1. 一条真实信号进入 Decision Inbox（非测试构造）
2. principal 对该候选执行 adopt / edit / ignore
3. OMO 写入恰好一个 adjudication + 一个 decision_outcome
4. 用真实裁决的 `episode_id` / `signal_event_id` 补齐 value 轴四键证据
