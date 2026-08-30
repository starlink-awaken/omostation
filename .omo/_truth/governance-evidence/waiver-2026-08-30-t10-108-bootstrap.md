---
schema: workflow-waiver/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-08-30
last-reviewed: 2026-08-30
title: BET-Y1Q3-T10-108 self-bootstrap waiver
type: doc
---

# BET-Y1Q3-T10-108 self-bootstrap waiver

waiver: user-explicit
when: 2026-08-30T22:36:00+08:00
who: xiamingxing
quote: "我给你授权，按照标准流程推进吧。不行就创建bet来"
continuation_quote: "全面推进吧"
scope:
- docs/plans/3y-bet-ledger.yaml::BET-Y1Q3-T10-108
- docs/superpowers/specs/2026-08-30-cc-switch-recovery-state-relocation-design.md
- .omo/_truth/governance-evidence/waiver-2026-08-30-t10-108-bootstrap.md
reason: The approved recovery-state design needs a startable BET before a formal governed implementation run can claim code, registry, evidence, and host-mutation surfaces.
risk: Bootstrap declarations only; no implementation code, registry mutation, or host data movement is authorized by this waiver itself.
residual: Obtain written spec review, write the implementation plan, then use a formal BET-bound run with exact claims and test-first implementation.
gate_bypass: 1
no-run-id: true

formal_planning:
  run_id: 20260830T145443Z-bet-execution-91e1ffd9
  purpose: Write and validate the approved implementation plan with exact path claims.
  note: Implementation and host mutation require fresh formal execution runs after the design PR reaches main.

spec_amendment:
  authorized_quote: "全面推进吧"
  from_version: 1.0.0
  to_version: 1.0.1
  old_digest: sha256:b85c3264f03288f67d2e6cf0d6902afa90054d5e712e37ce92783c4c2e40ecf4
  new_digest: sha256:bb513598b8c08a970b7100e5becfc73478e643ded7b2b269bcb2822c0d09579b
  reason: GaC bin quota rejected a new governance entry; reuse the existing registered Documents owner job and keep bin surface flat.
  scope: Entry-point ownership only; transaction semantics, target, source roots, rollback, testing, and value boundaries are unchanged.

work_packet_amendment:
  authorized_quote: "全面推进吧"
  added_surface: tests/test_documents_content_plane_migration_check.py
  reason: The authoritative existing regression hard-codes the complete migration family set and must acknowledge the new family while preserving candidate_count 17.
  scope: Test expectation only; no migration semantics, production code, host data, or accepted specification digest changes.
