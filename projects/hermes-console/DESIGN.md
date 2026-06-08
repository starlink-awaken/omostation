# DESIGN.md

Hermes Console — operator-facing React SPA for monitoring and managing OMO swarm
workers and their brain state. Phase A (infrastructure) is complete; Phase B
(verification + test coverage) is pending per the team-plan worker decomposition.

## Purpose

Hermes Console is the human-facing dashboard for the OMO multi-agent system.
It surfaces real-time state from workers (Nucleus, BaseMembrane, SharedBrain,
OMO scheduler) via MCP connections, allowing operators to:

- Inspect running workers and their brain health
- View topology of the agent mesh
- Monitor compute usage and memory
- Configure worker parameters
- Trigger workflow runs

## Architecture

**Stack:** React 19 + TypeScript + Vite (bun), no CSS framework (raw CSS per
component), no external chart library.

**Data flow:**

```
Operator Browser
     │
     ▼
React SPA (hermes-console/)
     │ HTTP/MCP
     ▼
cockpit MCP server ──→ kairon/ (worker state)
     │
     ▼
gbrain/ (brain state via MCP)
```

The SPA communicates exclusively through the cockpit MCP server. It does not
connect directly to kairon or gbrain.

**Key components:**

| Component | Role |
|-----------|------|
| `Dashboard` | Main overview: worker health, brain score, recent events |
| `ComputeView` | CPU/memory/IO metrics per worker |
| `EnginesView` | LLM engine status and routing |
| `TopologyView` | Agent mesh graph visualization |
| `WorkflowsView` | Active workflow list and status |
| `WorkflowGraph` | Single workflow DAG renderer |
| `SettingsView` | Configuration panel |
| `SandboxTerminal` | Embedded terminal for ad-hoc commands |
| `MemoryInjector` | Memory injection into active workers |

**Design tokens** (follows gbrain admin SPA pattern for consistency):

| Token | Value | Use |
|-------|-------|-----|
| `--bg-primary` | `#0a0a0f` | Page background |
| `--bg-secondary` | `#14141f` | Sidebar, cards |
| `--bg-tertiary` | `#1e1e2e` | Subtle surfaces |
| `--text-primary` | `#e0e0e0` | Body text |
| `--text-secondary` | `#888` | Headings, labels |
| `--accent` | `#3b82f6` | Active states, links |
| `--success` | `#22c55e` | Healthy / ok |
| `--warning` | `#f59e0b` | Warnings |
| `--error` | `#ef4444` | Failures |

**Typography:** Inter for UI, JetBrains Mono for data/numbers.

**Spacing:** 4 / 8 / 16 / 24 / 32px scale.

## Phase B Scope

Pending work per team-plan worker-1:

- [ ] Verify MCP connectivity to cockpit
- [ ] Add integration tests for each view
- [ ] Complete Component health coverage
- [ ] Document API surface (MCP tool calls consumed by the SPA)

## What's NOT here yet

- Authentication / authorization (operator tool, single-user by default)
- Persistence layer (stateless; state comes from MCP at render time)
- Mobile layout (desktop-only; operator tool)
- Light mode (dark theme only; operator tool)

## References

- cockpit MCP server: `projects/cockpit/`
- OMO worker registry: `.omo/workers/`
- team-plan handoff: `.omc/handoffs/team-plan.md`
