---
id: BET-Y1Q3-T3-04
type: retro
status: archived
date: 2026-08-18
bet_id: BET-Y1Q3-T3-04
north_star_ref: docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
related:
  - BET-Y1Q3-T2-01
  - BET-Y1Q3-T2-03
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: "BET-Y1Q3-T3-04 Retro: 业务能力 bet 补位"
---

# BET-Y1Q3-T3-04 Retro: 业务能力 bet 补位

## Q1 目标回顾
从治理/文档域转向真实业务能力落地：感知面第二根管子（T2-01 文件夹/日历）或自主性阶梯判据（Y1Q4-T3-01）中选一，在 Y1Q3 内完成首个业务型 bet 交付。

## Q2 实际结果
**感知方向已选定并落地**：BET-Y1Q3-T2-01（感知面第二根管子）于 2026-08-16 done，交付真实用户可见产出：

- **双邮件源注册且有真实信号**：apple_mail_inbox + netease_mailmaster_inbox
  - netease 首条真实信号 2026-08-16T08:00Z（容器真名 com.netease.macmail 修正后）
- **signal-sources 抽象对第二类源成立**：无 if-else 特判（probe_depth 通用配置）
- **配套管道**：T2-03 信号落盘管道修复（探测深度 + health 回写 + state 防御）

## Q3 目标偏差
- 原 goal 提到"文件夹/日历已 candidate"，实际落地的第二根管子是**邮件源**（Apple Mail + Netease 邮件），而非文件夹/日历。方向一致（感知面），管子选择不同——邮件源比文件夹信号更实时、更结构化。
- 认知/自主性方向（Y1Q4-T3-01 自主性阶梯判据）未在 Y1Q3 落地，留待后续窗口。

## Q4 机制沉淀
- **业务补位通过 umbrella bet 实现**：T3-04 作为业务补位 umbrella，其 done_when 由 T2-01 的实际交付达成。业务型 done 计数（T2-PERCEPT 轨道）增加。
- **感知面第二根管子验证了抽象可扩展性**：signal-sources 抽象对两类源（文件夹 + 邮件）成立，为第三/四根管子（Y2Q4）铺路。
- **修复根因价值**：netease 容器真名修正（mailmaster → com.netease.macmail）说明"注册正确性"是信号源落地的关键，非代码逻辑问题。
- **业务/治理比提升**：Y1Q3 新增业务型 done（T2-01/T2-03），缓解 E1（业务比仅 23%）失衡。

## Q5 给下一个 agent 的建议
- 认知/自主性方向（Y1Q4-T3-01）是下一个业务型候选：自主性阶梯判据 + Agent 据心智模型决策。
- 感知面可继续深化：日历信号源、文件夹监控增强。
