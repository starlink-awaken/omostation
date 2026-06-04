# 10器官全面深度扫描 — 最终评估报告

> 2026-06-02 · 10 并行 agent · 865 Python 文件 · ~214K 行代码

---

## 总览

| 器官 | 文件数 | 行数 | 可提取 | 零耦合 | 核心发现 |
|------|:-----:|:-----:|:-----:|:-----:|------|
| D_Execution | 275 | 55,725 | ~40 | 20+ | llm-gateway (8 provider), symphony, engine-core |
| D_Memory | 133 | 42,359 | ~25 | 10 | storage_dal, vector_backends, nks/smart_test_selector |
| D_Gateway | 98 | 26,516 | ~30 | 15 | auth包, MCP协议, federation, extension marketplace |
| D_Harvest | 110 | 29,394 | ~20 | 8 | utils, search/bm25, embeddings, observability |
| D_Governance | 131 | 27,200 | ~28 | 9 | thinking_paths, collab_protocol, RBAC, committee |
| D_Logos | 51 | 16,857 | ~21 | 9 | pipeline框架, alignment engine, config_manager |
| D_Cloud | 21 | 5,278 | ~15 | 7 | billing全子模块零耦合(Stripe+Pricing+Webhook) |
| D_Intelligence | 20 | 4,007 | ~10 | 5 | session_manager, 推理引擎(×4), smart_assistant |
| D_Continuity | 15 | 4,143 | ~8 | 3 | CRDT原语, conflict_resolver, session_store |
| D_Voice | 11 | 2,631 | ~8 | 5 | voice_io契约, STT/TTS适配器(Whisper/ElevenLabs) |

---

## 十大零耦合模块 (立即可提取，无需适配)

| 排名 | 模块 | 器官 | 行数 | 目标包 | 说明 |
|:--:|------|------|:--:|--------|------|
| 1 | **storage_dal.py** | D_Memory | 233 | minerva | 37+ 文件依赖的基础设施 |
| 2 | **thinking_paths.py** | D_Governance | 763 | kairon.thinking | 17 种思维模式+7 工厂函数 |
| 3 | **llm/provider.py + 8 providers** | D_Execution | ~1,400 | llm-gateway | Ollama/Anthropic/OpenAI/Gemini/DeepSeek |
| 4 | **billing/models.py + pricing.py + stripe** | D_Cloud | ~1,800 | kaironcloud.billing | 完整计费系统，零 BaseMembrane |
| 5 | **event_bus.py** | D_Execution | 336 | engine-core | 通用发布订阅，纯 stdlib |
| 6 | **symphony/models.py** | D_Execution | 311 | symphony-protocol | 12 dataclass/enums 舞台编排模型 |
| 7 | **permission_matrix.py** | D_Governance | 696 | kairon.rbac | 完整 RBAC 权限矩阵 |
| 8 | **collab_protocol.py** | D_Governance | 592 | kairon.collaboration | 9 个 dataclass 协作协议库 |
| 9 | **bm25_searcher.py** | D_Harvest | 738 | kairon.search | 纯 Python BM25 检索引擎 |
| 10 | **voice_io.py** | D_Voice | 173 | kairon.voice | VoiceResult/VoiceConfig/ABCs 契约 |

---

## 自然包分组 (可直接独立发布)

### 1. llm-gateway (~1,400 行, 零耦合)
```
D_Execution/organs/llm/
├── provider.py          ← ABC + LLMRequest/LLMResponse
├── ollama_provider.py   ← Ollama REST API
├── anthropic_provider.py ← Claude API
├── openai_provider.py   ← GPT models
├── gemini_provider.py   ← Google Gemini
├── deepseek_provider.py ← DeepSeek API
├── hitl_provider.py     ← Human-in-the-loop 回退
├── lmstudio_provider.py ← LM Studio 本地
└── quota_router.py      ← 多 provider 路由
```

### 2. kaironcloud.billing (~2,300 行, 零耦合)
```
D_Cloud/organs/billing/
├── models.py            ← ResourceType/UsageRecord/Bill/BillLineItem/PricingTier
├── pricing.py           ← 分层定价引擎 (Decimal 精度)
├── usage_tracker.py     ← SQLite 用量追踪
├── bill_generator.py    ← 月度账单生成
├── stripe_integration.py ← Stripe SDK 封装
├── subscription_manager.py ← 订阅生命周期
└── webhook_handler.py   ← HMAC 签名验证
```

### 3. symphony-protocol (~1,740 行)
```
D_Execution/organs/symphony/
├── models.py            ← Stage/Transition/Invariant/AgentMatcher 数据模型
├── state_machine.py     ← 4+1 阶段状态机
├── agent_matcher.py     ← 加权 Agent-任务匹配
└── trigger_engine.py    ← 条件触发器引擎
```

### 4. kairon.voice (~1,100 行)
```
D_Voice/
├── interfaces/voice_io.py    ← VoiceResult/VoiceConfig/ABCs
├── interfaces/base_voice.py  ← 基础 STT/TTS 实现
├── stt/whisper_adapter.py    ← Whisper 语音识别
├── stt/stt_provider.py       ← STT 工厂
├── tts/tts_adapter.py        ← ElevenLabs/Google/Azure TTS
└── tts/tts_provider.py       ← TTS 工厂
```

### 5. kairon.search + embeddings (~1,370 行)
```
D_Harvest/
├── search/bm25_searcher.py       ← 纯 Python BM25 + 中文分词
├── embeddings/providers.py       ← OpenAI/local/mock embedding 工厂
└── embeddings/__init__.py        ← EmbeddingProvider ABC
```

### 6. kairon.pipeline (~1,300 行, D_Logos)
```
D_Logos/organs/
├── pipeline_models.py   ← StepStatus/StepResult/BatchItem/PipelineCheckpoint
├── pipeline.py          ← 检查点/恢复/并行批处理/故障隔离
├── pipeline_steps/base.py ← PipelineStep ABC
├── pipeline_steps/core_steps.py       ← Scan/Diff/Report 步骤
├── pipeline_steps/governance_steps.py ← CI 门禁步骤
└── pipeline_steps/validation_steps.py ← 验证步骤
```

### 7. kairon.governance (~3,000 行, D_Governance)
```
D_Governance/organs/governance/
├── ai/thinking_paths.py          ← 17 种思维模式
├── consensus/committee.py        ← 13 种角色+委员会治理
├── consensus/consensus_mechanism.py ← 共识投票
├── collaboration/collab_protocol.py ← 协作协议库
├── collaboration/collective_mind.py  ← 集体审议
├── core/governance_engine.py     ← 治理引擎
├── emergency/auto_executor.py    ← 自动执行
└── federation/*.py               ← 联邦学习+信任网络
```

---

## 之前漏报更正

第一轮评估报告存在以下漏报：

| 漏报项 | 实际发现 |
|--------|---------|
| "D_Cloud 是空壳" | **错误** — 21 文件/5,278 行，billing 子模块零耦合 |
| "19 个提取模块" | **实际 ~200+** 可提取模块 |
| "D_Execution 全被 agentmesh 替代" | 有 **llm-gateway + symphony + engine-core** 三个完整子包 |
| "D_Harvest 全高耦合" | utils/search/embeddings/observability 几乎零耦合 |
| "D_Intelligence 只有 intent" | 有完整的 **推理引擎×4 + 会话管理** |

---

## 推荐执行优先级

### P0 — 立即提取 (今天)
1. D_Execution/llm/* → llm-gateway 包 (零耦合, 8 provider, 通用价值极高)
2. D_Cloud/billing/* → kaironcloud.billing (零耦合, 完整 Stripe 集成)
3. D_Harvest/utils/* → kairon.utils (retry/dedup/rate_limit/concurrent)

### P1 — 本周提取
4. D_Governance/thinking_paths.py → kairon.thinking
5. D_Voice/{interfaces,stt,tts}/* → kairon.voice
6. D_Execution/engine/event_bus.py + task_store.py → engine-core
7. D_Memory/storage_dal.py → minerva (解锁后续 37+ 文件)
8. D_Harvest/{search,embeddings} → kairon.{search,embeddings}

### P2 — 本月提取
9. D_Execution/symphony/* → symphony-protocol
10. D_Logos/pipeline* → kairon.pipeline
11. D_Governance/governance/* → kairon.governance
12. D_Memory/vector_backends/* → minerva.vectors

---

*汇总: 10 agent × 865 文件深度扫描完成*
