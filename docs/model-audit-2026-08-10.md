# Local Compute Hub Model Audit — 2026-08-10

This audit records the measured baseline for the MacBook Pro oMLX App and the
recommended placement across the three-node tailnet. It separates models suitable
for default routing from experimental/custom conversions so AetherForge can make
predictable memory and quality decisions.

## Measured oMLX App baseline

Measurements used `omlxc bench` with thinking disabled. Each large model was
loaded alone alongside the resident `mythos-fast`, then unloaded. The oMLX process
returned to about 4.7 GB after every unload; no retained post-warm-up growth was
observed.

| Logical model | Role | Loaded footprint | Warm throughput | Result |
|---|---|---:|---:|---|
| `mythos-fast` | always-on fast/creative | ~4.7 GB | 92.2 tok/s | pass |
| `coding` (Devstral Small 2 24B) | balanced coding | ~28 GB total | 20.6 tok/s | pass |
| `coding-fast` (custom Qwopus/Holo MoE) | experimental fast coding | ~32 GB total | 51.3 tok/s | pass |
| `coding-next` (Qwen3-Coder-Next 5-bit) | high-precision agentic coding | ~56 GB total | 73.4 tok/s | pass |
| `reasoning` (GLM-4.7-Flash 8-bit) | planning/reasoning | ~35 GB total | 66.7 tok/s | pass |
| `embedding` (Qwen3-Embedding-8B) | quality retrieval | ~12 GB total | 380–396 input tok/s warm | pass |

The `size_gb` values in `conf/models.json` are ceilings derived from the actual
dereferenced model directories, not the nominal parameter count. They are used for
admission control and intentionally round upward.

## Default routing tiers

1. **Fast resident:** `mythos-fast`. Keep it for triage, summarisation, creative
   drafting, and liveness checks. It is a custom conversion, so it must not be the
   sole authority for coding or governance decisions.
2. **Balanced coder:** `coding` / Devstral Small 2. Its measured throughput is lower
   than the MoE models, but the official model is explicitly tuned for software
   engineering agents and has predictable 24B memory behaviour.
3. **Precision coder:** `coding-next` / Qwen3-Coder-Next. Use for repository-scale
   changes and tool-using agents. It is non-thinking by design and showed the best
   measured quality/throughput trade-off that fits comfortably in 128 GB unified
   memory.
4. **Reasoner:** `reasoning` / GLM-4.7-Flash. Use for complex planning and difficult
   diagnosis. Thinking output stays disabled at the gateway even though the model
   supports reasoning modes.
5. **General/multimodal:** `mid-local` / Qwen3.6-27B and `vision` / Qwen3-VL-8B.
   Prefer these official families over custom blends when reproducibility matters.
6. **Retrieval:** `embedding` for highest local retrieval quality; `embed-bge-m3`
   for a much smaller multilingual fallback; BGE reranker v2 M3 for second-stage
   ranking.

`mistral-medium-128b` is a 74 GB on-disk model and must remain on-demand. Never
co-reside it with `coding-next` or another large model. `coding-fast` passed the
runtime/memory probe but remains experimental because it is a custom blend; it
still needs task-level coding evals before becoming the default. `coder-precise`,
Ornith, Qwythos, and third-party DeepSeek conversions remain experimental until
each passes the same memory-guarded benchmark and task evals.

## Node placement

| Node | Primary workload | Runtime policy |
|---|---|---|
| MBP M5 Max / 128 GB | oMLX App; all quality/large models | one large model at a time; `mythos-fast` may remain resident; LM Studio then Ollama fallback |
| Mac mini M4 Pro / 24 GB | LM Studio Link fast/general and vision fallback | Gemma 4 E4B, 16K context, parallelism 1, one-hour TTL/auto-evict; Ollama fallback |
| Lenovo Y7000P / RTX 4070 8 GB | CUDA small-model worker | 7–9B Q4, 8K context, parallelism 1, flash attention; currently excluded until LM Link/API health is restored |

The Y7000P is visible in Tailscale but neither LM Studio nor Ollama is reachable
and it is absent from the current LM Link peer list. AetherForge must treat it as
unavailable rather than route requests optimistically.

## Runtime settings

- Disable thinking at all layers: oMLX chat-template `enable_thinking=false` and
  zero budget; LM Studio `reasoning: off`; Ollama `think: false`.
- Prefer dynamic oMLX memory admission over a fixed 100 GB ceiling so other apps
  can reclaim unified memory. Keep the prefill memory guard enabled.
- Use concurrency 2 only for small/resident models; admission control must serialize
  large-model loads. Keep chunked prefill disabled on oMLX 0.5.7 and reevaluate
  after the long-context/cache fixes reach a stable release.
- Cap normal context at 32K and output at 8K. Raise context per request only when
  the task justifies the KV-cache cost.
- Keep SSD KV cache bounded (recommended 64 GB); stale signatures should be removed
  only during an explicit maintenance window.

## Primary references

- [oMLX releases](https://github.com/jundot/omlx/releases)
- [oMLX README](https://github.com/jundot/omlx/blob/main/README.md)
- [LM Studio per-model defaults](https://lmstudio.ai/docs/app/advanced/per-model)
- [LM Studio TTL and auto-evict](https://lmstudio.ai/docs/developer/core/ttl-and-auto-evict)
- [LM Studio reasoning control](https://lmstudio.ai/docs/developer/rest/chat)
- [Ollama thinking control](https://docs.ollama.com/capabilities/thinking)
- [Qwen3-Coder-Next model card](https://huggingface.co/Qwen/Qwen3-Coder-Next)
- [Devstral Small 2 model card](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512)
- [GLM-4.7-Flash model card](https://huggingface.co/zai-org/GLM-4.7-Flash)
- [Qwen3.6-27B model card](https://huggingface.co/Qwen/Qwen3.6-27B)
- [Qwen3-VL-8B model card](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct)
- [BGE-M3 model card](https://huggingface.co/BAAI/bge-m3)
- [BGE reranker v2 M3 model card](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [Gemma 4 E4B model card](https://huggingface.co/google/gemma-4-E4B)
