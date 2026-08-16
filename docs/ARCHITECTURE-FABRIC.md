# 🌐 omlxc Compute Fabric & Data Plane Architecture

## 1. Executive Summary

`omlxc` is a private, multi-node, heterogeneous LLM compute fabric designed for local multi-agent ecosystems (AetherForge, OMO Swarm, OpenCode). It acts as an **adaptive L4/L7 Compute Gateway and Mesh Scheduler**, abstracting unified memory nodes (Apple Silicon MBP M5 Max, Mac mini M4) and CUDA accelerators (Y7000P RTX 4070) into an elastic, resilient compute grid.

---

## 2. Core Architectural Pillars

```
+-------------------------------------------------------------------------------+
|                             Client / Agent Layer                              |
|          AetherForge Swarm  |  OMO Agent Mesh  |  OpenCode / Kilo / Human     |
+-------------------------------------------------------------------------------+
                                      │ (OpenAI-Compatible / Typed Socket)
                                      ▼
+-------------------------------------------------------------------------------+
|                      omlxc v3.4.0 Compute Fabric Core                         |
|                                                                               |
|  [Priority QoS & WFQ]           [Semantic Intent Triage]                      |
|  - P0: Interactive (Headroom)    - FAST: 2B~4B micro-latency (lookup/typo)    |
|  - P1: Autonomous Agent          - STANDARD: 9B~14B daily code generation     |
|  - P2: Background Batch          - REASONING: 27B~70B deep thinking / proofs  |
|                                                                               |
|  [Two-Tier Cache Mesh]          [VRAM Budget & Pre-Emption]                   |
|  - L1: 0ms Exact Prefix-Hash     - Model base weights + Dynamic KV Cache MB   |
|  - L2: <5ms Semantic Invariant   - Pre-emptive headroom admission (>85% block)|
|                                                                               |
|  [Thermal & Battery Guard]       [Dynamic Resilience & Affinity]              |
|  - Local macOS pmset telemetry   - Dual-mode session sticky affinity (1.35x)  |
|  - Remote Tailscale sync         - In-flight concurrency load-shedding        |
|  - 0.5x~0.1x throttle penalty   - 3-state circuit breaker + emergency probe  |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
+-------------------------------------------------------------------------------+
|                         Physical Heterogeneous Cluster                        |
|                                                                               |
|  💻 MBP M5 Max 128G         🖥️ Mac mini M4 24G         🎮 Y7000P RTX 4070 8G  |
|  (qwen-27b / deepseek-70b)  (gemma-4b / qwen-9b)       (local embedding)      |
+-------------------------------------------------------------------------------+
```

---

## 3. Mathematical Scoring & Routing Formula

When an inference request arrives, the `RoutePlanner` computes a placement score for each candidate model placement $p$:

$$\text{FinalScore}(p) = \text{BaseScore}(p) \times M_{\text{affinity}}(p) \times M_{\text{concurrency}}(p) \times M_{\text{thermal}}(p) \times M_{\text{priority}}(p)$$

Where:
- $\text{BaseScore}(p) = \text{EWMA}(\text{TPS}) \times w_{\text{tps}} - \text{EWMA}(\text{TTFT}) \times w_{\text{ttft}} - \text{NetworkCost}$.
- $M_{\text{affinity}}(p) = 1.35$ (if session matched) or $1.15$ (if prefix hash matched).
- $M_{\text{concurrency}}(p) = \frac{1}{1 + 0.5 \times N_{\text{in\_flight}}}$.
- $M_{\text{thermal}}(p) = 1.0$ (Nominal), $0.5$ (Heavy / Battery Low), $0.1$ (Trapping).
- $M_{\text{priority}}(p) = 1.25$ (P0 Interactive), $1.0 / 0.7$ (P1 Autonomous), $0.9 / 0.6 / 0.1$ (P2 Batch).

---

## 4. CLI Governance Reference

| Command | Output | Description |
| :--- | :--- | :--- |
| `omlxc fabric inspect` | Rich / JSON | Cluster thermal pressure, triage capability, registered architectures, cache hit rates |
| `omlxc fabric triage "<prompt>"` | Rich / JSON | Zero-latency AST complexity classification (`FAST` / `STANDARD` / `REASONING`) |
| `omlxc fabric vram <model> <tokens>` | Rich / JSON | Pre-emptive KV Cache memory footprint, headroom admission & compaction advisory |
| `omlxc fabric warm [--model <name>]` | Rich / JSON | Pre-warm high-frequency system prompt prefixes into cache registry (0ms TTFT) |
| `omlxc routes plan <model>` | Rich / JSON | Explain exact multi-factor scoring formula for any model request |
| `omlxc doctor` | Rich / CLI | Verify database, launchd daemon, config, and node socket reachability |

---

## 5. Resilient Context Compaction & Sliding Windows

When a continuous multi-turn autonomous Agent session expands toward hardware memory limits:
1. `VRAMBudgetEstimator.check_headroom_admission` detects safe threshold breaches ($>85\%$ headroom).
2. It returns `compaction_advised=True`, `max_safe_tokens`, and `recommended_compaction_ratio`.
3. The upstream gateway or Agent invokes `bos://memory/mos/consolidate` or slides historical context into structural memory entities, ensuring long-running agents never crash from OOM.
