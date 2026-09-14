---
name: agent-onboarding
description: "Onboard a new AI agent into the omostation workspace. Covers agent profile registration, MCP connection setup, BOS URI discovery, cockpit CLI orientation, and first workflow lifecycle run. Use when adding a new agent (Claude Code, Codex, Cursor, custom) or re-onboarding after a major architecture change."

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# Agent Onboarding - New Agent Integration Workflow

The guided onboarding path for any AI agent joining the omostation workspace. Walks through 5 phases: identity registration, MCP connection, BOS discovery, cockpit orientation, and first governed workflow.

## When To Use

- A new AI agent (Claude Code, Codex, Cursor, OpenCode, custom) needs to join the workspace
- An existing agent needs re-onboarding after major architecture changes
- User says "onboard this agent" / "接入新 agent" / "how does a new agent start here"

## Prerequisites

- Workspace cloned with submodules: `git clone --recursive`
- Python 3.13+ and `uv` installed
- Agent has read access to `AGENTS.md` and `CLAUDE.md`

## Phase 1: Identity Registration

Register the agent in `.omo/_truth/registry/agent-workflows/profiles/_base.yaml::agent_profiles`.

### 1.1 Choose or Create a Profile

Existing profiles cover common roles:

| Profile | Purpose | Example Agent |
|---------|---------|---------------|
| docs-agent | Markdown/docs only | Documentation writer |
| engineering-agent | Project code changes | Feature developer |
| qa-agent | Verification & testing | Test runner |
| governance-agent | Governance-sensitive edits | Gac/omo operator |
| state-sync-agent | Runtime projection refresh | State sync daemon |
| mof-agent | MOF model changes | Schema maintainer |
| c2g-agent | Strategy ingress | Pitch materializer |
| observer-agent | Read-only oversight | Auditor |
| any-agent | Session resume/handoff | All agents (fallback) |

If none fits, register a new profile:

```yaml
agent_profiles:
  <new-agent-profile>:
    purpose: "<one-line purpose>"
    allowed_workflows: [<workflow-id>, ...]
    can_write_lanes: [<lane>, ...]
    closeout_required: [<check-id>, ...]
```

### 1.2 Verify Registration

```bash
uv run --with pyyaml python bin/agent-workflow.py agents
uv run --with pyyaml python bin/agent-workflow.py lint
```

## Phase 2: MCP Connection

Connect the agent to the Agora MCP server for BOS URI resolution, governance audit, A2A task delegation, and service discovery.

### 2.1 Start Agora MCP Server

```bash
# Ensure agora is available
git submodule update --init projects/agora

# Start the MCP server (stdio or HTTP mode)
uv run --project projects/agora agora server --transport stdio
# Or HTTP mode:
uv run --project projects/agora agora server --transport http --port 8700
```

### 2.2 Register MCP in Agent Config

For Claude Code (`~/.claude/`):
```json
{
  "mcpServers": {
    "agora": {
      "command": "uv",
      "args": ["run", "--project", "projects/agora", "agora", "server", "--transport", "stdio"]
    }
  }
}
```

For other agents, adapt to their MCP config format. The key tools the agent needs:

| MCP Tool | Purpose |
|----------|---------|
| `resolve_bos_uri` | Call any BOS service by URI |
| `list_bos_resources` | Discover available services |
| `list_bos_domains` | Browse BOS domain structure |
| `register_service` | Register agent's own services |
| `a2a_send_task` | Delegate tasks to other agents |
| `list_agent_cards` | Discover other agents |
| `audit_query` | Query governance audit log |
| `swarm_status` | Check swarm node availability |

### 2.3 Verify MCP Connection

> Do **not** use `agora tools` — that subcommand does not exist.

```bash
# Via cockpit
uv run --project projects/cockpit cockpit mcp --list-tools

# Via agora directly
uv run --project projects/cockpit cockpit mcp --list-tools
python3 bin/ssot/mcp-attach-smoke.py
```

## Phase 3: BOS URI Discovery

Learn the BOS URI namespace and how to call services. See the companion skill `bos-service-discovery` for detailed browsing.

### 3.1 Browse Available Services

```bash
# List all BOS domains
uv run --project projects/cockpit cockpit bos capability --list-domains

# List services in a domain
uv run --project projects/cockpit cockpit bos capability --domain memory

# Or via MCP
# Call list_bos_resources() and list_bos_domains()
```

### 3.2 Key BOS Domains

| Domain | Purpose | Example URIs |
|--------|---------|-------------|
| `memory` | Knowledge graph, search, indexing | `bos://memory/kos/search` |
| `governance` | Audit, OMO operations, evolution | `bos://governance/omo/audit` |
| `brain` | Knowledge cards, events | `bos://brain/events/card_updated` |
| `compute` | Local LLM inference | `bos://compute/aetherforge/infer` |

### 3.3 Call a BOS Service

```bash
# Via cockpit
uv run --project projects/cockpit cockpit bos resolve "bos://memory/kos/search" --args '{"query": "test"}'

# Via MCP: call resolve_bos_uri(uri="bos://memory/kos/search", arguments={"query": "test"})
```

## Phase 4: Cockpit CLI Orientation

Cockpit is the L3 unified entry point. The agent should know the key subcommands.

### 4.1 Explore Available Commands

```bash
uv run --project projects/cockpit cockpit help
uv run --project projects/cockpit cockpit help <keyword>
```

### 4.2 Essential Commands for Any Agent

| Command | Purpose |
|---------|---------|
| `cockpit agent` | Agent workflow lifecycle (delegates to `bin/agent-workflow.py`) |
| `cockpit agent-workflow list` | List available workflows |
| `cockpit bos` | BOS URI resolution and discovery |
| `cockpit governance` | Governance health and evolution |
| `cockpit status` | System health overview |
| `cockpit mcp` | MCP server management |
| `cockpit skill` | Skill discovery |

## Phase 5: First Governed Workflow

Every requirement iteration MUST go through the workflow lifecycle (ADR-0203).

### 5.1 Bootstrap

```bash
make agent-workflow-bootstrap
make agent-workflow-status
```

### 5.2 Start + Claim

```bash
# Suggest the right workflow
uv run --with pyyaml python bin/agent-workflow.py suggest --from-diff --profile <agent-profile>

# Start
uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> \
  --profile <agent-profile> --objective "<summary>"

# Claim the paths you will touch
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path <path>
```

### 5.3 Work, Verify, Closeout

```bash
# ... make edits ...

# Verify
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute

# Closeout
make agent-workflow-closeout RUN_ID=<run-id>

# Compliance check
make agent-workflow-compliance
```

## Onboarding Checklist

- [ ] Agent profile registered under `.omo/_truth/registry/agent-workflows/profiles/`
- [ ] `agent-workflow.py agents` lists the new profile
- [ ] `agent-workflow.py lint` passes
- [ ] Agora MCP server starts and responds
- [ ] Agent config has MCP server entry
- [ ] `list_bos_resources` returns service list
- [ ] `cockpit help` shows available commands
- [ ] First workflow run completed (bootstrap -> start -> claim -> verify -> closeout)
- [ ] `agent-workflow.py compliance` passes

## Related

- Skills: `bos-service-discovery`, `a2a-coordination`, `project-governance`, `external-agent-attach`
- Registry: `.omo/_truth/registry/agent-workflows/`
- Contract: `.omo/standards/agent-workflow-contract.md`
- ADR-0203: Mandatory requirement iteration workflow
- Cockpit: `projects/cockpit/README.md`
- Agora: `docs/I0-AGORA-CALLCHAIN.md`
