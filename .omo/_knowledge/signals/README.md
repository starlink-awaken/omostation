---
type: ephemeral
status: archived
---

# 信号库（signals/）

> ADR-0443 决策分级：信号/draft 级内容在此**不占 ADR 编号**。人审后若升格为
> L1 架构决策，迁回 decisions/ 并占用新号；L2 战术决策并入战役 ADR 尾部。

- 来源：evolution-agent RSS 自动管道 + insufficient-cards 自动生成
- 迁入记录（2026-08-30，ADR-0443 Q12）：0401/0405（insufficient-cards）、
  0429/0437/0438（trend-signal；其中 0437/0438 为同一新闻重复生成）
- 编号处理：原编号随之退役不回收（历史引用不断链），新决策从 0444 起占号
- 2026-08-31 修复：`proposal-to-adr.py` 保留兼容命令名，但新 draft 只写本目录、
  使用 `signal://evolution/*` 身份；误入 decisions 的 `unhealthy_service` draft 已迁回。
