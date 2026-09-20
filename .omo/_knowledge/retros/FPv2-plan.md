---
schema: bet-retro/v1
bet_id: FPv2-plan
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-20
type: ephemeral
completed_at: 2026-09-20
---

# Retro: FPv2 — FORWARD-PLAN v2 起草

## Summary

FORWARD-PLAN v1 (2026-09-19) 在 1 天内 §A/§B/§C2/§C3 全部完成,
需起草 v2 持续 6 个月路线图 (2026H2 - 2027H1). 核心思路:
"维护 + 探索" 双轨, 实战反馈循环 + 报告自动化 + C2 剩余 3 项.

## What went well

- **从 v1 完成到 v2 起草 1 天过渡**: 复用 C3 季度评估 + A1/A2/A3/B1/B2/C2 沉淀
  作 v2 输入
- **风险预判**: 列出 6 项风险 (工具采纳率 / 季度报告手工 / AI 误报 / bin-quota /
  SSL / 产出不确定), 每项配缓解
- **范围明确**: "不在范围内" 列 4 项, 防止 scope creep
- **新增门对齐 C1**: 工具采纳率 / 季度报告自动化 / C2 完成度 3 项新门,
  比 v1 更可量化

## What was learned

- **v1 寿命仅 1 天**: 36 个目标 100% 完成的速度超出预期. 后续 v2 要保留
  6 个月有效期, 不能太密集
- **C1 终局门扩展**: 4 项原门全部 done, 但 "12 周建议采纳" 仍是 "待证" 状态,
  这是 v2 短期 P0
- **C2 探索性剩 3/4**: 隐私保护 / Agent 联邦 / 跨域学习, 都是长期任务,
  不能急于 1 季度完成

## What to improve

- **§A1 反馈循环** 缺乏具体 KPI: 应加 "工具采纳率 ≥ 50% 第 4 周末" 等
  具体 milestone
- **§B1.2 隐私保护端侧** 范围模糊: 应进一步定义 "persona 数据" 边界
- **v2 终局门** "≥ 80% 工具采纳率" 可能定得太低: 应基于 Q3 实际 baseline 估算

## Metrics

- Files added: 1 (docs/OMOSTATION-FORWARD-PLAN-v2.md 150L)
- Files modified: 1 (docs/OMOSTATION-FORWARD-PLAN.md → superseded)
- Tests: N/A (文档类)
- Roadmap coverage: 6 个月 (2026H2 - 2027H1)
- §A 短期: 2 项 (反馈循环 / 报告自动化)
- §B 中期: 4 项 (C2 剩余 3 + 历史累积 1)
- §C 长期: 3 新增门 (工具采纳率 / 季度报告自动化 / C2 完成度)
- Risks tracked: 6
- PR: TBD
- Total LOC delta: +160

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| FORWARD-PLAN v2 doc 创建 | ✅ |
| v1 → status: superseded 标记 | ✅ |
| §A 短期 (反馈循环 + 报告自动化) | ✅ |
| §B 中期 (C2 剩余 3 项 + 历史累积) | ✅ |
| §C 长期 (C1 扩展 + C2 进展表 + C3 自动化) | ✅ |
| 风险 + 缓解 (6 项) | ✅ |
| 不在范围内 (4 项明确) | ✅ |
| 与 v1/C3/SOP/agent-onboarding 关联 | ✅ |