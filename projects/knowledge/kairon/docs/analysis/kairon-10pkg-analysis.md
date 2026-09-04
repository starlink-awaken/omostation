---
title: kairon-10pkg-analysis
type: doc
---

# Kairon 10-Package深度分析报告 (gc-engine → minerva)

> 生成时间: 2026-06-03
> 工作路径: ~/Workspace/projects/kairon/packages/

---

## 1. gc-engine (v0.1.0)

**身份**: GC Engine — 垃圾回收、内存排泄、蒸馏引擎  
**规模**: 7个源文件 / 1,395 LOC / 2个测试文件  
**架构**:
- 模块: `gc_core`, `lifecycle`, `retention`, `excretion`, `distillation`, `archiver`
- 入口: `from gc_engine import GCEngine, MemoryExcretionPipeline, DistillationEngine, RetentionPolicy, LifecycleManager`
- 关键类: `GCEngine`, `GCStats`, `LifecycleManager`, `RetentionPolicy`, `MemoryExcretionPipeline`, `DistillationEngine`, `ArchiveManager`, `TieredStorage`
- 纯内存操作，无外部依赖，纯 stdlib

**依赖**: 声明 `dependencies = []` ✓ 实际只用到 stdlib ✓ 零依赖  
**测试**: 2个测试文件 (test_gc_engine.py), unittest风格。覆盖 GC标记/清理/蒸馏/排泄/生命周期。无外部调用，全mock-free  
**健康**: 🟡 存在 — 功能完整但无消费者。Alpha状态  
**集成**: 不依赖任何内部包，也不被任何包依赖  
**债务**: 无 TODO/FIXME，代码干净。零依赖设计优雅但无实际使用场景

---

## 2. iris (v0.1.0)

**身份**: 连接器枢纽 — 个人知识平台的连通器 (备忘录/飞书/钉钉/GitHub等)  
**规模**: 46个源文件 / 8,236 LOC / 10个测试文件  
**架构**:
- 模块: `connectors/`(10+连接器), `sync/`(同步引擎), `adapters/`(eidos/ssot适配), `cli.py`, `mcp_server.py`, `registry.py`, `store.py`, `models.py`
- 入口: `iris.cli:main`, `iris.mcp_server:main`
- 连接器: AppleNotes, DingTalk, Feishu, GitHub, OpenHuman, Pocket, Polar, RSS, WeChat, 本地文件, Obsidian, Telegram, NotebookLM, WPS, 知乎, 微信读书
- 关键类: `Registry`, `SyncEngine`, `Config`, `Keychain`, `Store`

**依赖**:
- 声明: `httpx`, `pyyaml`, `pydantic`, `fastmcp`
- 实际import: `httpx` ✓, `fastmcp` ✓, **`pydantic` ✗**, **`pyyaml` ✗**
- 差距: `pydantic` 和 `pyyaml` 是**僵尸依赖** — 声明但不使用

**测试**: 10个文件，pytest风格。覆盖: 适配器、CLI、配置、连接器、模型、注册表、同步。mock httpx  
**健康**: 🟢 成熟 — 连接器生态丰富，代码量大。唯一可能的问题是部分连接器未充分测试  
**集成**: 不依赖内部包，依赖 `ssot-kernel`(optional)，不被其他包依赖  
**债务**: 无TODO/FIXME。2个僵尸依赖 (pydantic, pyyaml)

---

## 3. kairon-assistant (v1.0.0)

**身份**: 智能助手 — 命令解析、上下文管理、会话管理，提取自 SharedBrain D_Intelligence  
**规模**: 9个源文件 / 1,768 LOC / 3个测试文件  
**架构**:
- 模块: `core.py`, `command_parser.py`, `context_manager.py`, `session_manager.py`, `types.py`, `governance_integration.py`, `recommendation_engine.py`, `system_handlers.py`
- 入口: `from kairon_assistant import AssistantSession, CommandParser, ContextManager, SessionManager`
- 关键类: `AssistantSession`, `SessionManager`, `CommandParser`, `ContextManager`, `ConversationContext`, `RecommendationEngine`, `GovernanceIntegration`

**依赖**: 声明 `dependencies = []` ✓ 实际只用到 stdlib ✓  
**测试**: 3个文件，pytest风格。测试命令解析、上下文管理、推荐引擎、会话生命周期  
**健康**: 🟢 成熟 — 功能完整，代码清晰，设计良好。v1.0.0  
**集成**: 不依赖内部包，也不被其他包依赖  
**债务**: 无TODO/FIXME。干净代码

---

## 4. kairon-voice (v1.0.0)

**身份**: 语音子系统 — STT/TTS接口与多Provider适配器，提取自 SharedBrain D_Voice  
**规模**: 8个源文件 / 1,860 LOC / 2个测试文件  
**架构**:
- 模块: `interfaces/`(基类), `stt/`(Whisper适配), `tts.py`, `voice_recognition.py`, `voice_intent_digestor.py`
- 入口: `from kairon_voice import STTProviderFactory, TTSProviderFactory, WhisperAdapter, ElevenLabsAdapter`
- Provider: Whisper, Faster-Whisper, ElevenLabs, Google TTS, Azure TTS (全部optional)

**依赖**:
- 声明: `pydantic`, `numpy` (核心); `openai-whisper`, `faster-whisper`, `google-cloud-texttospeech` (optional)
- 实际import: `pydantic` ✓, **`numpy` ✗** (声明但仅类型注解?)
- 差距: `numpy` 可能未直接import（需确认）

**测试**: 2个文件，pytest + mock。覆盖接口契约、Provider工厂、各适配器逻辑  
**健康**: 🟢 成熟 — 设计优秀(optional-deps模式)，适配器架构清晰。v1.0.0  
**集成**: 不依赖内部包，不被其他包依赖  
**债务**: 无TODO/FIXME

---

## 5. kaironcloud-billing (v0.1.0)

**身份**: 计费子系统 — 模型、定价、用量跟踪、Stripe集成，提取自 SharedBrain D_Cloud  
**规模**: 15个源文件 / 3,599 LOC / 6个测试文件  
**架构**:
- 模块: `models.py`, `pricing.py`, `usage_tracker.py`, `bill_generator.py`, `subscription_manager.py`, `stripe_integration.py`, `webhook_handler.py`, `gateway/`(auth), `tenant/`(quota_enforcer), `tenant_manager.py`, `rate_limiter.py`
- 关键类: `PricingModel`, `UsageTracker`, `BillGenerator`, `SubscriptionManager`, `StripeClient`, `WebhookHandler`, `TenantManager`, `AuthGateway`, `RateLimiter`
- 使用sqlite3本地存储

**依赖**:
- 声明: `dependencies = []`, optional: `stripe`
- 实际import: `jwt` (在gateway/auth.py) — **未声明！**
- 差距: **`pyjwt` 是缺失依赖** — 代码中 `import jwt` 但pyproject里没写

**测试**: 6个文件，pytest风格。覆盖: 账单、模型、定价、用量跟踪、webhook处理  
**健康**: 🟡 存在 — 功能完整，requires-python >=3.11。但缺少 `pyjwt` 声明  
**集成**: 不依赖内部包，不被其他包依赖  
**债务**: 无TODO/FIXME。**关键问题: `import jwt` 无对应dependency声明**

---

## 6. kos (v2.0.0)

**身份**: 知识操作系统 — 跨域搜索、本体论、深度研究  
**规模**: 82个源文件 / 14,271 LOC / 24个测试文件 — 第二大包  
**架构**:
- 模块(14个子目录): `cli/`, `commands/`, `ontology/`, `indexer/`, `ingest/`, `perception/`, `self/`, `collab/`, `consensus/`, `minerva/`, `web/`, `mcp/`, `adapters/`, `accounting/`
- 入口: `kos.cli.__main__:main`, `kairon-cli` 别名
- 关键类: `KosIndexer`, `OntologyEngine`, `FactInjector`, `MemoryCard`, `KnowledgeBridge`, `MinervaAdapter`, `SelfAPI`
- 关键函数: `discover`, `cross_discovery`, `digest`, `metacog`, `web_search`, `scrape_url`

**依赖**:
- 声明: `python-docx`, `PyMuPDF`, `openpyxl`, `jieba`
- 实际import: `jieba` ✓(lazy), `numpy` ✓(query_service.py), `yaml` ✓(self/api.py), `eidos` ✓(内部), `python-docx`/`PyMuPDF`/`openpyxl` (文档parser)
- 差距: **`numpy` 和 `pyyaml` 未声明但被使用** — 缺失依赖

**测试**: 24个文件，pytest + conftest。测试命令、索引、本体、感知、适配器、MCP、Web等。使用 `KOS_HOME` fixture  
**健康**: 🟢 成熟 — 最大最活跃的包之一，v2.0.0。功能非常丰富  
**集成**: 依赖 `eidos`(内部), 不被其他包直接依赖  
**债务**: 1个TODO (eidos.py: "# TODO: replace with MCP calls")。**2个缺失依赖声明**

---

## 7. kronos (v0.5.0)

**身份**: 知识摄取管线 — L0原生HTTP / L2 Jina / L4 CloakBrowser 5层自动抓取引擎  
**规模**: 15个源文件 / 2,874 LOC / 9个测试文件  
**架构**:
- 模块: `fetch_router.py`, `fetcher/`(http, browser, classify, errors), `extractor.py`, `insight_engine.py`, `dispatcher.py`, `compressors/token_juicer.py`, `adapters.py`, `cli.py`, `mcp_server.py`, `gateway_client.py`
- 入口: `kronos.cli:main`, `kronos.mcp_server:main`
- 抓取层级: L0(原生HTTP), L0.5(Scrapling指纹), L2(Jina), L4(CloakBrowser)
- 关键类: `FetchRouter`, `HTTPFetcher`, `BrowserFetcher`, `Extractor`, `InsightEngine`, `TokenJuicer`, `Dispatcher`

**依赖**:
- 声明: `click`, `fastmcp`, `httpx`, `cloakbrowser`, `scrapling`, `core-models`
- 实际import: `click` ✓, `fastmcp` ✓, `httpx` ✓(lazy), `cloakbrowser` ✓, **`scrapling` ✗**, **`core-models` ✗**
- 差距: **`scrapling` 和 `core-models` 是僵尸依赖** — 声明但不import

**测试**: 9个文件，pytest风格。测试: 适配器、调度、ETL管线、抽取、抓取、insight引擎  
**健康**: 🟡 存在 — Alpha状态，功能完整但可选依赖多。5层抓取架构设计精良  
**集成**: 依赖 `core-models`(声明但未使用)，不被其他包依赖  
**债务**: 无TODO/FIXME。2个僵尸依赖

---

## 8. llm-gateway (v0.1.0)

**身份**: 统一LLM Provider抽象层 — ABC基类 + 多Provider实现 (Ollama/Anthropic/OpenAI/Gemini/DeepSeek/LM Studio/HITL)  
**规模**: 24个源文件 / 2,599 LOC / 2个测试文件  
**架构**:
- 模块: `provider.py`, `providers/`(8个Provider), `types.py`, `registry.py`, `policies.py`, `scheduler.py`, `circuit_breaker.py`, `retry.py`, `detection.py`
- 关键类: `BaseLLMProvider`, `LLMProvider`, `ModelRegistry`, `ModelScheduler`, `CircuitBreaker`, `RetryConfig`, `AnthropicProvider`, `OpenAIProvider`, `GeminiProvider`, `DeepSeekProvider`, `OllamaProvider`, `HitlLLMProvider`

**依赖**:
- 声明: `requests`, `pyyaml` (核心); `anthropic`, `openai`, `google-generativeai` (optional)
- 实际import: **`requests` ✗**, `pyyaml`? 使用了`httpx`(providers/base.py) — **未声明**
- 差距: **`requests` 和 `pyyaml` 是僵尸依赖**; **`httpx` 被使用但未声明！**
- 关键: 核心代码实际用 `httpx` 而非 `requests`

**测试**: 2个文件，pytest。测试LLMRequest/LLMResponse模型、Provider抽象类、统一接口  
**健康**: 🟡 存在 — Provider架构完善，双API设计(旧provider.py + 新providers/)，有冗余  
**集成**: 不依赖内部包，不被其他包依赖  
**债务**: 无TODO/FIXME。**`httpx` 缺失依赖**, `requests`/`pyyaml` 僵尸依赖

---

## 9. metaos (v7.1.0)

**身份**: MetaOS — 编排/治理层：决策门控、免疫监控、路由、数字资产引擎  
**规模**: 29个源文件 / 7,002 LOC / 3个测试文件  
**架构**:
- 模块: `core/`(engine, gate, immune, router, types), `layers/`(community, d_layer, governance, m_layer), `cli/`, `scenarios/`(8个测试场景), `mcp_server.py`, `dashboard.py`, `deadlock_detector.py`, `l2_controller.py`
- 入口: `metaos.cli:main`, `metaos.mcp_server:main`
- 关键类: `SEngine`, `Gate`, `ImmuneSystem`, `Router`, `DigitalAsset`, `Decision`, `CommunityEngine`, `CLI`, `L2Controller`

**依赖**:
- 声明: `fastmcp`, `structlog`
- 实际import: **`fastmcp` ✗**, **`structlog` ✗**
- 差距: **两个都是僵尸依赖** — 全部不用！实际只用了stdlib + sqlite3

**测试**: 3个文件，pytest。测试unit、deadlock_detector、L2 controller。另有8个scenario脚本(在src中，非正式测试)  
**健康**: 🟡 存在 — v7.1.0最高版本号但功能零散。场景脚本(8个)在src而非tests目录  
**集成**: 不依赖内部包，不被其他包依赖  
**债务**: 无TODO/FIXME。**2个僵尸依赖**, 场景脚本混在src中

---

## 10. minerva (v0.11.0)

**身份**: 本地优先的深度研究系统 — 分层管线、多源搜索、知识图谱、符号范式引擎、时序推理  
**规模**: 114个源文件 / 22,920 LOC / 34个测试文件 — **全库最大包**  
**架构**:
- 模块(25+子目录): `pipeline/`, `executor/`, `search/`, `knowledge/`, `graph/`, `paradigm/`, `embeddings/`, `sources/`, `storage/`, `quality/`, `triage/`, `mcp_server/`, `extractors/`, `maintenance/`, `creative/`, `observability/`, `metrics/`, `scheduler/`, `web/`, `llm/`, `index/`, `shared/`, `utils/`, `templates/`, `integration/`
- 入口: `minerva.cli:main`, `minerva.mcp_server.server:main`, `minerva.executor.daemon:main`
- 关键类: `PipelineEngine`, `Orchestrator`, `KnowledgeStore`, `RAGEngine`, `SearchEngine`, `BFSSearcher`, `TriageRouter`, `ParadigmEngine`, `GraphBridge`, `Executor`, `QualityGate`, `TemporalEngine`
- 关键函数: `harvest`, `deep_research`, `ingest`, `bfs_search`, `triage`

**依赖**:
- 声明(16个): `core-models`, `httpx`, `lancedb`, `pyyaml`, `croniter`, `spacy`, `sentence-transformers`, `pydantic`, `fastmcp`, `structlog`, `beautifulsoup4`, `readability-lxml`, `apscheduler`, `ddgs`, `ujson`, `urllib3`
- 实际import: `httpx` ✓, `lancedb` ✓(lazy), `spacy` ✓(lazy), `sentence-transformers` ✓(lazy), `fastmcp` ✓, `beautifulsoup4` ✓, `apscheduler` ✓(lazy), `yaml` ✓, `pydantic` ✓, `structlog` ✓, `croniter` ✓, `ddgs` ✓, `readability` ✓, `ujson` ✓, `urllib3` ✓, **`core-models` ✗**(声明但不import)
- **未声明但使用**: `fastapi` ✗, `starlette` ✗, `cryptography` ✗, `kairon_lib`(shared-lib) ✗, `mcp` ✗, `numpy` ✗
- 差距: **`core-models`是僵尸**; **6个依赖缺失声明**

**测试**: 34个文件 — 单元测试(19) + 集成测试(3) + 基准测试(3) + helpers。pytest + asyncio。覆盖: 搜索、RAG、知识图谱、BFS、triage、MCP、LLM、管线各阶段  
**健康**: 🟢 成熟 — Beta状态，全库最大最复杂包。Development Status 4 - Beta  
**集成**: 依赖 `core-models`(僵尸), `shared-lib/kairon_lib`(未声明), `eidos`(optional), `sophia`(optional)。不被其他包直接依赖  
**债务**: 无TODO/FIXME。**关键问题: 6个缺失依赖 + 1个僵尸依赖**, 大量lazy import**

---

## 汇总对比表

| 指标 | gc-engine | iris | kairon-assistant | kairon-voice | kaironcloud-billing | kos | kronos | llm-gateway | metaos | minerva |
|------|-----------|------|------------------|--------------|---------------------|-----|--------|-------------|--------|---------|
| **版本** | 0.1.0 | 0.1.0 | 1.0.0 | 1.0.0 | 0.1.0 | 2.0.0 | 0.5.0 | 0.1.0 | 7.1.0 | 0.11.0 |
| **源文件** | 7 | 46 | 9 | 8 | 15 | 82 | 15 | 24 | 29 | 114 |
| **代码行数** | 1,395 | 8,236 | 1,768 | 1,860 | 3,599 | 14,271 | 2,874 | 2,599 | 7,002 | 22,920 |
| **测试文件** | 2 | 10 | 3 | 2 | 6 | 24 | 9 | 2 | 3 | 34 |
| **子模块数** | 6 | 5+ | 8 | 4+ | 6+ | 14+ | 5+ | 6+ | 6+ | 25+ |
| **健康状态** | 🟡 | 🟢 | 🟢 | 🟢 | 🟡 | 🟢 | 🟡 | 🟡 | 🟡 | 🟢 |
| **僵尸依赖** | 0 | 2 | 0 | 0? | 0 | 0 | 2 | 2 | 2 | 1 |
| **缺失依赖** | 0 | 0 | 0 | 0? | 1 | 2 | 0 | 1 | 0 | 6 |
| **TODO/FIXME** | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| **内部依赖** | 无 | 无 | 无 | 无 | 无 | eidos | core-models(僵尸) | 无 | 无 | core-models(僵尸), shared-lib |
| **测试风格** | unittest | pytest | pytest | pytest+mock | pytest | pytest | pytest | pytest | pytest | pytest+asyncio |

### 关键发现

1. **最大包**: minerva (114文件/22,920行) — 全库核心
2. **最复杂依赖问题**: minerva — 6个未声明依赖 + 1个僵尸依赖
3. **最干净包**: gc-engine 和 kairon-assistant — 零依赖、无债务
4. **普遍问题**: 5个包有**僵尸依赖**(声明但不用); 3个包有**缺失依赖**(用但未声明)
5. **安全注意**: `shared-lib`中硬编码 `secret_key = "bos-governance-demo-key"`
6. **未完成**: `kaironcloud-billing` 缺少 `pyjwt` 声明; `llm-gateway` 用 `httpx` 但未声明
7. **最成熟**: kos (v2.0.0, 24测试), minerva (Beta), kairon-assistant (v1.0.0), kairon-voice (v1.0.0)
