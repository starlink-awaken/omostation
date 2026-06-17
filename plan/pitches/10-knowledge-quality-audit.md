# Pitch: Knowledge Quality Audit (Spine Scorer)

## 🎯 The Why (Problem & Opportunity)
The Memory Spine successfully aggregates knowledge across KOS, gbrain, and Vault. However, "reach" does not guarantee "reliability." Aggregated results may contain outdated facts, contradictory claims, or low-density noise. Returning unfiltered knowledge fragments to the LLM Gateway decreases reasoning accuracy and wastes context tokens.

## 🚧 The What (Solution Overview)
Introduce an inline `QualityScorer` interceptor within the Memory Spine's aggregation path.

1.  **Scoring Heuristics:** Implement heuristics (e.g., recency decay, source authority weights) to penalize stale or dubious results.
2.  **LLM-Assisted Fact Checking:** For critical queries, utilize a low-cost, high-speed LLM (e.g., `gpt-4o-mini` via the Compute Spine) to briefly evaluate the top-k retrieved snippets for contradiction against the core query.
3.  **Dynamic Filtering:** Automatically prune results falling below a dynamic confidence threshold before returning the aggregated payload to the caller.

## 📏 Boundaries & Appetites
-   **Appetite:** 1 Week (Medium complexity).
-   **No-Gos:** Do not block the primary retrieval path with slow, blocking LLM calls for every minor search. The scoring must be fast (primarily heuristic) with LLM usage strictly bounded by async timeouts.

## ⚠️ Rabbit Holes & Risks
-   **Latency Spikes:** The synchronous waiting for an LLM to score results can severely degrade the responsiveness of `bos://memory/local/all-search`. We must use `asyncio.wait_for` with aggressive timeouts.