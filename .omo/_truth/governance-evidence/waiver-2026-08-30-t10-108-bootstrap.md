---
schema: workflow-waiver/v1
lifecycle: history
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
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

recovery_corpus_amendment:
  authorized_quote: "全面推进吧"
  from_version: 1.0.1
  to_version: 1.0.2
  old_digest: sha256:bb513598b8c08a970b7100e5becfc73478e643ded7b2b269bcb2822c0d09579b
  new_digest: sha256:2c73609e12406af70db5a0a6f82b3516e8b6c460c8759022a72494592bf32cd9
  observed_file: .cc-switch-recovery2/current.db
  observed_sha256: sha256:df0a17b1cb391f3cf78426853269402fbf3be578f86f051bc1e280bb0431c76a
  reason: The recovery corpus intentionally retains a pre-repair corrupt database while six other recognizable SQLite recovery files are healthy; relocation must preserve both facts byte-identically.
  scope: SQLite evidence classification only; source roots, target, movement, rollback, active/iCloud exclusions, and value boundary are unchanged.

formal_execution:
  implementation_pr: 2763
  implementation_commit: 898e5f6ee0878ad218333693a0cc40a73326a1ef
  recovery_amendment_pr: 2765
  recovery_amendment_commit: e72bf052af1f09d9e87502b979b97fd165777bf5
  host_run_id: 20260830T163244Z-bet-execution-5affab11
  status: host-verified
  note: Final ledger closeout and workflow closeout remain in the closeout PR.
