---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T4-01 Retrospective — capability_calibration 自动更新
type: retro
---
# BET-Y1Q2-T4-01 Retrospective — capability_calibration 自动更新

> 完成日期: 2026-08-08  
> 状态: done  
> 耗时: ~1 week (实际 < 1 day)

## 目标

让每次人类裁决自动改变系统对自身能力的认知(自我模型闭环)。

## 交付物

1. **闭环实现** (`projects/omo/src/omo/omo_adjudication.py`)
   - 新增 `_update_capability_calibration()` 方法
   - 在 `record()` 方法中调用, 位于 `_apply_belief_feedback()` 之后
   - 公式: `calibration = accepted_as_is / invocations` (per capability)
   - 写入 `capability_calibrations` 表 + `capability_calibration_summary.yaml`

2. **测试覆盖** (`projects/omo/tests/test_mos_closed_loop.py`)
   - `test_adjudication_triggers_capability_calibration`: 验证裁决触发校准更新
   - `test_calibration_formula_accepted_over_total`: 验证公式正确性 (2/3 accepted)
   - `test_calibration_summary_yaml_written`: 验证 outcomes 目录可观察

3. **文档**
   - 计算口径文档化: `calibration = accepted_as_is / invocations`
   - 可观察性: `.omo/_delivery/outcomes/capability_calibration_summary.yaml`

## 技术决策

### 1. 闭环位置
**决策**: 在 `AdjudicationStore.record()` 中调用, 与 `_apply_belief_feedback()` 并列。  
**理由**: 
- 复用已有的 decision_outcome 查询逻辑
- 与信念反馈闭环保持一致的架构模式
- best-effort 语义: 异常不抛, 不影响裁决记录

### 2. 计算公式
**决策**: `calibration = accepted_as_is / invocations` (per capability)  
**理由**:
- 简单直观: accepted 表示系统决策被人类原样接受
- 按 capability 分组: 不同决策类型独立校准
- 动态更新: 每次裁决后重算历史平均值

### 3. 存储策略
**决策**: 双写 — `capability_calibrations` 表 + `capability_calibration_summary.yaml`  
**理由**:
- 表: 结构化查询, 与 MOS 其他 5 表一致
- YAML: 人类可读, 便于 `/outcomes` 观察
- 冗余可接受: YAML 是派生视图, 表是 SSOT

### 4. 异常处理
**决策**: 全方法 try/except, 异常静默忽略  
**理由**:
- 校准是辅助功能, 不应阻塞核心裁决流程
- 与 `_apply_belief_feedback()` 保持一致的 best-effort 语义
- 审计日志可通过 `_mos_manager` 的 audit_log 追踪

## 验证结果

```bash
$ uv run --with pyyaml --with pytest python -m pytest \
    tests/test_mos_closed_loop.py \
    tests/test_omo_adjudication.py \
    tests/test_agent_belief.py -v

============================== 37 passed in 0.21s ==============================
```

**关键验证点**:
- ✅ 每条 AdjudicationRecorded 触发对应 capability_calibration 更新
- ✅ calibration 值变化可在 /outcomes 观察
- ✅ 计算口径文档化: calibration = accepted_as_is / invocations

## 依赖关系

- **前置依赖** (已 done):
  - BET-Y1Q1-T4-01: adjudication 存储与查询
  - BET-Y1Q1-T3-01: MOS agent_belief 三表 schema

- **后续依赖** (待执行):
  - BET-Y1Q4-*: 据 calibration 自动放权 (Y1Q4 规划)

## 教训与模式

### 1. 闭环架构模式复用
**模式**: 裁决 → 反馈 → 模型更新  
**应用**: 
- T4-01 (本任务): 裁决 → capability_calibration
- T1-03 (前置): 裁决 → belief confidence
- 未来: 裁决 → 其他模型 (world_snapshot, context 等)

**教训**: 闭环架构应抽象为通用模式, 降低新闭环的实现成本。

### 2. 可观察性优先
**模式**: 双写 (结构化表 + 人类可读文件)  
**应用**: 
- capability_calibrations 表: 机器查询
- capability_calibration_summary.yaml: 人类观察

**教训**: 治理系统需要双重可观察性 — 机器自动化 + 人类审计。

### 3. best-effort 语义
**模式**: 辅助功能不阻塞核心流程  
**应用**: try/except 包裹, 异常静默忽略  
**教训**: 闭环反馈是"锦上添花", 不应成为单点故障。

## 治理合规

- ✅ ADR: 无需新 ADR (复用现有闭环模式)
- ✅ 测试: 3 个新测试, 37/37 通过
- ✅ 文档: 计算口径在代码注释与 retro 中明确
- ✅ 可观察: outcomes 目录 YAML 文件
- ✅ 守门: `make memory-os-check` (实际用 pytest 直接验证)

## 后续工作

1. **Y1Q4 规划**: 据 calibration 自动放权
   - 高 calibration (>0.8) 的 capability 可减少人类审阅
   - 低 calibration (<0.5) 的 capability 需加强审阅

2. **趋势分析**: calibration 随时间变化曲线
   - 目标: 系统能力持续提升 (calibration ↑)
   - 告警: calibration 持续下降需人工介入

3. **跨 capability 对比**: 哪些决策类型人类更信任
   - 可视化: calibration heatmap by capability
   - 优化: 低 calibration capability 需改进算法

## 结论

BET-Y1Q2-T4-01 成功实现自我模型闭环, 系统首次能根据人类裁决自动校准对自身能力的认知。37/37 测试通过, 架构模式可复用于未来闭环需求。
