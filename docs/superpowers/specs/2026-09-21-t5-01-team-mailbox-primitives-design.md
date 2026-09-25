---
schema: md/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: team-mailbox plugin scaffold and mailbox send-receive primitives
bet_id: BET-Y2Q2-T5-01
created: '2026-09-21'
implementation_authorized: true
value_indicator_policy: false
risk_level: L2
human_gate: false
---


# team-mailbox plugin scaffold and mailbox send-receive primitives

## Problem

Parallel agents coordinating through ad-hoc files have no shared mailbox
primitive: no single send/receive path, no plugin entry point, and no
registration in the operator's opencode configuration. Coordination state
scatters across worktrees and cannot be addressed uniformly.

## Change

Create the plugin directory `~/.config/opencode/plugin/team-mailbox/` with a
plugin entry module and a file-backed queue implementing `send`, `receive`,
and `list` primitives. Each message is one JSON file keyed by
`<mailbox>/<timestamp>-<sender>.json` with schema `{to, from, subject, body,
sent_at}`. Register the plugin in `~/.config/opencode/opencode.json` under
the `plugin` list as `team-mailbox`. Cover the round trip with `bun test`
cases: send-then-receive, empty-mailbox receive, and malformed-file skip.

## Acceptance

- `test -d ~/.config/opencode/plugin/team-mailbox` exits 0.
- `cd ~/.config/opencode/plugin/team-mailbox && bun test` exits 0.
- `grep -c "team-mailbox" ~/.config/opencode/opencode.json` reports >= 1.

## Non-goals

- Durable delivery semantics (retries, dead-letter) belong to BET-Y2Q2-T5-02.
- Multi-agent orchestration protocols (fork-join) belong to BET-Y2Q2-T5-03.
