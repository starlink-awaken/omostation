# BET-Y1Q2-T6-02 Closeout: ADR 分层 (active/historical)

**BET ID**: BET-Y1Q2-T6-02
**Track**: T6-SUBTRACT
**Window**: Y1Q2
**Status**: done
**Completed at**: 2026-08-08

## Objective
将 ADR 分为 active/historical 两层，归档不再适用的 ADR 以减少认知负载。不删任何一份。

## Analysis
扫描 .omo/_knowledge/decisions/ 下全部 ADR，按以下标准分类：
- **active**: 当前仍指导决策、未被 superseded 的 ADR
- **historical**: 已被后续 ADR 取代、或描述的状态已过时的 ADR

## Action
- 对 historical 层 ADR 在 frontmatter 添加 `status: historical` 标记
- 保留文件不删除 (审计需要)，但降低其在索引中的优先级
- ADR INDEX 更新反映分层状态

## Verification
- active ADR 均未被标记为 superseded
- historical ADR 均有明确的 superseded-by 或 reason 字段
- 分层本身就够, 不设定 active 数量硬指标
