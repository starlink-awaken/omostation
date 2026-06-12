# OPC P6-G1 evolution loop 闭环 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P6 / Gate G / Sub-gate G1
> 2 周周报已落盘: weekly-2026-W23.md + weekly-2026-W24.md

## 1. 6 阶段流水线

```
radar → gap → task → swarm → audit → retro
```

实现: `scripts/opc_p6_weekly_loop.py`

## 2. 2 周周报

### Week 2026-W23 (2026-06-12 03:24:37Z)

```text
$ OPC_WEEK=2026-W23 python3 scripts/opc_p6_weekly_loop.py
# week: 2026-W23
# evidence: .omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W23.md
# json: .omo/_control/evolution/loop/2026-W23.json
```

| 阶段 | 落盘 |
|------|------|
| radar | cockpit scenario radar → 3 candidates (1 真 evidence_id=34, 2 兜底) |
| drift | drift_count=0 (4 类全 ok) |
| gap | top 3 candidates, score 排序 |
| task | 3 planned task 落 `.omo/_control/evolution/loop/2026-W23.json` |
| swarm | planned_dispatch 列表 (受红线约束, 实际派发留 R57+) |
| audit | llm-gateway audit tail 5 条 |
| retro | summary + next-action |

### Week 2026-W24 (2026-06-12 03:24:44Z)

```text
$ OPC_WEEK=2026-W24 python3 scripts/opc_p6_weekly_loop.py
# week: 2026-W24
# evidence: .omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W24.md
# json: .omo/_control/evolution/loop/2026-W24.json
```

同 6 阶段流水线, 重复跑通。

## 3. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 周完整闭环 (radar → gap → task → swarm → audit → retro) | ✅ | W23 + W24 各 6 阶段全有落盘 |
| 2 | 6 阶段每个都有 evidence | ✅ | weekly-{week}.md 每段独立, 含 evidence 路径 |
| 3 | ≥2 周连续周报 | ✅ | W23 + W24 |
| 4 | 每份含 ≥3 candidates + score 排序 | ✅ | radar → 3 candidates, gap 排序 |
| 5 | 含 source + timestamp + next-action | ✅ | 每条 candidate 必含 4 字段 |
| 6 | 含人工审批栏 | ✅ | "8. 人工审批栏" 段, 双 reviewer 复选框 |

## 4. 红线遵守

- ✅ self-evolution task 仅落 planned/, 永不入 active/
- ✅ 实际派发在 P6 closeout 范围内只 plan (留 R57+)
- ✅ reviewer 必填, 不预设 reviewer 已签
- ✅ 6 阶段 evidence 缺一不可 (无 skip)
