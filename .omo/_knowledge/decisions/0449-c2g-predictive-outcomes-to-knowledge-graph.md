---
id: ADR-0449
status: ACCEPTED
lifecycle: spec
owner: governance-agent
last_updated: 2026-08-02
---

# ADR-0296: C2G Predictive Outcomes to Knowledge Graph Pipeline (Wave 2 Phase C)

> **Status**: ACCEPTED  
> **Date**: 2026-08-02  
> **Authors**: Xiamingxing, Antigravity AI  
> **Context**: P1-1 C2G outcome and predictive reporting integration with P0 KnowledgeIndexer  
> **References**: ADR-0183 (Wave 2 Phase A), ADR-0185 (Wave 2 Phase B), ADR-0294 (Knowledge Gateway Decoupling)

## 1. Context & Problem Statement

In **Wave 2 Phase A (ADR-0183)** and **Phase B (ADR-0185)**, the `c2g` engine introduced `OutcomeTracker` for backtesting pitch completion metrics and `PredictiveModel` for time-series forecasting and risk heatmaps.

However, these strategic insights were isolated within YAML runtime files (`runtime/c2g/outcomes/pitch-outcomes.yaml`) and terminal CLI JSON outputs. They were not searchable in the **Knowledge Graph (KOS)** or LanceDB vector storage. Consequently, agents (such as `@Sage` or `cockpit iterate`) could not query historical project success scores, lessons learned, or predictive risk heatmaps through natural language or Cypher queries during governance and architectural deliberation.

## 2. Decision

We establish **Wave 2 Phase C**: an automated, decoupled **C2G-to-Knowledge-Graph Pipeline** that bridges `c2g` with the P0 `KnowledgeIndexer` (ADR-0294) without violating layer dependencies (since `c2g` is a zero-dependency leaf/horizontal framework layer).

### 2.1 Architectural Boundaries & Decoupling
- **No Reverse Dependency**: `c2g` MUST NOT import `cockpit`, `agora`, or `kairon` modules directly.
- **Protocol Port**: All communication is executed over standardized network requests to Agora `/v1/tools/call` (`publish_event` MCP tool) emitting `bos://brain/events/card_updated` or via HTTP `/api/knowledge/put` if available.
- **Graceful Offline Fallback**: When network endpoints are unreachable or in unit/offline test environments, the publisher degrades silently with structured logging, ensuring zero disruption to upstream C2G calculations.

### 2.2 New Module: `c2g.knowledge_publisher`
We introduce `projects/c2g/src/c2g/knowledge_publisher.py` with two core capabilities:
1. `publish_outcome_card(pitch_id, outcome_data, ...)`: Converts historical pitch performance (success score, completed vs. failed tasks, lessons learned) into structured Markdown cards tagged with `#c2g #outcome #backtest`.
2. `publish_predictive_card(report_data, ...)`: Converts time-series forecasts and Markdown risk heatmaps into high-level strategic governance cards tagged with `#c2g #predictive #risk`.

### 2.3 CLI Integration
We extend `c2g.predictive_report` CLI (`python -m c2g.predictive_report --publish-knowledge`) to support one-click or automated CI/CD publishing of predictive governance cards to KOS.

## 3. Consequences

### Positive
- **Closed-Loop Intelligence**: Strategic pitch outcomes and future risk heatmaps are continuously indexed by `KnowledgeIndexer` (ADR-0294) and stored in KOS/LanceDB.
- **Semantic & Cypher Searchable**: Strategic advisors and users can query historical ROI and risk heatmaps across past pitches.
- **Layer Compliance**: Zero reverse imports; standard network-first / fallback architecture.

### Negative / Mitigations
- **Network Overhead**: Minor HTTP request overhead when publishing cards; mitigated by asynchronous or non-blocking network calls with short timeouts (1.5s).
