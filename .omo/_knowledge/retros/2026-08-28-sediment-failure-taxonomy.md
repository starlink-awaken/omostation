---
status: active
lifecycle: report
owner: engineering-agent
last-reviewed: 2026-08-28
---

# Sediment 失败分类报告 (P2 项, 2026-08-28)

> 数据源: workflow-mesh/events.jsonl 全流 StepFailed × 153 (sediment 报 115/502=23% 为同期口径)

## 分类结果

| workflow 类型 | 失败数 | 占比 | 典型状态 |
|--------------|--------|------|----------|
| **mini** | 51 | 33% | failed |
| bet-execution | 29 | 19% | failed |
| project-code-change | 24 | 16% | failed |
| governance-state-mutation | 15 | 10% | **blocked** |
| project-doc-change | 15 | 10% | **blocked** |
| governance-audit | 7 | 5% | blocked |
| observer-audit | 4 | 3% | blocked |
| external-adapter-sync | 2 | 1% | failed |

## 按日分布 (改善趋势)

```
08-07~09: 14+16+20 (高峰, mini/bet 失败为主)
08-22~25: 16+1+5+17 (次高峰)
08-26:    10
08-27:     2  ← 治理修复周开始
08-28:     1  ← 显著改善
```

## 三个发现

1. **error 字段统一为 "workflow failed"** — execute 步骤的真实错误
   (hook 拦截/超时/断言?)在发布时被吞掉。修复方向: 事件发布点透传
   exit code / stderr 首 200 字符。(治本项, 未在本轮做)

2. **mini workflow 占失败 1/3** — "mini" 是什么? 高频轻量流程失败
   51 次无人处理, 值得单独深挖 (可能是周期性任务的已知噪音)

3. **blocked ≠ failed** — governance 类失败多为 blocked (被治理门拦下),
   属"正常拦截被记为失败", 建议事件分级时把 blocked 降级为 info 级
   (动脉 B 的后续项)

## 与 sediment 23% 的关系

sediment 统计口径 = 失败 runs / 总 runs (115/502)。本报告提供的是
失败**成分**: 真实失败 (mini/bet/code) vs 治理拦截 (governance blocked)。
真实失败率 ≈ 106/502 = 21%, 治理拦截 ≈ 41/502 = 8%。
