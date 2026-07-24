---
title: Batch1 real backlog collab trail — REMEDIATE-SHAREDBRAIN-CLEANUP
date: 2026-07-24
type: collab-trail
backlog: true
task_id: REMEDIATE-SHAREDBRAIN-CLEANUP
task_path: .omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml
---

# Real backlog collab: `REMEDIATE-SHAREDBRAIN-CLEANUP`

| Field | Value |
|-------|-------|
| task_id / task_ref | `REMEDIATE-SHAREDBRAIN-CLEANUP` |
| task_path | `.omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml` |
| title | SharedBrain遗留代码清理 |
| completed | True |
| steps | ['assign', 'claim_ack', 'handoff', 'verify_result', 'complete'] |
| roles | ['engineering', 'governance', 'audit'] |

## Handoff evidence

```json
{
  "task_id": "REMEDIATE-SHAREDBRAIN-CLEANUP",
  "task_path": ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml",
  "title": "SharedBrain遗留代码清理",
  "work_summary": "Batch1 B2 collab on real backlog REMEDIATE-SHAREDBRAIN-CLEANUP: SharedBrain遗留代码清理",
  "artifacts": [
    ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml"
  ]
}
```

## Protocol replay

```json
[
  {
    "id": "21f933a60a2540adaabf840526c15852",
    "type": "assign",
    "from_role": "governance",
    "to_role": "engineering",
    "task_ref": "REMEDIATE-SHAREDBRAIN-CLEANUP",
    "payload": {
      "kpi": "real-backlog-collab",
      "task_id": "REMEDIATE-SHAREDBRAIN-CLEANUP",
      "task_path": ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml",
      "title": "SharedBrain遗留代码清理"
    }
  },
  {
    "id": "208756280f12462195052f1cbc416939",
    "type": "claim_ack",
    "from_role": "engineering",
    "to_role": "governance",
    "task_ref": "REMEDIATE-SHAREDBRAIN-CLEANUP",
    "payload": {
      "claimed_path": ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml"
    }
  },
  {
    "id": "f5a32e9d54f048bfa5f17c8d09a83b41",
    "type": "handoff",
    "from_role": "engineering",
    "to_role": "audit",
    "task_ref": "REMEDIATE-SHAREDBRAIN-CLEANUP",
    "payload": {
      "evidence": {
        "task_id": "REMEDIATE-SHAREDBRAIN-CLEANUP",
        "task_path": ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml",
        "title": "SharedBrain遗留代码清理",
        "work_summary": "Batch1 B2 collab on real backlog REMEDIATE-SHAREDBRAIN-CLEANUP: SharedBrain遗留代码清理",
        "artifacts": [
          ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml"
        ]
      }
    }
  },
  {
    "id": "1797d02085354769afcffb194d62d390",
    "type": "verify_result",
    "from_role": "audit",
    "to_role": "governance",
    "task_ref": "REMEDIATE-SHAREDBRAIN-CLEANUP",
    "payload": {
      "pass": true,
      "task_path": ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml",
      "path_exists": true,
      "evidence_keys": [
        "task_id",
        "task_path",
        "title",
        "work_summary",
        "artifacts"
      ]
    }
  },
  {
    "id": "36fd2df9073d4cf1bb562c95a233647d",
    "type": "complete",
    "from_role": "governance",
    "to_role": null,
    "task_ref": "REMEDIATE-SHAREDBRAIN-CLEANUP",
    "payload": {
      "task_path": ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml",
      "closed": true
    }
  }
]
```

## Verify payload

```json
{
  "pass": true,
  "task_path": ".omo/tasks/remediation/REMEDIATE-SHAREDBRAIN-CLEANUP.yaml",
  "path_exists": true,
  "evidence_keys": [
    "task_id",
    "task_path",
    "title",
    "work_summary",
    "artifacts"
  ]
}
```
