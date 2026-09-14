---
name: bos-service-discovery
description: "Browse and call BOS URI services in the omostation workspace. Lists available domains, services, and transports. Use when an agent needs to find a service by domain, understand BOS URI routing, or resolve a URI for the first time."

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# BOS Service Discovery - Domain Browsing and URI Resolution

Guide for discovering and calling BOS (Bus of Services) URIs. BOS is the domain-based service routing layer in agora (I0). Every service is identified by a `bos://<domain>/<package>/<action>` URI.

## When To Use

- Agent needs to find a service but does not know the exact URI
- Agent wants to understand what domains are available
- Agent needs to register a new BOS service
- User says "what services are available" / "how do I call X" / "bos uri"

## How BOS Routing Works

```
bos://<domain>/<package>/<action>
  |         |         |       |
  |         |         |       +-- What to do (search, mcp-server, audit, ...)
  |         |         +-- Which package provides it (kos, omo, eidos, ...)
  |         +-- Which domain owns it (memory, governance, brain, compute, ...)
  +-- Protocol prefix
```

Routing chain (9 steps, see `docs/I0-AGORA-CALLCHAIN.md`):
1. Domain authorization (CR-RBAC-01)
2. Rate limiter (20 QPS/domain)
3. Circuit breaker
4. Cache lookup
5. BOSRouter prefix match (Trie, O(k))
6. ProxyManager fallback
7. POC_SERVICES registry lookup
8. Transport execution (stdio / mcp_proxy / http)
9. L0 audit hook (mof_agora_hook)

## Discovery Commands

### List All Domains

```bash
# Via MCP tool
# Call list_bos_domains()

# Via cockpit
uv run --project projects/cockpit cockpit bos capability --list-domains

# Via agora
uv run --project projects/agora agora bos domains --json
```

### List Services in a Domain

```bash
# Via MCP tool
# Call list_bos_resources(prefix="bos://memory/")

# Via cockpit
uv run --project projects/cockpit cockpit bos capability --domain memory

# Read the SSOT directly
cat projects/agora/etc/bos-services.yaml | grep -A10 "domain: memory"
```

### Get Service Schema

```bash
# Via MCP tool
# Call get_bos_schema(uri="bos://memory/kos/search")

# Via cockpit
uv run --project projects/cockpit cockpit bos schema "bos://memory/kos/search"
```

### Resolve a URI (Execute)

```bash
# Via MCP tool
# Call resolve_bos_uri(uri="bos://memory/kos/search", arguments={"query": "test"})

# Via cockpit
uv run --project projects/cockpit cockpit bos resolve "bos://memory/kos/search" \
  --args '{"query": "test"}'

# Via agora CLI
uv run --project projects/agora agora bos resolve "bos://memory/kos/search" \
  --args '{"query": "test"}'
```

## Known BOS Domains

| Domain | Owner | Key Services | Transport |
|--------|-------|-------------|-----------|
| `memory` | kairon / mos | KOS search · **Memory OS** `bos://memory/mos/*` · Eidos/Ontoderive | stdio, mcp_proxy |
| `governance` | omo | OMO audit, state sync, governance evolution | http, stdio |
| `brain` | agora | Knowledge cards, event publishing | http |
| `compute` | aetherforge | Local LLM inference (AetherForge + omlxc) | http |

> Full registry: `projects/agora/etc/bos-services.yaml`
> Domain routing rules: `ARCHITECTURE.md` section 4

## Registering a New BOS Service

If the agent provides a service others should discover:

### 1. Add to bos-services.yaml

```yaml
services:
- uri: bos://<domain>/<package>/<action>
  domain: <domain>
  package: <package>
  action: <action>
  transport: stdio  # or mcp_proxy, http
  command:
  - uv
  - run
  - --directory
  - projects/<project>
  - python
  - -m
  - <module>
  - <action>
  description: "<what this service does>"
  status: active
```

### 2. Validate the Contract

```bash
# BOS contract lint
uv --directory projects/ecos run mof-contract-lint \
  --bos-yaml projects/agora/etc/bos-services.yaml

# Or use the skill
# Activate: bos-contract-fix skill if lint fails
```

### 3. Verify Registration

```bash
# Reload M1 routes (hot, no restart)
# Via MCP: call bos_reload_m1()

# Verify the service appears
uv run --project projects/cockpit cockpit bos capability --domain <domain>
```

## Middleware Status

Check rate limiting, circuit breaker, and cache health:

```bash
# Via MCP: call bos_middleware_status()
# Via cockpit:
uv run --project projects/cockpit cockpit bos middleware-status
```

## Common Patterns

### Pattern 1: Memory OS control plane (default for agents)

```bash
# Status / recall (preferred over raw kos/gbrain for general memory)
cockpit memory status --json
cockpit memory recall "agent workflow governance" --json
cockpit bos resolve bos://memory/mos/status
# MCP: resolve_bos_uri("bos://memory/mos/recall", {query, intent?, as_of?})
```

Skill: `memory-recall` · Docs: `docs/architecture/memory-os.md`

### Pattern 1b: Search the knowledge graph (direct KOS)

```python
# Via MCP
result = await resolve_bos_uri(
    uri="bos://memory/kos/search",
    arguments={"query": "agent workflow governance"}
)
```

### Pattern 2: Publish a brain event

```python
# Via MCP
result = await mutate_resource(
    uri="bos://brain/events/card_updated",
    payload={"card_id": "abc123", "content": "..."},
    action="update"
)
```

### Pattern 3: Trigger governance audit

```python
# Via MCP
result = await resolve_bos_uri(
    uri="bos://governance/omo/audit",
    arguments={"scope": "full"}
)
```



## Status honesty (default discovery)

- Agora **routing** excludes `status: unimplemented` always, and `deprecated` unless `AGORA_BOS_INCLUDE_DEPRECATED=1` (see `bos_registry.py`).
- `cockpit bos list` shows **routable** services by default.
- `cockpit bos list --all` includes non-routable YAML rows for operators debugging registrations (e.g. AGT placeholders).
- Never treat unimplemented URIs as live product APIs.

## Related

- Skills: `agent-onboarding`, `a2a-coordination`, `bos-contract-fix`
- SSOT: `projects/agora/etc/bos-services.yaml`
- Callchain: `docs/I0-AGORA-CALLCHAIN.md`
- Architecture: `ARCHITECTURE.md` section 4 (BOS domain routing)
- Cockpit: `uv run --project projects/cockpit cockpit bos --help`
