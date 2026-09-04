---
title: README
type: doc
---

# Minerva — Local-First Deep Research System

> *Minerva: Roman goddess of wisdom, strategic warfare, and the arts.*
>
> A local-first, multi-tier deep research system that searches 8 sources, analyzes with 4 LLMs, verifies claims against sources, persists knowledge in Neo4j + SQLite + LanceDB, and produces bilingual reports with quality scoring. Powered by **Sophia** symbolic paradigm engine. Runs on Apple Silicon with $0/month base cost. **v0.11.0**

[English](#english) | [中文](#chinese)

---

## English

### What is Minerva?

Minerva is a local deep research engine. You ask a question, it searches across 8 backends in parallel, extracts entities, analyzes contradictions, scores quality, and generates a bilingual (EN+ZH) report — all running on your machine with zero cloud dependency for basic tiers.

**New in v0.11.0:** Web API with SSE streaming, PDF report export, Sophia paradigm engine integration, circuit breaker for LLM resilience, RAG pipeline with LanceDB+SQLite hybrid retrieval, API key authentication, rate limiting, 3 research templates, CI/CD pipeline, and enterprise governance docs.

### Quick Start

```bash
# Install
pip install -e .

# First-time setup wizard
minerva init

# Research a topic (L0: 30s, free)
minerva research "What is a transformer architecture?" --level L0

# Use a research template
minerva research --template competitor-analysis --target "Apple Vision Pro"

# Deep research with citations (L2: ~2min)
minerva research "MoE model production practices" --level L2

# Enterprise reasoning with counter-arguments (L3: ~8min)
minerva research "AI existential risk: both sides" --level L3

# Start Web API (FastAPI + Swagger UI at /docs)
minerva web

# Start MCP server for Claude Code integration
minerva mcp

# Knowledge maintenance
minerva maintenance
```

### Web API

```bash
minerva web  # Starts at http://localhost:8765
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with component status |
| `/api/research` | POST | Start async research, returns `task_id` |
| `/api/research/{task_id}` | GET | Poll research status and results |
| `/api/report` | GET | Rendered HTML report |
| `/api/report/pdf` | GET | A4 PDF export |
| `/api/stream` | GET | SSE real-time progress stream |
| `/api/paradigm` | GET | Current paradigm operations |
| `/api/progress` | GET | Pipeline stage progress |
| `/docs` | GET | Swagger UI (OpenAPI) |

### Pipeline Levels

| Level | Time | Cost | What It Does |
|-------|------|------|-------------|
| **L0** Quick | <30s | $0 | Single-round search, 5 sources, QualityGate |
| **L1** Standard | <3min | $0 | Decompose→Search→Cross-analyze |
| **L2** Deep | ~2min | ~$0.30 | Entity extraction, DeepRead, contradiction analysis |
| **L3** Comprehensive | ~8min | ~$0.50 | Counter-argument generation, StepVerifier + GlobalVerifier |
| **L4** Max | ~15min | ~$2 | Multi-model voting, extended report, full verification |

### Research Paradigms

Minerva uses the **Sophia** symbolic paradigm engine to dynamically compose research operations:

| Paradigm | States | Operations | Best For |
|----------|--------|------------|----------|
| Scientific Inquiry | 8 | 6 | Hypothesis-driven research |
| Comparative Analysis | 6 | 5 | Side-by-side comparisons |
| Problem Solving | 7 | 5 | Root-cause analysis |
| Literature Review | 5 | 4 | Survey papers, state-of-art |
| Policy Analysis | 6 | 5 | Regulatory and policy review |

### Research Templates

```bash
minerva research --template competitor-analysis --target "Company X"
minerva research --template literature-review --target "Topic Y"
minerva research --template policy-audit --target "Policy Z"
```

### System Architecture

```
User Input → TriageRouter (L0-L4) → Pipeline (10 stages)
                                        │
         ┌──────────────────────────────┼──────────────────────────────┐
         │                              │                              │
    Search Layer                   AI Layer                    Knowledge Layer
   ┌─────────────┐            ┌─────────────┐               ┌─────────────┐
   │ DDG (free)  │            │ Ollama Local │              │ SQLite FTS5 │
   │ Scholar(free)│           │ DeepSeek V4  │              │ Neo4j 5     │
   │ arXiv (free) │           │ LongCat(free)│              │ LanceDB     │
   │ Metaso(paid) │           │ GLM-4.7 Flash│              │ Allen Temporal│
   │ Exa (free)   │           │              │              │ RuleEngine  │
   │ Brave (free) │           │ CircuitBreaker│              │ RAG Pipeline│
   │ Zhipu (free) │           │ StepVerifier │              │ GraphBridge │
   │ SearXNG(opt) │           │ GlobalVerifier│             └─────────────┘
   └─────────────┘            └─────────────┘                    │
         │                              │                        │
         └──────────────────────────────┴────────────────────────┘
                                        │
                                   Output Layer
                              ┌─────────────────┐
                              │ EN+ZH Report     │
                              │ TL;DR Summary    │
                              │ Quality Score    │
                              │ Source Confidence│
                              │ Paradigm Info    │
                              │ Web Dashboard    │
                              │ PDF Export       │
                              │ SSE Streaming    │
                              │ MCP 8 Tools      │
                              └─────────────────┘
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Local LLM | Ollama MLX (qwen3.6:27b) |
| Cloud LLM | DeepSeek V4 Pro · LongCat · GLM-4.7 Flash |
| NLP | spaCy en_core_web_lg + zh_core_web_sm |
| Search | DDG · Semantic Scholar · arXiv · Metaso · Exa · Brave · Zhipu · SearXNG |
| Knowledge Graph | Neo4j 5 Community · GraphBridge |
| Vector DB | LanceDB |
| Full-text | SQLite FTS5 |
| Paradigm Engine | Sophia (symbolic state machine) |
| Web Framework | FastAPI + Jinja2 + htmx |
| Agent Integration | MCP (8 tools) |
| Temporal | Allen 13 interval relations |
| Terminal UX | Rich (banners, progress bars, TUI) |
| Infrastructure | Docker Compose (Neo4j + SearXNG) |
| CI/CD | GitHub Actions (Python 3.11-3.13) |
| Linting | ruff + pre-commit hooks |
| Security | gitleaks secret scanning |

### Configuration

```bash
# Required env vars (add to ~/.zshrc or .env)
export DEEPSEEK_API_KEY="sk-..."        # V4 Pro (primary reasoning)
export LONGCAT_API_KEY="ak-..."          # Backup reasoning (free 5M/day)
export GLM_API_KEY="..."                 # DeepRead fallback (free)

# Optional
export MINERVA_API_KEY="..."             # Enable Web API auth
export METASO_API_KEY="mk-..."           # Chinese search
export EXA_API_KEY="..."                 # Semantic search
export BRAVE_API_KEY="BSA..."            # Brave search
export ZHIPU_API_KEY="..."               # Zhipu search
```

### vs Commercial Products

| Feature | Minerva | ChatGPT DR | Gemini DR | Perplexity |
|---------|---------|-----------|-----------|------------|
| Monthly cost | **$0-5** | $200 | $20 | $20 |
| Search sources | **8** | 1 | 1 | 1 |
| Privacy | **100% local** | Cloud | Cloud | Cloud |
| Knowledge persistence | **Neo4j + SQLite + LanceDB** | None | None | None |
| Chinese native | **Yes** | Translated | Translated | Translated |
| Programmable (MCP) | **Yes (8 tools)** | No | No | API |
| Bilingual reports | **EN+ZH** | EN only | EN only | EN only |
| Report quality score | **Yes** | No | No | No |
| Symbolic paradigms | **Yes (Sophia)** | No | No | No |
| Web API + SSE | **Yes** | No | No | No |
| RAG pipeline | **Yes** | Partial | Partial | Partial |

### Project Status

| Metric | Value |
|--------|-------|
| Version | **0.10.0** |
| Tests | 238 (all passing) |
| Source lines | ~8,500 |
| Source files | 42 |
| Test files | 21 |
| Maturity | Production-ready Beta |

---

## 中文

### Minerva 是什么？

Minerva 是一个本地深度研究引擎。你提出问题，它并行搜索 8 个信息源，通过 spaCy 提取实体，分析矛盾，评分质量，生成中英双语报告——基础级别完全在本地运行，零云依赖。

**v0.11.0 新特性：** Web API（SSE 流式推送）、PDF 报告导出、Sophia 符号范式引擎集成、LLM 断路器、RAG 管道（LanceDB + SQLite 混合检索）、API 密钥认证、速率限制、3 个研究模板、CI/CD 管道、企业级治理文档。

### 快速开始

```bash
# 安装
pip install -e .

# 首次设置向导
minerva init

# 快速查定义 (L0: 30秒, 免费)
minerva research "什么是 transformer 架构" --level L0

# 使用研究模板
minerva research --template competitor-analysis --target "Apple Vision Pro"

# 深度调研 (L2: ~2分钟)
minerva research "MoE 模型在生产环境的最新实践" --level L2

# 企业推理 + 对立论证 (L3: ~8分钟)
minerva research "AI existential risk: both sides" --level L3

# 启动 Web API
minerva web

# 启动 MCP 服务器
minerva mcp

# 知识库维护
minerva maintenance
```

### Web API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查及组件状态 |
| `/api/research` | POST | 启动异步研究，返回 `task_id` |
| `/api/research/{task_id}` | GET | 轮询研究状态和结果 |
| `/api/report` | GET | 渲染后的 HTML 报告 |
| `/api/report/pdf` | GET | A4 PDF 导出 |
| `/api/stream` | GET | SSE 实时进度流 |
| `/api/paradigm` | GET | 当前范式操作信息 |
| `/api/progress` | GET | 管道阶段进度 |
| `/docs` | GET | Swagger UI 交互文档 |

### 研究范式

Minerva 使用 **Sophia** 符号范式引擎动态组合研究操作：

| 范式 | 状态数 | 操作数 | 适用场景 |
|------|--------|--------|----------|
| 科学探究 | 8 | 6 | 假设驱动的研究 |
| 比较分析 | 6 | 5 | 横向对比 |
| 问题解决 | 7 | 5 | 根因分析 |
| 文献综述 | 5 | 4 | 综述论文、现状调研 |
| 政策分析 | 6 | 5 | 法规与政策审查 |

### 管道级别

| 级别 | 时间 | 成本 | 做什么 |
|------|------|------|--------|
| **L0** 快速 | <30s | $0 | 单轮搜索，5 个来源，质量评分 |
| **L1** 标准 | <3min | $0 | 子问题分解，交叉分析 |
| **L2** 深度 | ~2min | ~$0.30 | 实体提取，内容分析，矛盾检测 |
| **L3** 全面 | ~8min | ~$0.50 | 对立论证生成，双重验证 |
| **L4** 极致 | ~15min | ~$2 | 多模型投票，扩展报告 |

### 与商业产品对比

| 特性 | Minerva | ChatGPT DR | Gemini DR | Perplexity |
|------|---------|-----------|-----------|------------|
| 月成本 | **$0-5** | $200 | $20 | $20 |
| 搜索源 | **8 个** | 1 个 | 1 个 | 1 个 |
| 隐私 | **100% 本地** | 云端 | 云端 | 云端 |
| 知识持久化 | **Neo4j + SQLite + LanceDB** | 无 | 无 | 无 |
| 中文原生 | **是** | 翻译 | 翻译 | 翻译 |
| 可编程 (MCP) | **是 (8 tools)** | 否 | 否 | API |
| 双语报告 | **中英双版** | 仅英文 | 仅英文 | 仅英文 |
| 符号范式 | **是 (Sophia)** | 否 | 否 | 否 |
| Web API + SSE | **是** | 否 | 否 | 否 |
| RAG 管道 | **是** | 部分 | 部分 | 部分 |

### 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 本地 LLM | Ollama MLX (qwen3.6:27b) |
| 云 LLM | DeepSeek V4 Pro · LongCat · GLM-4.7 Flash |
| NLP | spaCy en_core_web_lg + zh_core_web_sm |
| 搜索 | DDG · Scholar · arXiv · 秘塔 · Exa · Brave · 智谱 · SearXNG |
| 知识图谱 | Neo4j 5 · GraphBridge |
| 向量数据库 | LanceDB |
| 全文检索 | SQLite FTS5 |
| 范式引擎 | Sophia（符号状态机） |
| Web 框架 | FastAPI + Jinja2 + htmx |
| Agent 集成 | MCP（8 个工具） |
| 时态推理 | Allen 13 区间关系 |
| 终端界面 | Rich |
| 基础设施 | Docker Compose (Neo4j + SearXNG) |
| CI/CD | GitHub Actions (Python 3.11-3.13) |
| 代码检查 | ruff + pre-commit hooks |
| 安全扫描 | gitleaks |

### 项目状态

| 指标 | 数值 |
|------|------|
| 版本 | **0.10.0** |
| 测试数 | 238 (全部通过) |
| 代码行数 | ~8,500 |
| 源文件数 | 42 |
| 测试文件数 | 21 |
| 成熟度 | 生产就绪 Beta |

### 许可证

MIT

### 相关项目

- [Sophia](https://github.com/minerva/sophia) — 符号化研究范式引擎
- [Agora](https://github.com/minerva/agora) — MCP 服务收敛中心
