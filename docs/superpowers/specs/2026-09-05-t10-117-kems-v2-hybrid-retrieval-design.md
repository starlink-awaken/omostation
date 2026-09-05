---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q3-T10-117
risk_level: L1
human_gate: false
type: ssot
last_updated: 2026-09-05
---

# KEMS-v2 卫生政务与技术架构领域知识图谱毫秒级混合检索

**Bet**: BET-Y1Q3-T10-117
**Version**: 1.0.0
**Date**: 2026-09-05
**Status**: accepted

## 1. Problem

kairon 脚本层已有 KEMS（Knowledge Engineering & Management System）的 adjudication queue、model evaluation 等工具，
但缺少核心知识图谱模块和混合检索能力。gbrain 引擎已有 pgvector HNSW 向量索引和 GraphNode/GraphPath 类型，
但缺少面向卫生政务领域的语义级混合检索路由。

目标：为卫生健康国家政策、公文规程、系统 ADR 与历史优秀批复构建 KEMS-v2 知识图谱，
结合向量嵌入、BM25 全文索引与图关系推理，实现 <50ms 混合检索与精准引用溯源。

## 2. Architecture

### 2.1 kairon graph module (`src/kairon/graph/kems_v2.py`)

- **KnowledgeGraph**: 节点实体（Policy / Regulation / ADR / Approval）与关系边（cites / supersedes / implements / references）
- **GraphBuilder**: 从 ADR、政策文档、kairon 脚本输出自动抽取实体与关系
- **Storage**: JSONL 持久化 + 内存图结构，不引入外部图数据库依赖

### 2.2 gbrain hybrid retrieval (`src/retrieval/hybrid.ts`)

- **HybridSearcher**: 融合向量相似度 + BM25 全文分数 + 图关系跳数的统一排序
- **ScoreFusion**: 归一化三路分数，加权融合（向量 0.4 + BM25 0.35 + 图 0.25）
- **溯源链**: 每条结果附带 `source_chain`（policy → regulation → ADR → approval）

## 3. Non-Goals

- 不引入未经审核的公网不可信第三方语料
- 不引入 Neo4j 或外部图数据库依赖
- 不做实时增量索引（首批全量构建）

## 4. Criteria

| ID | Criterion | 测量方式 |
|----|-----------|----------|
| C1 | 图谱实体节点 ≥5000 个 | `kems_v2 graph stats --min-nodes 5000` |
| C2 | 关系边 ≥20000 条 | 同上 |
| C3 | 混合检索 Top-3 Recall ≥95% | `hybrid-query --eval` 测试集 |
| C4 | P99 延迟 <50ms | benchmark 脚本 |
| C5 | 为 Spine Draft 提供溯源链接 | `hybrid-query` 返回 `source_chain` |

## 5. Test Strategy

- **Unit**: kems_v2 graph operations (add/remove/query/stats)
- **Integration**: hybrid score fusion + ranking correctness
- **E2E**: `hybrid-query --q 卫生健康数字化转型` 返回溯源结果

## 6. Write Surfaces

- `projects/knowledge/kairon/src/kairon/graph/__init__.py`
- `projects/knowledge/kairon/src/kairon/graph/kems_v2.py`
- `projects/knowledge/kairon/tests/test_kems_v2_graph.py`
- `projects/knowledge/gbrain/src/retrieval/hybrid.ts`
- `projects/knowledge/gbrain/src/retrieval/hybrid.test.ts`
- `docs/plans/3y-bet-ledger.yaml`
- `.omo/_knowledge/retros/BET-Y1Q3-T10-117.md`
