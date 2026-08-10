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
Ollama use `reasoning_effort=none`. The tuned App profile also forces the chat
template flag off so a stray client cannot silently re-enable long reasoning.

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

# Preview the bounded App tuning profile (GET only, no settings changed)
omlxc tune

# Compare remote LM Studio/Ollama residency with remote_resident SSOT
omlxc fleet-tune

# Validate tools, model paths, and every configured fallback target
omlxc doctor
```

`omlxc bench` deliberately refuses to JIT-load an unloaded model. It samples the
oMLX process footprint and host memory pressure before every request, treats the
first request as warm-up, fails on retained post-warm-up growth, and rejects any
reasoning field or `<think>` output. Load one model at a time when comparing large
models, then unload it before moving to the next candidate.

## Safe App tuning

`omlxc tune` is preview-only. It compares the live App settings with a bounded
profile: balanced memory admission, two concurrent requests, embedding batch 16,
64 GB SSD cache, a 32K global context default, per-model context/sampling profiles,
30-60 minute idle TTLs, and thinking disabled. It never reads or backs up API
keys, proxy settings, network listeners, or launch settings.

Mutation requires an explicit acknowledgement and creates a mode-0600 backup
before the first write:

```bash
# Apply persistent settings; add --restart only when an immediate App restart is wanted
omlxc tune --apply --yes
omlxc tune --apply --yes --restart

# Restore exactly the fields owned by the earlier tune transaction
omlxc tune --rollback ~/omlx/backups/app-tune-YYYYMMDD-HHMMSS.json --yes
```

Global fields whose current value is `null` are intentionally not managed because
oMLX App 0.5.7 cannot reliably restore those values through its global settings
endpoint. Per-model `null` overrides are reversible and are included in backups.

## Remote fallback tuning

`omlxc fleet-tune` closes the gap between `autopilot.remote_resident` and the
actual LM Studio/Ollama processes. Preview probes LM Studio with read-only
`lms ps --json` over the configured SSH channel and probes Ollama over its HTTP
API. It reports context, parallelism, and total TTL drift for LM Studio, plus
finite/forever residency for Ollama.

Applying reloads only drifting, controllable targets and writes a private state
snapshot first. If any configured target is offline or lacks a working control
channel, the default is to reject the entire mutation:

```bash
# All configured remote targets must be controllable
omlxc fleet-tune --apply --yes

# Explicitly tune reachable targets while leaving offline nodes unchanged
omlxc fleet-tune --apply --yes --allow-partial
```

LM Studio is reloaded with the configured context length, parallel count, TTL,
and stable instance identifier. Ollama receives an empty non-streaming generate
request that only resets its `keep_alive`; it does not generate tokens. The
preview and confirmation gate are deliberately separate because reloading an LM
Studio instance briefly interrupts that fallback node.

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
