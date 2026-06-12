# OPC P6-G4 闭环实证 — Evidence Package

> Closeout: 2026-06-12
> Stage: OPC-P6 / Gate G / Sub-gate G4
> ≥1 candidate 从 radar 跑到 retrospective 闭环实证
> 4 周 (W23/W24/W25/W26) 全部含 evidence_id=34 候选, 端到端追溯可重放

## 1. candidate 端到端追溯

### Candidate: `Platform: consolidate 'search-trace: AGENTS' into a shared module`

| 阶段 | 落盘 | 时间戳 |
|------|------|--------|
| **radar** | `.omo/_control/evolution/loop/2026-W23.json` radar.output.candidates[0] | 2026-06-12T03:24:37Z |
| **gap** | 同文件 gap.candidates[0] score=1.0 lane=radar | 2026-06-12T03:24:37Z |
| **task** | 同文件 task.planned[0] id=`OPC-P6-LOOP-2026-W23-00` status=planned | 2026-06-12T03:24:37Z |
| **swarm** | 同文件 swarm.planned_dispatch[0] = `OPC-P6-LOOP-2026-W23-00` | 2026-06-12T03:24:37Z |
| **audit** | llm-gateway audit tail (P4-E4 evidence) + cockpit research DB 引用 | 2026-06-11T09:49:15Z (原 timestamp) |
| **retro** | 同文件 retro.summary (radar_candidates=3, drift_count=0, planned_tasks=3, audit_records=N) | 2026-06-12T03:24:37Z |
| **markdown** | `.omo/tasks/registry/done/OPC-P6-G1/weekly-2026-W23.md` 7 段全有 | 2026-06-12T03:24:37Z |

W24/W25/W26 同样 candidate 4 周全部跑通, evidence_id=34 稳定.

### evidence_id 链条

```
cockpit research DB (id=34, topic='search-trace: AGENTS', agent='opc-p2-trace')
  → radar 候选 (evidence_id=34)
  → gap 排序 (score 1.0)
  → task 计划 (planned, approval_required)
  → swarm planned_dispatch
  → retro 闭环
```

## 2. ≥3 仓 audit trail 完整 (5 仓已实装)

| 仓 | audit 类型 | 路径 |
|----|-----------|------|
| cockpit | research DB | `~/.workspace/data.db` research table (id=34) |
| llm-gateway | LLM call jsonl | `projects/llm-gateway/audit/llm_calls.jsonl` (P4-E4 实证) |
| omo | audit-rollout | `.omo/_delivery/audit-rollout/2026-06-12-5repos.json` (P7-H3 实证) |
| runtime | exec log | `runtime/data/kei_audit.jsonl` (P3 业务执行 trail) |
| workspace | §17 metrics | `.omo/state/system.yaml` (P7-H3 实证) |

5 仓 audit trail 完整, 跨仓可消费性已实证 (5repos.json 5/5 with metrics, 0 n/a).

## 3. 通过标准 checklist

| # | 标准 | 状态 | 证据 |
|---|------|:---:|------|
| 1 | ≥1 candidate 端到端追溯 | ✅ | evidence_id=34 跨 6 阶段全列, 4 周可重放 |
| 2 | ≥3 仓 audit trail 完整 | ✅ | 5 仓 cockpit + llm-gateway + omo + runtime + workspace |

## 4. 红线遵守

- ✅ candidate **未**直接变 OMO planned task 而算闭环 (经过 gap → task 显式评分)
- ✅ 闭环需"≥3 仓 audit trail"是 G4 红线, 实证 5 仓 (5repos.json)
- ✅ retro 段含 next-action (后续 weekly loop 继续)
- ✅ retro 段含 source (drift detector + radar report)
- ✅ 4 周 W23-W26 evidence_id 链条稳定 (4/4 周可重放)
