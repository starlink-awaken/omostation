---
schema_version: receipt/v1
type: report
title: Value-Proof Debt Registry — Spine done BETs
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last_updated: 2026-09-05
---

# Value-Proof Debt Registry

**Observed**: 2026-09-05T09:54:05Z  
**Ledger**: `docs/plans/3y-bet-ledger.yaml`  
**Entries**: 135 (NOT_PROVEN=135, REJECTED=0)  
**With attestation**: 0

## Circuit Breaker

Per BET-Y1Q4-T4-05 design: when attestation/signed evidence is unavailable,
leave `NOT_PROVEN` as the official status rather than forging `ACCEPTED`.
This prevents "已 done" from being misread as "愿景已证明".

## Methodology

Scan `docs/plans/3y-bet-ledger.yaml` for BETs where:
1. `status == done`
2. `value_indicator_policy == false`
3. `completion_evidence.axes.value.status` ∈ {`NOT_PROVEN`, `REJECTED`}

## Entries

| BET ID | Track | VIP | Value Status | Has Attestation | Suggested Action |
|--------|-------|-----|--------------|-----------------|-------------------|
| BET-Y1Q3-T10-111 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-110 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-109 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-108 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-107 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-104 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-103 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-102 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-101 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-100 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-99 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-98 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-97 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-96 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-95 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-93 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-94 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-92 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-91 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-90 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-89 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-88 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-87 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-86 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-85 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-84 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-83 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-82 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-81 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-80 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-79 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-78 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-73 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-74 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-76 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-77 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-71 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-70 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-69 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-68 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-65 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-62 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-64 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-66 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-61 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-63 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-56 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-57 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-60 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-59 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-55 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-54 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-52 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-51 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-49 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-50 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-44 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T4-03 | T4-OUTCOME | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T4-04 | T4-OUTCOME | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T4-05 | T4-OUTCOME | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T4-06 | T4-OUTCOME | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T4-08 | T4-OUTCOME | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-02 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T1-12 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T6-15 | T6-SUBTRACT | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-23 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-25 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-26 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-27 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-45 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-46 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-28 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-47 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-29 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-30 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-31 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-32 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-33 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-34 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-35 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-36 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-37 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-38 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-39 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-40 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-41 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-42 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-106 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-112 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-114 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-119 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-120 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-121 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-01 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T2-01 | T2-PERCEPT | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T2-02 | T2-PERCEPT | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T2-03 | T2-PERCEPT | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T3-02 | T3-COGNI | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T3-03 | T3-COGNI | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T7-03 | T7-SCENE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-02 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-03 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T2-04 | T2-PERCEPT | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T2-05 | T2-PERCEPT | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T10-01 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T1-13 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-200 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q3-T10-201 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T6-02 | T6-SUBTRACT | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-03 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-04 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-05 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-06 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-07 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-08 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-05 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-09 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T6-03 | T6-EVOLUTION | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T9-01 | T9-OBSERV | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-13 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T9-02 | T9-OBSERV | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T10-04 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T10-02 | T10-MATURITY | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-11 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-12 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-13 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-14 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-17 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-18 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-19 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T8-20 | T8-SURFACE | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-HITL-02 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-12 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T1-14 | T1-TRUTH | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |
| BET-Y1Q4-T4-03 | T4-OUTCOME | False | NOT_PROVEN | ❌ | backfill-or-written-exemption |

## References

- `docs/superpowers/specs/2026-09-05-bet-y1q4-t4-05-value-proof-debt-registry-design.md`
- `KR-VALUE-JOURNEY-COMPLETION`, `KR-VALUE-WEEKLY-ADOPTION`, `KR-VALUE-REVISION-RATE`
