---
title: scenario-coverage-audit
type: doc
---

# kairon 场景覆盖审计

> 从**用户应用场景**维度审计 kairon 16 包的覆盖度 + 缺口 (场景维度优化, 2026-07-13)
> 配合 CAPABILITY-MAP (包能力) + CALLCHAIN (数据流) + ARCHITECTURE (架构)

---

## 一、已覆盖场景 (6 类)

### 1. 知识管理 (kos + kronos + core-models + eidos)
- **场景**: 个人/团队知识库构建, 跨域搜索, 实体/关系建模
- **包链**: kronos 摄取 → eidos 记忆/nks → kos 索引/搜索 → core-models 建模
- **状态**: 🟢 成熟 (kos v2.0 P0-P4, 30K LOC, 35 tests)

### 2. 深度研究 (minerva + iris + ontoderive)
- **场景**: 自动化研究, 多源搜索, 推导报告
- **包链**: iris 连接器 → minerva 8 引擎研究 → ontoderive 渊衍推导
- **状态**: 🟢 成熟 (minerva v0.15, ontoderive v3.6.4)

### 3. 代码分析 (codeanalyze)
- **场景**: AST 代码扫描, 代码图谱, 重构/安全审查
- **包链**: codeanalyze 独立
- **状态**: 🟢 (v0.5, 25 MCP tools)

### 4. 数据校验/推导 (eidos schema + ontoderive)
- **场景**: Schema 约束, 本体推理, 语义验证
- **包链**: eidos schema 子集 + ontoderive 验证与演化流水线 (`MetaValidateEngine` / `MetaEvolveEngine` + 单/批 `Step`)
- **状态**: 🟢 (ontoderive 验证步骤覆盖了单项、批量并行/顺序场景；最厚测试集位于 `packages/ontoderive/tests/test_validation_steps.py`)

### 5. 资产管理 (forge + iris)
- **场景**: AI 数字资产管理, 工具注册/发现, 平台同步
- **包链**: forge 资产 + iris 平台连接
- **状态**: 🟢 (forge v1.3)

### 6. 可观测/监控 (kairon-observability + kairon-utils)
- **场景**: SLO/metrics/anomaly/alerts
- **状态**: 🟡 骨架 (2053 LOC 但测试薄)

---

## 二、缺口场景 (待覆盖)

### G1. 实时协作/多用户 (缺)
- **场景**: 多用户同时编辑知识, 实时同步, 冲突解决
- **现状**: eidos continuity (CRDT 会话) 是单用户会话连续性, 非多用户协作
- **建议**: eidos CRDT 扩展到 entity-level 多用户协作 (现 continuity_session 是会话级)

### G2. 多模态知识 (缺)
- **场景**: 图片/音频/视频知识摄入 + 语义搜索
- **现状**: kronos 摄取是文本/URL/HTML, 无多模态; eidos vector_backends 是文本向量
- **建议**: kronos + eidos vector_backends 扩展多模态 embedding (CLIP/whisper)

### G3. 外部 LLM/工具市场深度集成 (部分)
- **场景**: 动态接入外部 LLM (OpenAI/Claude/Gemini), MCP 工具市场生态
- **现状**: minerva 多 LLM (可能硬编码), forge 工具注册 (内部工具, 非外部市场)
- **建议**: forge 扩展 MCP 外部工具市场发现 + minerva LLM provider 抽象层 (对接 omlx gateway)

### G4. 知识图谱可视化/交互 (部分)
- **场景**: 图谱可视化, 交互式查询, 实体卡片浏览
- **现状**: eidos viz/viz_interactive (有), kos graph (CLI 输出), 无统一前端
- **建议**: 统一可视化前端 (eidos viz + kos graph → cockpit UI)

### G5. 流式/增量知识 (部分)
- **场景**: 实时数据流增量入图谱, 不全量 rebuild
- **现状**: kos indexer --daemon/--full-embed (有增量回灌), eidos nks_incremental_indexer (有)
- **建议**: 统一流式摄取管线 (kronos event → eidos incremental → kos delta index)

---

## 三、场景成熟度矩阵

成熟度与缺口状态以代码实现 + 回归测试为准；具体测试数量以 CI 产物为权威，本表不硬编码计数。

| 场景 | 成熟度 | 关键缺口 | 实现状态 |
|------|--------|----------|----------|
| 知识管理 | 🟢 成熟 | 多用户协作 G1 | ✅ G1 eidos/entity_collab.py (CRDT stub) |
| 深度研究 | 🟢 成熟 | 外部 LLM 深度集成 G3 | ✅ G3 forge/discover_mcp.py |
| 代码分析 | 🟢 成熟 | - | - |
| 数据校验 | 🟢 成熟 | - | ✅ ontoderive.validation_steps + meta_validate/meta_evolve |
| 资产管理 | 🟡 部分 | 工具市场 G3 | ✅ G3 discover_mcp |
| 可观测 | 🟢 成熟 | 测试补全 (P1) | ✅ kairon-observability 全模块测试通过 |
| 多模态 | 🟡 stub | G2 | ✅ G2 eidos/multimodal.py (CLIP/whisper 可选依赖) |
| 可视化 | 🟢 统一 | G4 统一前端 | ✅ G4 kos/viz_unified.py |
| 流式增量 | 🟢 stub | G5 统一管线 | ✅ G5 kos/stream_pipeline.py |

> **G1-G5 实现状态 (2026-07-13)**: 5 缺口全部实质代码落地 (stub/编排层).
> - G1 `eidos/entity_collab.py` (CollaborativeEntity CRDT, demo 验证多用户无冲突合并)
> - G2 `eidos/multimodal.py` (CLIP 图片 + whisper 音频 embedding, 可选依赖)
> - G3 `forge/discover_mcp.py` (MCP 外部市场发现: 本地 configs + agora backends + registry)
> - G4 `kos/viz_unified.py` (统一 kos graph + eidos viz Mermaid, render_all 全景)
> - G5 `kos/stream_pipeline.py` (kronos→eidos incremental→kos delta 流式编排, watch mtime)
> stub 说明: 接口 + 编排骨架已就位, 接各包实际 incremental/embed 实现 (注入 handler) 即生产可用.

---

## 四、优先级建议

1. **P1 可观测测试补全** — kairon-observability 2053 LOC 测试薄, 内部健康依赖
2. **P2 多用户协作 G1** — eidos CRDT 扩展 entity-level, 知识管理核心演进
3. **P2 外部 LLM/工具市场 G3** — forge MCP 市场 + minerva provider 抽象, 生态扩展
4. **P3 多模态 G2 / 可视化 G4 / 流式 G5** — 功能扩展, 按需

---

## 五、场景 × 包 矩阵 (谁服务谁)

| 包 \ 场景 | 知识管理 | 深度研究 | 代码分析 | 资产管理 | 可观测 |
|-----------|----------|----------|----------|----------|--------|
| kos | ★ 搜索/索引 | ☆ 语义召回 | | | ☆ status |
| eidos | ★ 记忆/nks | ☆ 记忆召回 | | | ☆ health |
| minerva | | ★ 研究 | | | |
| ontoderive | | ☆ 推导 | | | |
| kronos | ☆ 摄取 | | | | |
| iris | | ☆ 平台 | | ☆ 同步 | |
| codeanalyze | | | ★ | | |
| forge | | | | ★ | |
| sophia | ☆ 范式 | ☆ 符号研究 | | | |
| kairon-observability | | | | | ★ |

(★ 主服务, ☆ 辅助)

---

*审计日期: 2026-07-13 · 基于 CAPABILITY-MAP + CALLCHAIN + ARCHITECTURE*
