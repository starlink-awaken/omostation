# Phase 2 Provider Plane Evidence

> Date: 2026-05-30
> Scope: `P2-UNBLOCK-LITELLM-PROVIDER`, `P2-WS1-LITELLM-BASELINE`, `P2-WS2-AGENT-RUNTIME-ROUTE-SEAM`

## 1. Selected provider path

- **Provider registry source**: `cc-switch`
- **Selected app type**: `claude`
- **Selected provider**: `DeepSeek`
- **Selected base URL**: `https://api.deepseek.com/anthropic`
- **Selected runtime model**: `DeepSeek-V4-pro[1m]`
- **Safe snapshot**: `.omo/state/provider-plane.yaml`

## 2. LiteLLM readiness

- `/tmp/litellm_config.yaml` updated so local model `claude-3-5-sonnet` points to the selected `cc-switch` provider path.
- `litellm` Docker container restarted successfully.
- Local health summary after restart:
  - `healthy_count: 1`
  - `unhealthy_count: 1`
  - healthy model: `anthropic/DeepSeek-V4-pro[1m]`
  - remaining unhealthy model: `openai/gpt-4o` (still waiting for an OpenAI-compatible path)

## 3. Smoke evidence

- `GET http://127.0.0.1:4000/health` returned healthy endpoints.
- `POST http://127.0.0.1:4000/v1/chat/completions`
  - model: `claude-3-5-sonnet`
  - status: `200`
  - response shape: valid chat completion envelope with assistant reasoning payload

## 4. agentmesh route seam

- Runtime config updated: `projects/agentmesh/config/gateway.yaml`
- Package default config updated: `projects/agentmesh/packages/gateway/src/config/gateway.yaml`
- Result:
  - new provider: `litellm -> http://127.0.0.1:4000/v1`
  - `claude` route now prefers `litellm` first, then `openrouter`
  - no business-code edits required for the route switch

## 5. CodexBar quota monitoring baseline

- `CodexBar` retained as **quota monitor / observation plane**
- Current live baseline captured via `codexbar usage --provider openrouter --status --format json`
- Snapshot:
  - provider: `openrouter`
  - available: `true`
  - balance: `$26.72`
  - used_percent: `46.56%`

## 6. Phase 3 preparation outcome

- Provider plane now has a concrete split:
  - `cc-switch` = provider registry / runtime source-of-truth
  - `LiteLLM` = local unified proxy
  - `CodexBar` = quota monitoring / operator visibility
- This is sufficient to start Phase 3 foundation work on top of an already-running local route seam.
