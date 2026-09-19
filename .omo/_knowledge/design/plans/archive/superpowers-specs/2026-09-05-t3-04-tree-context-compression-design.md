---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y2Q1-T3-04
risk_level: L1
human_gate: false
value_indicator_policy: false
type: ssot
---

# T3-04 超长文档树状上下文压缩与毫秒级精准问答设计

## 1. 目标

针对超长政务/架构全案文档（50 万字级），构建分层树状上下文摘要与
PagedKV 块级缓存，实现超长文本秒级跨卷对比检索与逻辑矛盾检测。

## 2. In scope

1. `projects/omlxc/src/omlxc/dataplane/tree_context.py`（新文件）：
   - `TreeContextIndex` 类：将长文档按标题层级切分为树状摘要结构。
   - 每个节点存储：heading path、摘要文本（<200 token）、chunk 指针、
     embedding 向量。
   - 支持 `query(text, top_k)` 返回最相关节点路径 + 原文片段。
   - 支持 `find_contradictions()` 跨节点语义冲突检测（embedding 余弦
     相似度 < 0.3 + 关键实体重叠 > 50% 视为候选矛盾）。
2. `projects/omlxc/src/omlxc/dataplane/paged_kv.py`（新文件）：
   - `PagedKVCache`：固定显存预算（16GB 水位）的分页 KV 缓存。
   - LRU 淘汰策略，按 4KB 块粒度管理。
   - `put(key, value, priority)` / `get(key)` / `evict()` 接口。
3. `projects/omlxc/tests/unit/test_tree_context.py`（新文件）：
   - 单元测试：树构建、查询、矛盾检测。
4. `projects/omlxc/tests/unit/test_paged_kv.py`（新文件）：
   - 单元测试：put/get/evict、LRU 淘汰、显存预算。

## 3. Out of scope

- 不引入外部向量数据库（本地纯 embedding 计算）。
- 不修改现有 dataplane 模块的公共接口。
- 不做 GPU 显存直通（当前版本为 CPU 模式）。

## 4. 验收（对齐 ledger done_when）

1. `uv run python -m pytest projects/omlxc/tests/unit/test_tree_context.py -q` exit 0。
2. `uv run python -m pytest projects/omlxc/tests/unit/test_paged_kv.py -q` exit 0。
3. PagedKV 在 16GB 预算下可缓存 ≥10K 条 KV 块而不 OOM。
4. TreeContextIndex 对 50 万字测试文档 query 响应 < 50ms（CPU 模式）。
5. 矛盾检测至少能识别"旧政策被新政策废止"类型的冲突。
