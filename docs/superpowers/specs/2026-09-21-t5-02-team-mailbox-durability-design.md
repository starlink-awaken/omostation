---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: team-mailbox durable delivery and fallback semantics
bet_id: BET-Y2Q2-T5-02
created: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---


# team-mailbox durable delivery and fallback semantics

## Problem

The BET-Y2Q2-T5-01 send/receive primitives are best-effort: a failed delivery
vanishes silently and there is no backoff, no dead-letter quarantine, and no
documented fallback path. Orchestration (T5-ORCH) cannot harden on top of
lossy delivery.

## Change

Build on the T5-01 primitives without changing their public interface. Add a
delivery layer with bounded retries under exponential backoff, a durable
outbox directory fsynced before acknowledgement, and a `dead_letter`
quarantine for messages exhausting retries. Document the fallback path:
operators drain `dead_letter` back into the outbox after fixing the cause.
Cover with `bun test` cases: retry-then-success, exhaustion-to-dead-letter,
and fallback redelivery. The public `send`/`receive`/`list` interface stays
unchanged.

## Acceptance

- `cd ~/.config/opencode/plugin/team-mailbox && bun test` exits 0.
- `grep -r -c "dead_letter" ~/.config/opencode/plugin/team-mailbox` exits 0.
- `grep -c "team-mailbox" ~/.config/opencode/opencode.json` reports >= 1.

## Non-goals

- Multi-agent orchestration protocols (fork-join) belong to BET-Y2Q2-T5-03.
- No change to the T5-01 public send/receive interface.
