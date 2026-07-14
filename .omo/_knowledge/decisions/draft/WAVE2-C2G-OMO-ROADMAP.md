# Wave 2: C2G + OMO 迭代路线图 (草案)

> Draft — 待评审后转为正式 ADR

## 目标

在 Wave 1 (闭环反馈 + 预测治理 + 测试覆盖 + 性能优化) 基础上深化：

| 方向 | 内容 | 优先级 |
|------|------|--------|
| **数据闭环** | OutcomeTracker 实际数据回测，驱动 C2G 策略自动调参 | P0 |
| **预测模型增强** | 引入时间序列模型 (ARIMA/Prophet) 替代简单阈值评分 | P0 |
| **可视化** | Cockpit 接入 PredictiveGovernance 仪表盘 + 风险热力图 | P1 |
| **自动联动** | C2G Outcome → OMO 治理规则自动调整 (feedback loop) | P1 |
| **MOF 深化** | M2 schema 增加 M0 工具链验证器 (mof-validate 覆盖新 schema) | P1 |
| **跨仓一致性** | 新增 M2 schema 与现有 55 个 schema 的交叉引用审计 | P2 |

## 时间线

- Phase A (数据闭环): 2 周
- Phase B (预测增强 + 可视化): 2 周
- Phase C (自动联动 + MOF 深化): 1 周
