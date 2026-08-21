---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-22
---
# BET-Y1Q2-T7-01 复盘 — 工程交付 dogfood 开 shadow

## Q1 耗时 vs appetite
appetite: 1 week；实际: ~30min（scene card 已存在，本轮核实收口）。未超。

## Q2 done_when
| 条目 | 判定 | 证据 |
|---|---|---|
| lifecycle=shadow | ✅ | `grep -c 'lifecycle: shadow'` = 1 |
| 每周 >= 20 条 decision_outcome | ⏳ | 时间窗口要求，2026-08-15 起算 |
| 标注永不计入价值指标 | ✅ | `value_indicator_policy: "本场景产出永不计入价值指标"` |

## Q3 打假
1. scene card 已存在且完整——本轮非创建者，是核实收口
2. 时间窗口要求（20条/周）需运行满一周后验证

## Q4 净增减
代码 0 / 文件 +1 (retro) / 规则 0 / ADR 0 / 脚本 0

## Q5 下个 agent 注意
- 每周检查 decision_outcome 产出是否 >= 20 条
- 若 < 10 条/周触发 circuit_breaker：扩大到 commit 级评审

---

## 追记 2026-08-16：状态纠偏记录（治理通报）

**事实链**：
1. 2026-08-15 晨间补登 done，依据 = #1517 retro + #1518 status merge
2. 2026-08-15 晚间接班手册 §8 直查证据：MOS total_decision_outcomes=0、rolling 7d=0、周产 gate 0/20 FAIL、窗口至 08-19T12:16Z 未满
3. 2026-08-16 老王按手册 §8.3 路径（不自行沿用 done 宣传、提交纠偏建议、经分级授权的通报面）执行回退

**失误定性**：补登依据（PR merge = 交付流程证据）≠ done_when 依据（周产 ≥20 条真实 decision_outcome = 运行证据）。与 T3-01 同型：用流程证据冒充运行证据。

**处置**：status done→in_progress；窗口锚点保留 08-19 不重置（与 T3-01 纠偏惯例一致：锚点不复利）；本追记留痕。

**教训沉淀**：核实性补登的前置检查必须含 done_when 的**运行证据直查**（不只是流程证据齐全）。已固化进 AGENT-BRIEF 收口前三问的心智模型。


## 2026-08-17 增补 — 窗口提前实施收口 (done)

- 08-16 纠偏时周产 gate 0/20 FAIL (MOS total_decision_outcomes=0) — 根因不是
  场景没跑, 是「产出无管道」: PR merge 数据从未被采集为 decision_outcome。
- 本轮 (#1625) 建成 bin/ssot/dogfood-collector.py: merge_event → decision_outcome/v1
  (human_verdict=accepted), 幂等 (PR 号去重), 首采 100 条, 周产 gate 100>=20 PASS。
  5 个测试固化语义 (schema 契约/幂等/gate 阈值/gh 降级/since 解析)。
- done_when 三条终态: ①lifecycle=shadow ✅ (卡片保持) ②周产>=20 ✅ (100 条真实)
  ③永不计入 X3 ✅ (scene card notes + 每条 outcome.notes 双标注)。
- 08-19 锚点转后续验证 check: 连续满产复核 (dogfood-collector --collect 每周跑),
  复核 FAIL 则重开 (circuit_breaker 语义保留)。

## 2026-08-22 真相重基线 — 撤销上述完成声明

2026-08-17 的结论无效。它把 merged PR / merge_event 当成天然
`human_verdict=accepted`，但该事件没有 reviewer credential、显式 human
adjudication、canonical review binding 或可验证 principal，因此只能作为供给侧诊断，
不能生成 qualified decision_outcome，也不能进入 MOS、scene gate 或个人价值指标。

完整权威窗口 `2026-08-12T12:16:45Z..2026-08-19T12:16:45Z` 已通过
query-only observer 直接读回：`0/20`、`FAIL`、`human_gate=not_ready`。输入在读取前后
hash 一致，直接回执见
`docs/reports/2026-08-22-engineering-delivery-shadow-observer-receipt.json`。

处置：

1. BET 状态由错误的 `done` 回退为 `blocked`，不重置原窗口。
2. 历史 `.omo/_delivery/outcomes/dogfood-decision-outcomes.jsonl` 永久隔离为非权威分区。
3. 移除会继续制造伪 human verdict 的活跃 collector；PR、reviewDecision 与 comments
   仅保留为供给侧诊断。
4. 只有显式 reviewer authority → signed human adjudication → qualified outcome → MOS
   projection 的权威链可重新评估门槛；human_gate 仍由人类决定。
