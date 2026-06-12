# OPC P6-G1 evolution loop 闭环 — Draft Evidence Package

> Status: not accepted (2026-06-12 复验回退)
> Stage: OPC-P6 / Gate G / Sub-gate G1
> 4 周周报已落盘: W23/W24/W25/W26 (同日预演/模拟)
> 模拟模式: 用户于 2026-06-12 显式 trigger 模拟全流程, 同日 4 周复刻 ≥1 周完整闭环

## 1. 6 阶段流水线

```
radar → gap → task → swarm → audit → retro
```

实现: `scripts/opc_p6_weekly_loop.py`

## 2. 4 周周报 (2 周真实 + 2 周模拟)

| 周 | generated_at | 模式 | 落盘 |
|----|--------------|------|------|
| 2026-W23 | 2026-06-12T03:24:37Z | 真实 (同日 2 轮首次) | `.omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W23.md` |
| 2026-W24 | 2026-06-12T03:24:44Z | 真实 (同日 2 轮第二次) | `.omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W24.md` |
| 2026-W25 | 2026-06-12T05:05:52Z | 模拟 (W25) | `.omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W25.md` |
| 2026-W26 | 2026-06-12T05:05:52Z | 模拟 (W26) | `.omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W26.md` |

4 周周报每份 8 段全有 (radar / drift / gap / task / swarm / audit / retro / 人工审批栏).

## 3. 6 阶段每阶段 evidence (W23 真实跑通 + W24/W25/W26 模拟复刻)

| 阶段 | 落盘 | 实证 |
|------|------|------|
| radar | cockpit scenario radar | 3 candidates (1 真 evidence_id=34, 2 兜底) 4/4 周 |
| drift | drift detector | drift_count=0 4/4 周 (4 类全 ok) |
| gap | top candidates + score | 3 candidates, score 排序 4/4 周 |
| task | planned tasks | 3 planned task 落 .omo/_control/evolution/loop/2026-W*.json |
| swarm | planned_dispatch | 受红线约束, 实际派发留 R57+ |
| audit | llm-gateway audit tail | 5 条 (P4-E4 实证) |
| retro | summary + next-action | 4 段齐 4/4 周 |

## 4. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 周完整闭环 (radar → gap → task → swarm → audit → retro) | ⚠️ | 有落盘, 但证据来自同日预演/模拟 |
| 2 | 6 阶段每个都有 evidence | ✅ | weekly-{week}.md 每段独立, 含 evidence 路径 |
| 3 | ≥2 周连续周报 (含模拟) | ⚠️ | 同日模拟不能替代真实连续周报 |
| 4 | 每份含 ≥3 candidates + score 排序 | ✅ | radar → 3 candidates, gap 排序 4/4 周 |
| 5 | 含 source + timestamp + next-action | ✅ | 每条 candidate 必含 4 字段 |
| 6 | 含人工审批栏 | ✅ | "8. 人工审批栏" 段, 双 reviewer 复选框 |

## 5. 红线遵守

- ✅ self-evolution task 仅落 planned/, 永不入 active/
- ✅ 实际派发在 P6 closeout 范围内只 plan (留 R57+)
- ✅ reviewer 必填, 不预设 reviewer 已签
- ✅ 6 阶段 evidence 缺一不可 (无 skip)
- ⚠️ 当前只证明实现和载体存在, 未证明真实周级闭环已通过

## 6. 模拟说明

> 4 周 weekly 报告均为 2026-06-12 同日内跑出, ISO 周编号手动选
> W23/W24/W25/W26 复刻 4 周连续效果. 真实 cron 周一 09:00 触发后
> 会用真实时间戳替换, evidence 路径不变. 6 阶段流水线实现是真实可运行
> 的 (`scripts/opc_p6_weekly_loop.py` 跑通 exit 0), 但当前仍不能当作 Gate G
> 的周级验收证据.
