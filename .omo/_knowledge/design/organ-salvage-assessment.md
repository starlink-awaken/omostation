---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# 废弃器官深度挖掘评估报告

> 2026-06-02 · 对 10 个已废弃器官的全面扫描
> 筛选标准: dataclass/enum 丰富 + 耦合度低 (<3) + 可独立提取

---

## 评估矩阵

| 器官 | 总文件 | 有价值模块 | 可即时提取 | 建议 |
|------|:-----:|:--------:|:--------:|------|
| D_Execution | 170+ | 15 | 9 | 🟡 选 3-4 最优 |
| D_Governance | 74+ | 10 | 7 | 🟡 选 RBAC+Audit |
| D_Memory | 120+ | 10 | 8 | 🟢 向量存储+缓存 |
| D_Gateway | 80+ | 11 | 9 | 🟢 MCP协议+Auth |
| D_Logos | 45+ | 7 | 5 | 🟢 Pipeline+Plugin |
| D_Harvest | 70+ | 12 | 10 | 🟢 Utils+Quality |
| D_Immunity | 60+ | 5 | 3 | 🔴 大多耦合高 |
| D_Monitoring | 35+ | 2 | 1 | 🔴 仪表盘非通用 |
| D_Excretion | 20+ | 3 | 2 | 🟢 GC+Distillation |
| D_Extension | 15+ | 2 | 2 | 🟢 Market+Plugin |

---

## 精选提取清单: 19 个高价值模块

### Priority 1: 通用工具类 (立即可提取)

| # | 模块 | 源位置 | 行数 | 目标包 | 用途 |
|---|------|--------|:--:|--------|------|
| 1 | **RetryPolicy** | D_Execution/engine/retry_policy.py | 103 | shared-lib | 重试策略配置 |
| 2 | **Deduplicator** | D_Harvest/utils/deduplicator.py | 136 | shared-lib | 去重工具 |
| 3 | **ErrorClassifier** | D_Harvest/utils/error_classifier.py | 206 | shared-lib | 错误分类器 |
| 4 | **Versioning** | D_Harvest/utils/versioning.py | 252 | shared-lib | 版本管理模型 |
| 5 | **QualityGate** | D_Harvest/quality/gate.py | 113 | minerva | 质量门控+规则 |

### Priority 2: 数据模型类

| # | 模块 | 源位置 | 行数 | 目标包 | 用途 |
|---|------|--------|:--:|--------|------|
| 6 | **AuthModels** | D_Gateway/organs/auth_models.py | 301 | agora | OAuth2 认证模型 (dataclass×16) |
| 7 | **PlannerState** | D_Execution/organs/planner_state.py | 171 | agent-runtime | 规划状态机模型 |
| 8 | **RoleRBAC** | D_Governance/organs/role/role_rbac.py | 268 | shared-lib | RBAC 角色权限模型 |
| 9 | **AuditTrail** | D_Governance/organs/audit/audit_trail.py | 601 | shared-lib | 审计追踪 (dataclass×13) |
| 10 | **PermissionMatrix** | D_Governance/organs/compliance/permission_matrix.py | 696 | shared-lib | 权限矩阵 (dataclass×15) |

### Priority 3: 协议/管道类

| # | 模块 | 源位置 | 行数 | 目标包 | 用途 |
|---|------|--------|:--:|--------|------|
| 11 | **MCPTransport** | D_Gateway/organs/mcp_transport.py | 288 | agora | MCP 传输层模型 |
| 12 | **MCPProtocolHandler** | D_Gateway/organs/mcp_protocol_handler.py | 316 | agora | MCP 协议处理器 |
| 13 | **PipelineModels** | D_Logos/organs/pipeline_models.py | 220 | ontoderive | 文档管道模型 (dataclass×13) |
| 14 | **PluginSystem** | D_Logos/organs/plugin_system.py | 774 | forge | 插件系统 (dataclass×11) |

### Priority 4: 基础设施类

| # | 模块 | 源位置 | 行数 | 目标包 | 用途 |
|---|------|--------|:--:|--------|------|
| 15 | **NumpyVectorStore** | D_Memory/organs/numpy_vector_store.py | 395 | eidos | NumPy 向量存储后端 |
| 16 | **SmartCache** | D_Memory/organs/smart_cache.py | 462 | eidos | 智能缓存 (dataclass×4) |
| 17 | **ConfigManager** | D_Logos/organs/config_manager.py | 420 | shared-lib | 配置管理 (dataclass×13) |
| 18 | **Credentials** | D_Harvest/sources/credentials.py | 309 | minerva | 凭据管理 (dataclass×4) |
| 19 | **DistilledKnowledgeStore** | D_Excretion/organs/distillation/distilled_knowledge_store.py | 426 | kos | 知识精馏存储 (dataclass×6) |

### 确认已提取 (不再重复)

| 模块 | 已提取到 |
|------|---------|
| RateLimiter (token bucket) | agora/rate_limit.py |
| IntentClassifier + ComplexityLevel | minerva/intent.py |
| HarvestFact + HarvestRecord | minerva/harvest_models.py |
| EnergyBudget + EnergyEntry | eu-pricing/energy_model.py |
| KnowledgeRecord + KnowledgeBridge | kos/knowledge_bridge.py |
| FrontmatterDetector + DetectionResult | ontoderive/engine/frontmatter.py |
| LanguageCode + RecognitionResult | agent-runtime/voice_models.py |
| UriResource + UriRegistry | shared-lib/uri_models.py |
| MemoryRecord + MemorySession | eidos/memory_schema.py |
| Enterprise/Relation/Provenance/KG tests | core-models/tests/test_models.py |
| OpLevel + operation_level tests | shared-lib/tests/test_operation_level.py |

---

## 建议执行方案

### 立即提取 (今天): Priority 1 — 5 个通用工具类 (~810 行)
- 全部独立、无耦合、可快速迁移
- 预计 30-45 分钟

### 近期提取 (本周): Priority 2+3 — 9 个模型/协议类 (~3,500 行)
- 数据模型为主，少量协议适配
- 预计 2-3 小时

### 后续评估: Priority 4 — 5 个基础设施类 (~2,000 行)
- 依赖较多或需要适配层
- 每个模块独立评估

---

*总可提取: ~6,310 行高价值代码 + 对应测试 (~3,000 行)*
*估算净价值: 9,310 行可复用代码 从 268,000 行废弃器官中*
