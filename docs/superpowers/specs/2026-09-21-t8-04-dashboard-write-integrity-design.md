---
schema_version: specification/v1
spec_version: 1.0.0
title: Dashboard 写操作诚信修复 + 跨板块合成条
bet_id: BET-Y2Q2-T8-04
status: accepted
lifecycle: spec
owner: governance-team
created: '2026-09-21'
last-reviewed: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L1
human_gate: false
type: ssot
---

# BET-Y2Q2-T8-04: Dashboard 写操作诚信修复 + 跨板块合成条

## 目标

删除 workbench 重复写操作实现；页脚文案诚实披露唯一写例外；新增两个跨板块合成镜头卡。

## 变更范围

### 1. workbench_ui.js — 删除重复写操作

- 删除 `ZhixingAdjudicateProposal` 函数（已删除）
- 删除 workbench proposals Tab（已删除）
- 添加页脚文案，诚实披露唯一写例外：`quickAdjudicate` 在 `ecosystem_ui.js` 中保留为唯一写入口

### 2. ecosystem_ui.js — 新增跨板块合成镜头卡

添加两个 `data-synthesis-card` 元素，提供跨板块合成视角：

1. **价值-治理合成条**：聚合 value 面板与 governance 面板的写操作诚信指标
2. **健康-执行合成条**：聚合 health 面板与 execution 面板的系统健康状态

## 验收标准

1. `grep -c "ZhixingAdjudicateProposal" workbench_ui.js` → 0
2. `grep -c "data-synthesis-card" ecosystem_ui.js` → >= 1
3. 页脚文案明确披露 `quickAdjudicate` 为唯一写入口

## 非目标

- 不修改 `quickAdjudicate` 函数逻辑
- 不新增写操作端点
- 不修改其他 UI 面板
