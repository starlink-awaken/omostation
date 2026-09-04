---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
bet_id: BET-Y1Q3-T10-103
---

# Vault daily health Workspace owner cutover — implementation evidence

## Result

The sole forbidden executor reported by T10-102 was cut over in the actual
Claude Scheduled skill. `vault-daily-health` now invokes the canonical
Workspace `learning-control-plane all` owner and writes its heartbeat under
Workspace runtime state. Cadence and all other Scheduled skills were untouched.

## Preflight and rollback package

- Source:
  `/Users/xiamingxing/Documents/Claude/Scheduled/vault-daily-health/SKILL.md`
- Before SHA-256:
  `b84f0c9f17162e9a838ea7fe546871b3712e43153c967fd1582ca0b740bca2e9`
- Before bytes/mode: `2259 / 0644`
- Backup:
  `/Users/xiamingxing/Workspace/runtime/quarantine/documents-scheduled-vault-daily-health-20260830/SKILL.md.before`
- After SHA-256:
  `0ba603a50d338c4a7aeab6fecb9119718b32fed44c82339eae00f395fee1df5f`
- After bytes/mode: `2539 / 0644`
- Manifest SHA-256:
  `fe698389b6bc7905502738a9933674558ec063795edf7c29834b2a0f94538f63`

The backup is byte-identical to the preflight source. The manifest is
`documents-host-config-cutover/v1`, `status=completed`, and
`permanent_deletion=false`.

## Exact host diff

Only two declared blocks changed:

1. Legacy `bash ~/Documents/@学习进化/_control/l4-kernel.sh all` became the
   system-Python Workspace owner command with explicit Documents/Workspace
   roots and JSON output. The mode descriptions now match the eight owner
   checks and preserve `status=attention` as a finding.
2. The heartbeat moved from
   `Documents/@驾驶舱/_generated/heartbeats/vault-daily-health` to
   `Workspace/runtime/heartbeats/vault-daily-health`.

The target was the only file in `Documents/Claude/Scheduled` with a new ctime
during the transaction. The old heartbeat file was retained as rollback/history.

## Postflight

The exact owner command returned exit 1 with structured evidence:

- status: `attention`
- mode_count: 8
- unavailable_modes: 0
- writes_documents: false

The fresh complete host consumer audit returned exit 0:

- status: `ok`
- active observations: 207
- forbidden executors: 0
- unmatched executors: 0
- Workspace owner reads: 14
- content references: 193

Evidence is stored under
`.omo/evidence/20260830T100926Z-bet-execution-08ae5d95/` in the delivery
clone. A Workspace heartbeat canary was created at the new path.

## Boundary

The installed `accepted-20260908` release predates the learning control-plane
owner, so this transaction uses the current `/Users/xiamingxing/Workspace`
execution root rather than pretending the accepted release has parity. The
next automatic Claude 08:02 execution and its UI history remain temporally
unproven; this report proves configuration, owner canary, and consumer cutover.

## Mainline closure

Root PR #2731 was squash-merged as
`79ff4a4eccda66d4ae48811e9ba60e88592ed8d2`. Required tests, GaC,
interface, evidence, and governance-verify checks completed successfully. A
fresh mainline replay preserves owner `writes_documents=false` and consumer
`status=ok`, `forbidden_executors=0`, `unmatched=0`; receipts are under
`.omo/evidence/20260830T103527Z-bet-execution-e97a9763/` in the closeout
clone.
