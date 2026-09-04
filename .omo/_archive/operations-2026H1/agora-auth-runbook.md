---
lifecycle: entry
owner: agora-gateway
last_updated: 2026-08-24
related:
- ../../projects/agora/src/agora/server/mcp_entry.py
- ../../projects/agora/src/agora/server/tools_auth.py
- ../../docs/scene-cards/agora-bos-gateway.yaml
title: Agora Auth Runbook
type: doc
---

# Agora Auth Runbook

## Overview

Agora MCP gateway exposes HTTP/SSE endpoints for BOS URI routing. Two endpoints
require authentication:

| Endpoint | Risk | Auth Required |
|----------|------|---------------|
| `/v1/tools/call` | Medium — invokes MCP tools | Yes (Bearer token) |
| `/v1/backends/register` | **High** — spawns subprocesses | Yes (Bearer token) |

## Auth Modes

Controlled by `AGORA_AUTH_MODE` environment variable:

| Mode | Behavior | Use Case |
|------|----------|----------|
| `required` (default) | Fail-closed: missing `AGORA_API_KEY` rejects all requests | **Production** |
| `permissive` | Allow all without a key | Local development only |

## Production Deployment Checklist

**MUST** set both environment variables:

```bash
export AGORA_AUTH_MODE=required
export AGORA_API_KEY=<strong-random-key>
```

Generate a key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Why This Matters

`/v1/backends/register` accepts arbitrary `command` and `args` fields and spawns
subprocesses. In `permissive` mode, any network-reachable client can register a
backend that executes arbitrary code on the Agora host.

The endpoint has shell-metacharacter filtering (`;`, `|`, `&&`, `` ` ``, `$(`)
but this is a defense-in-depth measure, not a substitute for authentication.

## Verification

```bash
# Should return 401 (no key)
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:7431/v1/backends/register \
  -H "Content-Type: application/json" \
  -d '{"name":"test","command":"echo"}'

# Should return 200 (with key)
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:7431/v1/backends/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AGORA_API_KEY" \
  -d '{"name":"test","command":"echo"}'
```

## Scene Card Reference

This runbook addresses blocker `unauthorized_register_endpoint` from
`docs/scene-cards/agora-bos-gateway.yaml`. The code-level auth enforcement is
already in place (`mcp_entry.py` L90-147 + `tools_auth.py`). This document
ensures production deployments are configured correctly.
