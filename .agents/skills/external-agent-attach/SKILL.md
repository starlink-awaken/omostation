---
name: external-agent-attach
description: "Attach an external AI agent (Claude Code, Codex, Cursor, custom MCP host) to omostation via Agora MCP + BOS + agent-workflow. Use when onboarding a foreign agent, configuring MCP, or asking how to connect another agent to this workspace."

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# External Agent Attach

Thin skill for **non-workspace-native** agents. Canonical one-pager:

→ [`docs/operations/external-agent-attach-card.md`](../../../docs/operations/external-agent-attach-card.md)

## When To Use

- User says "接入其他 agent" / "connect Cursor" / "add Codex MCP" / "external agent"
- New host runtime that is not already wired to cockpit
- After architecture change that broke MCP attach

## Do

1. Run smoke: `python3 bin/ssot/mcp-attach-smoke.py`
2. Configure Agora MCP stdio (see Attach Card §2)
3. Call only the **minimum 8 tools** until domain work is clear
4. For edits: ADR-0203 workflow lifecycle (`project-governance` skill)
5. Prefer `resolve_bos_uri` for cross-layer work

## Don't

- Use `agora tools` (invalid subcommand)
- Treat `status: unimplemented` BOS rows as live (AGT pack, etc.)
- Write `.omo` state without omo broker / workflow claim
- Stage high-conflict submodule gitlinks without PASW (ADR-0371)

## Profiles

| Need | Profile |
|------|---------|
| Read-only audit | `external-readonly-agent` or `observer-agent` |
| Contribute code/docs | `external-contributor-agent` or `engineering-agent` |

Fragment to merge if missing: `.agents/profiles/external-agent-profiles.fragment.yaml`

## Related skills

- `agent-onboarding` — full 5-phase workspace onboarding
- `bos-service-discovery` — BOS browse/resolve
- `project-governance` — mandatory workflow
- `a2a-coordination` — multi-agent tasks
