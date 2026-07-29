---
status: active
lifecycle: audit
owner: governance-team
last-reviewed: "2026-07-29"
---
# P86 A2 批次5: independent+none+well_defined 等量墙钟对照

> 上位: P86 §A2 · R1 剔除 5.4x 后补测  
> 🔴 口径: **等量工作单元** 并行 (协作) vs 顺序 (单 worker)；驱动 shipped `scenario_lib.run_scenario`  
> 非 haiku 多 agent 会话；是**可复现进程级真 dispatch**（独立 well_defined 批量）

## 任务

对 3 个独立 designed 场景各跑一遍 `run_scenario`（等量 3 单元）:

- ADV01-circular-dependency
- ADV03-deadlock-unresolved
- ADV05-broken-chain

| 模式 | 定义 | 墙钟 |
|------|------|------|
| 单 worker | 顺序执行 3 单元 | **0.032s** |
| 协作 (并行) | ThreadPool 3 workers，墙钟 = 包络 | **0.019s** |

**协作墙钟优 1.65x**（0.032 / 0.019）。3/3 单元均 PASS。

## 与作废 5.4x 的关系

| 项 | 5.4x (剔除) | 本批次5 |
|----|------------|---------|
| 来源 | P81 估算 / 无 output_file | 本机复跑 + 日志 |
| 等量 | 否 | **是**（同 3 场景） |
| 可追溯 | 否 | `batch5-simple-independent-wallclock.log` + 本审计 |

## 结论

在 **independent + none + well_defined** 机械批量上，等量并行相对顺序有墙钟正收益。  
**不**外推到思考性 multi-agent 会话；思考性见 batch2/3/4 + R1 纯 text。
