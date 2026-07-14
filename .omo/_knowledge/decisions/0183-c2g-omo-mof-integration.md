# ADR-0183: C2G + OMO 新功能 MOF 元模型集成

- **Status**: ACTIVE
- **Date**: 2026-07-14
- **Owner**: governance-team + eCOS team

## Context

Wave 1 迭代（ADR-0182）新增了 C2G 和 OMO 的核心功能模块。这些模块需要与 eCOS MOF 元模型架构集成，以获得元模型层的一致性校验、可追溯性和自反性支持。

## Decision

为 4 个新功能模块创建对应的 M2 schema 和 M1 实例：

### M2 Schema

| Schema | M3 Parent | 对应代码模块 | 状态机 |
|--------|-----------|-------------|--------|
| `pitch.yaml` | BehavioralElement | C2G PitchAnalyzer | draft → submitted → evaluated → accepted → rejected → archived |
| `pitch_outcome.yaml` | BehavioralElement | C2G OutcomeTracker | created → evaluated → in_progress → completed → archived |
| `predictive_governance.yaml` | GovernanceElement | OMO PredictiveGovernanceEngine | idle → analyzing → forecasting → alerting → recommending → monitoring |
| `state_cache.yaml` | StructuralElement | OMO GovernanceStateCache | empty → populated → stale → invalidated |

### M1 Instances

每个 M2 schema 配一个示例 M1 实例目录：
- `m1/pitch/M1-PITCH-001.yaml`
- `m1/pitch_outcome/M1-OUTCOME-001.yaml`
- `m1/predictive_governance/M1-PRED-001.yaml`
- `m1/state_cache/M1-CACHE-001.yaml`

### Schema 设计原则

1. **requiredProperties**: 每个 schema 定义 3-5 个必填属性
2. **validationRules**: 包含跨字段校验规则
3. **examples**: 至少一个示例用例
4. **stateMachine**: 完整生命周期状态转换

## Consequences

### Positive
- 新功能获得元模型层一致性校验（mof-validate）
- 可通过 mof-bootstrap 进行自反检查
- 可被其他 M2 schema 引用和依赖
- 可在 Cockpit 中可视化展示

### Negative
- M2 schema 数从 48 增加到 55
- schema 需要与代码实现保持同步更新
- 新增的元模型面需要维护

## Implementation

- 项目: `projects/ecos/`
- M2 目录: `src/ecos/ssot/mof/m2/`
- M1 目录: `src/ecos/ssot/mof/m1/`
- 关联 ADR: ADR-0182
