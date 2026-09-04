---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: External Agent Attach Card — Minimum Path
type: doc
---
# External Agent Attach Card — Minimum Path

> **Purpose**: one-page attach guide for Claude Code / Codex / Cursor / custom MCP hosts.  
> **Authority pointers**: `projects/agora/etc/bos-services.yaml` · `.omo/_truth/registry/agent-workflows/`
> **Discovery projection**: `docs/generated/capability-registry.yaml` (generated, read-only, not SSOT)
> **Smoke**: `python3 bin/ssot/mcp-attach-smoke.py`

---

## 1. Model (do not invent a second bus)

| Role | Surface |
|------|---------|
| Human | `cockpit` CLI / Web |
| External agent | **Agora MCP** → `resolve_bos_uri` / `list_bos_*` |
| Governed writes | `agent-workflow` lifecycle (ADR-0203) — never raw `.omo` I/O |
| High-conflict submodules | PASW / `gac-worktree` (ADR-0371) — internal; not a BOS product API |

---

## 2. MCP config (stdio)

```json
{
  "mcpServers": {
    "agora": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "projects/agora",
        "agora",
        "mcp"
      ]
    }
  }
}
```

Alternate (L3 wrapper):

```bash
uv run --project projects/cockpit cockpit mcp --transport stdio
```

> **Do not** use `agora tools --json` — that subcommand does **not** exist. List tools via the MCP session `list_tools`, or `cockpit mcp --list-tools`.

---

## 3. Minimum tool belt (8)

| # | MCP tool | Use |
|---|----------|-----|
| 1 | `resolve_bos_uri` | Call any `bos://…` service |
| 2 | `list_bos_resources` | Discover services (optional prefix) |
| 3 | `list_bos_domains` | Domain map |
| 4 | `health_check` | Hub health |
| 5 | `a2a_send_task` | Delegate to another agent |
| 6 | `list_agent_cards` | Discover peer agents |
| 7 | `agora_capability_discover` | Capability catalog |
| 8 | `audit_query` | Governance audit read |

Everything else is progressive disclosure. Full hub inventory: regenerate `docs/generated/capability-registry.yaml`.

---

## 4. First five minutes

```bash
# 0) smoke (no long-lived server required)
python3 bin/ssot/mcp-attach-smoke.py

# 1) identity / checklist
uv run --project projects/cockpit cockpit agent-onboard --json

# 2) BOS domains (routable only by default)
uv run --project projects/cockpit cockpit bos list
# include non-routable yaml rows (unimplemented/deprecated):
uv run --project projects/cockpit cockpit bos list --all

# 3) external channels inventory (ECCP)
uv run --project projects/cockpit cockpit channels
# or: python3 bin/ssot/gen-external-channels-inventory.py

# 4) KEMS (if needed)
uv run --project projects/cockpit cockpit kems status

# 5) governed work (ADR-0203)
make agent-workflow-bootstrap
uv run --with pyyaml python bin/agent-workflow.py start project-code-change \
  --profile external-contributor-agent --objective "<summary>"
# if profile is not yet merged under agent-workflows/profiles/, use engineering-agent
uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path <path>
# …edit…
uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>
```

---

## 5. Profiles

| Profile | Intent | Default workflows |
|---------|--------|-------------------|
| `external-readonly-agent` | Observe only | `observer-audit`, `handoff-resume` |
| `external-contributor-agent` | Code/docs under claim | `project-code-change`, `project-doc-change` |
| `engineering-agent` / `governance-agent` | Full workspace roles | see `.omo/_truth/registry/agent-workflows/profiles/` |

If profiles are missing from the live registry, fall back to `observer-agent` / `engineering-agent` and open a `project-doc-change` to merge `.agents/profiles/external-agent-profiles.fragment.yaml`.

---

## 6. Honesty rules

1. **BOS `unimplemented` / `deprecated` are not routable** by default (agora `bos_registry` filter). Do not retry AGT 8-pack as live services until status is `active`.
2. Prefer `resolve_bos_uri` over inventing parallel CLIs for cross-layer calls.
3. Internal surfaces (PASW, P79 gates, pyright-sweep tooling) stay on `bin/gac/*` + workflows — see `docs/operations/internal-only-surfaces.md`.
4. Skills live under `.agents/skills/` — host agents must load them (Claude plugins / Codex skills path). Recommended pack: `external-agent-attach`, `agent-onboarding`, `bos-service-discovery`, `project-governance`, `a2a-coordination`.

---

## 7. Related

- Skill: `.agents/skills/external-agent-attach/SKILL.md`
- Onboarding: `.agents/skills/agent-onboarding/SKILL.md`
- BOS discovery: `.agents/skills/bos-service-discovery/SKILL.md`
- Callchain: `docs/I0-AGORA-CALLCHAIN.md`
- Capability projection: `docs/generated/capability-registry.yaml` (`python3 bin/ssot/gen-capability-registry.py`)
