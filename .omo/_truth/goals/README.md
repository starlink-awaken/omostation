# .omo/goals/ — 目标管理

> Phase 级别目标定义和进度跟踪。人类设定目标，Agent 执行并报告进度。
> 运行时读写入口一律使用 `/.omo/goals/current.yaml`；当前目录是该入口背后的事实面存储位置。

---

## 目录结构

```
goals/
├── README.md        ← 本文件
├── current.yaml     ← 当前 Phase 目标（运行时唯一读写源，经 broker/人类维护）
└── history/         ← 已完成 Phase 的目标（复盘用）
    └── phase1.yaml
```

## 目标格式

```yaml
# current.yaml
phase: 1
status: active
start_date: "2026-05-29"
target_date: "2026-07-10"

goals:
  - id: G1.1
    desc: "kairon × SharedBrain 整合完成"
    kpi: "Docker 5/5 healthy + 烟雾 6/6 PASS"
    progress: 80%
    status: in_progress
    tasks: [T1.1.1, T1.1.2, T1.1.5, T1.2.1, T1.2.6]
    
  - id: G1.2
    desc: "agentmesh LiteLLM 路由就绪"
    kpi: "3+ 模型自动路由 + 回退"
    progress: 0%
    status: pending

health_targets:
  D1_vision: 85
  D2_coverage: 57
  D3_stories: 75
  D4_maturity: 74
  D5_architecture: 71
  D6_entropy: 50
  D7_security: 90
  D8_techdebt: 60
  overall: 75
```

## 使用约定

1. 人类或受审计 broker 更新 `current.yaml`
2. Agent 执行任务 → 更新 `.omo/tasks/active/` 状态
3. 目标进度由 `system_aggregator` Agent 自动计算（completed_tasks / total_tasks）
4. Phase 结束时，current.yaml → history/phase{N}.yaml

## 路径约定

- `/.omo/goals` 是指向 `/.omo/_truth/goals` 的符号链接，目的是把“运行时入口”与“事实面归档位置”统一起来。
- 文档若讨论当前目标，一律引用 `/.omo/goals/current.yaml`。
- 事实面索引可提到 `/.omo/_truth/goals/`，但不得把它表述成独立于 `/.omo/goals/current.yaml` 的第二写入目标。
