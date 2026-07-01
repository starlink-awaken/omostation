# OPC P6 weekly retro — 2026-W27

Generated: 2026-07-01T07:21:01Z

## 1. Radar (P5-F1)
- **📈 复用机会: renamed topic (多次出现, 值得抽象)**
  - source: `cockpit:research`
  - timestamp: `2026-07-01T07:11:16Z`
  - next_action: 评估抽象为共享模块 + 关联源研究
  - evidence_id: 243
- **📈 复用机会: renamed topic (多次出现, 值得抽象)**
  - source: `cockpit:research`
  - timestamp: `2026-07-01T06:38:04Z`
  - next_action: 评估抽象为共享模块 + 关联源研究
  - evidence_id: 227
- **🔍 待观察: broken topic (来自 研究)**
  - source: `cockpit:research`
  - timestamp: `2026-07-01T07:11:16Z`
  - next_action: 持续追踪, 累积信号后再决策
  - evidence_id: 247
- **🔍 待观察: broken topic (来自 研究)**
  - source: `cockpit:research`
  - timestamp: `2026-07-01T06:38:04Z`
  - next_action: 持续追踪, 累积信号后再决策
  - evidence_id: 231

## 2. Drift detector (P6-G3)
- kinds: 4
- drift_count: **1**
  - `entry_drift` → ok
  - `doc_drift` → DRIFT
  - `duplicate_facts` → ok
  - `agora_bypass` → ok

## 3. Gap → top candidates (sorted)
1. score=2.0 lane=drift title=Fix doc_drift drift
2. score=1.0 lane=radar title=📈 复用机会: renamed topic (多次出现, 值得抽象)
3. score=1.0 lane=radar title=📈 复用机会: renamed topic (多次出现, 值得抽象)
4. score=1.0 lane=radar title=🔍 待观察: broken topic (来自 研究)
5. score=1.0 lane=radar title=🔍 待观察: broken topic (来自 研究)

## 4. Task (planned, 人工审批)
- `OPC-P6-LOOP-2026-W27-00` | Fix doc_drift drift | approval_required=True
- `OPC-P6-LOOP-2026-W27-01` | 📈 复用机会: renamed topic (多次出现, 值得抽象) | approval_required=True
- `OPC-P6-LOOP-2026-W27-02` | 📈 复用机会: renamed topic (多次出现, 值得抽象) | approval_required=True
- `OPC-P6-LOOP-2026-W27-03` | 🔍 待观察: broken topic (来自 研究) | approval_required=True
- `OPC-P6-LOOP-2026-W27-04` | 🔍 待观察: broken topic (来自 研究) | approval_required=True

## 5. Swarm (派发受红线约束)
- planned_dispatch: ['OPC-P6-LOOP-2026-W27-00', 'OPC-P6-LOOP-2026-W27-01', 'OPC-P6-LOOP-2026-W27-02', 'OPC-P6-LOOP-2026-W27-03', 'OPC-P6-LOOP-2026-W27-04']
- note: P6 closeout 范围内只 plan; 实际派发受红线 'self-evolution task 仅落 planned' 约束

## 6. Audit (跨仓 trail)
- llm_audit_tail_count: 0

## 7. Retro / next-action
```json
{
  "stage": "retro",
  "ts": "2026-07-01T07:21:01Z",
  "summary": {
    "radar_candidates": 4,
    "radar_archive_path": "/Users/xiamingxing/Workspace/.omo/_delivery/scenarios/technical-radar/20260701T072101Z-technical-radar-9b67919e.json",
    "drift_count": 1,
    "planned_tasks": 5,
    "audit_records": 0,
    "history_weeks_recorded": 6,
    "history_max_consecutive_weeks": 6
  },
  "next_action": "next week's loop continues; if drift > 0 trigger self-evolve register",
  "evidence_complete": true
}
```

## 7.5. History / continuity
- weeks_recorded: 6
- max_consecutive_weeks: 6
- latest_week: 2026-W29

## 8. 人工审批栏
- [ ] reviewer A: ____  date: ____
- [ ] reviewer B: ____  date: ____

---
loop runner: scripts/opc_p6_weekly_loop.py
drift detector: scripts/opc_p6_drift_detector.py
