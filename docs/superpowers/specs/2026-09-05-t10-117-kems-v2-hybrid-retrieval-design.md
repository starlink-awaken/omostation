---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q3-T10-117
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-117 KEMS-v2 知识图谱混合检索设计

## 1. 目标

将卫生健康政策、公文规程、系统全量 ADR 与历史优秀批复沉淀为 KEMS-v2
知识图谱（kairon 图层），结合 BM25 全文索引与图关系推理实现 <50ms
混合检索，并为 Spine Draft 提供政策依据溯源链接。

## 2. In scope

1. `projects/knowledge/kairon/src/kairon/graph/kems_v2.py`（新文件）：
   - `KemsV2Graph`：实体（政策/条款/ADR/批复/机构）+ 关系（引用/依据/
     修订/管辖）建模；从 ADR 目录与 replay buffer 批注语料构建。
   - `hybrid_search(query, top_k)`：BM25（纯 Python 倒排，无外部依赖）
     × 图关系扩散二跳，返回带溯源路径（节点 → 源文件:行）的结果。
   - 规模验证：合成 + 真实 ADR 语料构建 ≥5000 实体 / ≥20000 边。
2. `projects/knowledge/gbrain/src/retrieval/hybrid.ts`（增量）：
   - gbrain 检索面注册 KEMS-v2 数据源适配（TS 侧 import 图谱导出的
     JSONL 快照）。
3. 测试：图谱规模断言、Top-3 Recall（合成查询集 ≥95%）、溯源链接
   完整性、检索延迟 <50ms。

## 3. Out of scope

- 不引入向量数据库/嵌入模型服务（BM25 + 图推理为本 bet 检索面；
  向量嵌入属既有 omlxc embedding 能力的后续接合）。
- 不抓取外部真实政策全文（以仓内 ADR/批复语料 + 合成政策样本构建）。

## 4. 验收（对齐 ledger done_when）

1. 图谱实体节点 ≥5000、关系边 ≥20000（构建脚本可复现）。
2. Spine Draft 可获得政策依据溯源链接（node → source path:line）。
3. 合成查询集 Top-3 Recall ≥95%，单次检索 <50ms。
4. 单测全部通过。
