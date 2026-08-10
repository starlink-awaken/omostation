# omlxc

`omlxc` is the operator-facing control plane for the local compute hub. Model
names, aliases, node policies, and fallback targets are owned by
[`conf/models.json`](conf/models.json); AetherForge provides the authenticated
OpenAI-compatible facade used by Workspace and Agora/BOS.

## Routing contract

Normal requests stay local and follow this order:

1. oMLX App on the MacBook Pro.
2. LM Link / LM Studio on reachable fleet nodes.
3. Ollama on reachable fleet nodes.

The MacBook Pro does not expose oMLX App directly to the tailnet. AetherForge owns
the authenticated loopback and Tailscale listeners. Cloud routing is opt-in at the
AetherForge request layer.

Thinking/reasoning is disabled by default with backend-specific request fields:
oMLX App uses `enable_thinking=false` and a zero thinking budget; LM Studio and
Ollama use `reasoning_effort=none`. Explicit caller fields remain authoritative.

## Daily operations

```bash
# Discover models and reconcile the flat projection consumed by oMLX App
omlxc app sync --apply

# Inspect App, fleet, and authenticated gateway state
omlxc app status
omlxc cluster
omlxc gw status

# Load/unload App models and exercise the complete facade
omlxc app load mythos-fast
omlxc app unload mythos-fast
omlxc gw test mythos-fast

# Benchmark an already loaded model with memory/OOM and thinking guards
omlxc bench mythos-fast --iterations 5

# Validate tools, model paths, and every configured fallback target
omlxc doctor
```

`omlxc bench` deliberately refuses to JIT-load an unloaded model. It samples the
oMLX process footprint and host memory pressure before every request, treats the
first request as warm-up, fails on retained post-warm-up growth, and rejects any
reasoning field or `<think>` output. Load one model at a time when comparing large
models, then unload it before moving to the next candidate.

The measured fleet/model baseline and placement recommendations live in
[`docs/model-audit-2026-08-10.md`](docs/model-audit-2026-08-10.md).

`omlxc up` reconciles the App projection and starts the AetherForge launch agent.
`omlxc down` stops the facade and legacy local processes without unloading the
oMLX App itself.

## SSOT and rollback

Run `omlxc ssot-sync --apply` to regenerate the eCOS MODEL-BREW projection after
changing logical models. Use `OMLXC_M1_MODEL_DIR` when generating into an isolated
eCOS worktree.

The old per-model `serve`/`stop` commands and ports remain only for explicit
rollback. AetherForge can temporarily select that path with
`AETHERFORGE_LOCAL_BACKEND=legacy`; the retired LiteLLM/autostart launch agents
must not be re-enabled as part of normal operation.
