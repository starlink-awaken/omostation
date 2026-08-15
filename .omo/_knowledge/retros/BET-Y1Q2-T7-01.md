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
