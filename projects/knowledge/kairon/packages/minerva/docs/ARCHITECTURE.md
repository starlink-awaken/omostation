---
title: ARCHITECTURE
type: doc
---

# Minerva Architecture v0.5.0

## Overview / 概述

Minerva is a local-first, tiered deep research system with 4 LLMs, 8 search backends, and 3 knowledge stores. All components degrade gracefully — no single point of failure.

### Tiered Dependency Model / 三级依赖模型

```
Layer 1 (Hard / 硬依赖): Must work. System fails without these.
  Ollama MLX · SQLite FTS5 · DDG Search · MCP Server

Layer 2 (Enhanced / 增强): Graceful degradation when missing.
  Neo4j 5 · DeepSeek V4 Pro · Metaso · Exa · spaCy · LanceDB

Layer 3 (Optional / 可选): Best-effort, no impact when absent.
  SearXNG · Brave · NotebookLM · graphify · Zhipu MCP
```

## System Layers / 系统分层

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT INTERFACE (MCP)                     │
│  research_now · schedule · watch · knowledge_search · ingest │
│             5 Super Tools via FastMCP stdio                   │
├─────────────────────────────────────────────────────────────┤
│                    EXECUTION ENGINE                          │
│  ResearchExecutor: Immediate Queue · APScheduler Cron        │
│  CostGuard (persistent JSONL ledger) · daemon (SIGTERM)     │
├─────────────────────────────────────────────────────────────┤
│                    TRIAGE ROUTER                             │
│  5-dim scoring → L0 | L1 | L2 | L3 | L4                     │
│  Rule-based (72%) + LLM fallback · classify_rule_based()     │
├─────────────────────────────────────────────────────────────┤
│                    PIPELINE ENGINE                           │
│  L0: Search → Output                                         │
│  L1: Decompose → Search → CrossAnalyze → Output              │
│  L2: +EntityExtract → DeepRead → QualityGate                 │
│  L3: +CounterArgument (cloud LLM)                            │
│  L4: +MultiModelVoting → ExtendedOutput                      │
├─────────────────────────────────────────────────────────────┤
│                    SEARCH LAYER                              │
│  8 backends parallel → RRF fusion → dedup → rank             │
│  DDG · Scholar · arXiv · Metaso · Exa · Brave · Zhipu · SearXNG│
├─────────────────────────────────────────────────────────────┤
│                    AI LAYER                                  │
│  Local: qwen3.6:27b (L0-L2) · spaCy en_lg + zh_sm (NER)     │
│  Cloud: V4 Pro 1M ctx (L3-L4) · GLM-4.7 Flash (DeepRead)    │
│         LongCat-Thinking (free 500万/day backup)             │
├─────────────────────────────────────────────────────────────┤
│                    KNOWLEDGE LAYER                           │
│  SQLite FTS5 · Neo4j 5 (Bolt) · LanceDB                      │
│  Allen 13 temporal relations · RuleEngine · KnowledgeIngester│
├─────────────────────────────────────────────────────────────┤
│                    MAINTENANCE LAYER                         │
│  Contradiction Detector · Staleness Checker · Gap Analyzer   │
├─────────────────────────────────────────────────────────────┤
│                    OUTPUT LAYER                              │
│  Bilingual EN+ZH · TL;DR summary · Quality Score (100-pt)    │
│  Source-based confidence · Rich terminal UX                  │
└─────────────────────────────────────────────────────────────┘
```

## Model Matrix / 模型矩阵

| Stage | Primary | Fallback | Context | Cost |
|-------|---------|----------|---------|------|
| L0-L2 Search/Extract | qwen3.6:27b (local) | qwen3.5:4b | 16K | $0 |
| L2 Decompose | qwen3.6:27b (local) | — | 16K | $0 |
| L2 DeepRead | DeepSeek V4 Pro | GLM-4.7 Flash | 1M / 128K | ~$0.01 |
| L3/L4 CrossAnalyze | DeepSeek V4 Pro | LongCat-Thinking | 1M / 256K | ~$0.03 |
| L3 CounterArgument | DeepSeek V4 Pro | LongCat-Thinking | 1M / 256K | ~$0.03 |
| L4 MultiModelVoting | DeepSeek V4 Pro | LongCat-Thinking | 1M / 256K | ~$0.05 |
| L0-L4 Output/Bilingual | qwen3.6:27b (local) | GLM-4.7 Flash | 16K / 128K | $0 |

## Search Backends / 搜索后端

| Backend | Type | Cost | Auth | Status |
|---------|------|------|------|--------|
| DDG | Web | Free | None | ✅ Active |
| Semantic Scholar | Academic | Free | None | ✅ Active |
| arXiv | Preprints | Free | None | ✅ Active |
| Metaso (秘塔) | Chinese AI | ~3 credits/search | API Key | ✅ Active |
| Exa | Semantic Web | 1000/mo free | API Key | ✅ Active |
| Brave | Web (35B pages) | 2000/mo free | API Key | ⚠️ GFW blocked |
| Zhipu (智谱) | Chinese Web | Free (MCP) | API Key | ✅ Active |
| SearXNG | Meta-search | Free (self-host) | None | ⚠️ Engine blocked |

## Data Flow / 数据流

```
Query → TriageRouter.classify()
    ↓
    ├─ Rule-based: 5-dim scoring → L0-L4
    └─ LLM fallback: qwen3.6:35b-a3b (if rule fails)
    ↓
Pipeline.run(query, level)
    ↓
    ├─ DecomposeStage: LLM sub-question generation
    ├─ SearchStage: asyncio.gather(8 backends) → RRF fusion
    ├─ EntityExtractStage: spaCy NER (en+zh routing)
    ├─ DeepReadStage: Content extraction (Jina→BS4→raw)
    │                   Cross-source analysis (V4 Pro 1M ctx)
    ├─ CrossAnalyzeStage: Contradiction/consensus detection
    ├─ CounterArgumentStage: Devil's advocate (L3+, cloud LLM)
    ├─ MultiModelVotingStage: Panel review (L4, cloud LLM)
    ├─ QualityGateStage: 100-pt quality scoring
    └─ OutputStage: Bilingual report + Neo4j persistence
    ↓
Report → ~/knowledge/reports/{timestamp}_{slug}_EN.md
       → ~/knowledge/reports/{timestamp}_{slug}_ZH.md
       → Neo4j entities/relations
```

## Knowledge Persistence / 知识持久化

```
Research Output
    ├─ Markdown reports → ~/knowledge/reports/ (Git-tracked)
    ├─ Entities/Relations → Neo4j 5 (GraphBridge)
    ├─ Full-text index → SQLite FTS5
    ├─ Vector embeddings → LanceDB
    ├─ Temporal validity → Allen 13 relations
    └─ Rule validation → RuleEngine (3 default rules)
```

## Graceful Degradation / 优雅降级

| If This Fails... | System Falls Back To... |
|-----------------|------------------------|
| Neo4j | SQLite (RECURSIVE CTE for graph queries) |
| DeepSeek V4 Pro | LongCat → GLM-4.7 Flash → local qwen3.6:27b |
| spaCy model | Skip entity extraction (non-blocking) |
| Any search backend | Other 7 backends continue in parallel |
| DDG (library fails) | Other backends still produce results |
| MCP server executor | Clear RuntimeError with init guidance |
| CostGuard ledger file | Start from $0 (graceful, not data loss) |

## Project Metrics / 项目指标

| Metric | Value |
|--------|-------|
| Python Version | 3.14+ |
| Lines of Code | ~5,700 |
| Source Files | 34 (8 subpackages) |
| Test Files | 17 |
| Test Count | 137 (all passing) |
| Commits | 45 |
| Search Backends | 8 |
| LLM Models | 4 (1 local + 3 cloud) |
| Pipeline Stages | 9 implementations |
| MCP Tools | 5 Super Tools |
| Docker Services | Neo4j 5 + SearXNG |
| ISC Completion | 137/200 (68.5%) |
| Maturity | 92% (production-ready prototype) |
