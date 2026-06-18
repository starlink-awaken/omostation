# OPC Master Execution Playbook

> Status: active
> Scope: reviewer-facing phase execution baseline for OPC P3-P7

## Baseline

- P3: implementation complete; Gate D passed (2026-06-12)
- P4: implementation complete; Gate E passed (2026-06-12, E1-E4 closed)
- P5: implementation complete; Gate F passed (2026-06-13, F1-F4 closed)
- P6: implementation complete; Gate G passed (2026-06-13, G1-G4 closed)
- P7: implementation complete; Gate H passed (2026-06-13, H1-H5 closed)

## Gate Map

| Phase | Gate | Runtime carrier |
|---|---|---|
| P3 | Gate D | `.omo/tasks/registry/done/OPC-P3-GATE-D-OPENING.yaml` |
| P4 | Gate E | `.omo/tasks/done/OPC-P4-MODEL-COMPUTE.yaml` |
| P5 | Gate F | `.omo/tasks/done/OPC-P5.yaml` |
| P6 | Gate G | `.omo/tasks/done/OPC-P6.yaml` |
| P7 | Gate H | `.omo/tasks/done/OPC-P7.yaml` |

## Reviewer Notes

- Phase carrier 以当前真实 task 载体为准，不强依赖 `planned/` 历史路径。
- `docs/OPC-PHASE*.md` 只保留骨架、状态和 signal，不复制运行时快照。
- `.omo/tasks/registry/done/*/evidence-package.md` 是子 gate 的最细颗粒证据入口。

## 4.4 Acceptance integrity red lines

1. Do not weaken original criteria during closeout.
2. Do not let plan status contradict its own evidence.
3. Do not bypass human approval for self-evolution tasks.
