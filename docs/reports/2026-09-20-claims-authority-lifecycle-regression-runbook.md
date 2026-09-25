---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
created: 2026-09-20
---


# Claims Authority Lifecycle Regression Authorization and Runbook

## Status

`AUTHORIZATION_PENDING — NO LIFECYCLE EFFECT EXECUTED`

This repository-only report is the single proposed content change for the WP1
legacy-publication regression canary.  It records the exact authorization
binding and execution boundaries; it does not claim graduation, operational
proof, or business value.

## Immutable activation binding

- Authority: `omo-claims-authority-r0`
- Epoch: `1`
- State: `shadow-active`
- Activation receipt: `sha256:96654eb9e03591b2b5da2cb89119997c9ec2c193755ae7c277b3a0ce7be1e5d3`
- Descriptor: `sha256:e2be953eb9d04d421f184c60c7d1c4196d6698a874bcf0827795a8b4e8d357cd`

## Accepted engineering contract

- Spec: `repo://docs/superpowers/specs/2026-09-10-claims-authority-bridge-wp1-shadow-design.md`
- Spec version: `1.9.0`
- Spec content digest: `sha256:b643890f3fda5bee575630018b155fb68ba0ce6f58af9c2b6772a2ff29bb0197`
- WorkPacket ID: `WP-BET-Y1Q4-T10-145`
- WorkPacket digest: recomputed at execution from the current Ledger and accepted
  Spec; mismatch is a hard stop.

## One-time effect boundary

The only authorized external effect is one repository-only commit containing
this report, one annotated tag, one non-force branch push, one unique PR, and
one squash merge after all required contexts pass.  A failed required context is
a stop condition: no retry, no force update, and no merge.

Before push, the canonical broker must issue a legacy fence and enter
publishing.  After push, remote HEAD must be double-read and the fence settled
with the observed OID and effect-process identity.  If any outcome is unknown,
the packet stops without a replacement effect.

## Forbidden

- force push or `--no-verify`;
- automatic retry after an unknown outcome;
- changes to gitlinks, implementation code, Ledger, completion/value evidence,
  branch protection, or runtime state;
- promotion of v2 above shadow;
- enablement of Claims instruction capability;
- mutation or backfill of historical receipts.
