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
