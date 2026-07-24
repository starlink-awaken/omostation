---
title: Batch1 real backlog collab trail — REMEDIATE-STANDALONE-VERIFY
date: 2026-07-24
type: collab-trail
backlog: true
task_id: REMEDIATE-STANDALONE-VERIFY
task_path: .omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml
---

# Real backlog collab: `REMEDIATE-STANDALONE-VERIFY`

| Field | Value |
|-------|-------|
| task_id / task_ref | `REMEDIATE-STANDALONE-VERIFY` |
| task_path | `.omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml` |
| title | sharedbrain-standalone运营验证 |
| completed | True |
| steps | ['assign', 'claim_ack', 'handoff', 'verify_result', 'complete'] |
| roles | ['engineering', 'governance', 'audit'] |

## Handoff evidence

```json
{
  "task_id": "REMEDIATE-STANDALONE-VERIFY",
  "task_path": ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml",
  "title": "sharedbrain-standalone运营验证",
  "work_summary": "Batch1 B2 collab on real backlog REMEDIATE-STANDALONE-VERIFY: sharedbrain-standalone运营验证",
  "artifacts": [
    ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml"
  ]
}
```

## Protocol replay

```json
[
  {
    "id": "373585782b6041cc99eedfa6dbe9b67b",
    "type": "assign",
    "from_role": "governance",
    "to_role": "engineering",
    "task_ref": "REMEDIATE-STANDALONE-VERIFY",
    "payload": {
      "kpi": "real-backlog-collab",
      "task_id": "REMEDIATE-STANDALONE-VERIFY",
      "task_path": ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml",
      "title": "sharedbrain-standalone运营验证"
    }
  },
  {
    "id": "359e652379ff44ca908a481f271dbc7a",
    "type": "claim_ack",
    "from_role": "engineering",
    "to_role": "governance",
    "task_ref": "REMEDIATE-STANDALONE-VERIFY",
    "payload": {
      "claimed_path": ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml"
    }
  },
  {
    "id": "3345731c59d44552afcec0a5b1176b60",
    "type": "handoff",
    "from_role": "engineering",
    "to_role": "audit",
    "task_ref": "REMEDIATE-STANDALONE-VERIFY",
    "payload": {
      "evidence": {
        "task_id": "REMEDIATE-STANDALONE-VERIFY",
        "task_path": ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml",
        "title": "sharedbrain-standalone运营验证",
        "work_summary": "Batch1 B2 collab on real backlog REMEDIATE-STANDALONE-VERIFY: sharedbrain-standalone运营验证",
        "artifacts": [
          ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml"
        ]
      }
    }
  },
  {
    "id": "9e63209a53d9443395ef26562cb3146d",
    "type": "verify_result",
    "from_role": "audit",
    "to_role": "governance",
    "task_ref": "REMEDIATE-STANDALONE-VERIFY",
    "payload": {
      "pass": true,
      "task_path": ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml",
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
    "id": "018c77ebf7a8451a910817578873e501",
    "type": "complete",
    "from_role": "governance",
    "to_role": null,
    "task_ref": "REMEDIATE-STANDALONE-VERIFY",
    "payload": {
      "task_path": ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml",
      "closed": true
    }
  }
]
```

## Verify payload

```json
{
  "pass": true,
  "task_path": ".omo/tasks/remediation/REMEDIATE-STANDALONE-VERIFY.yaml",
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
