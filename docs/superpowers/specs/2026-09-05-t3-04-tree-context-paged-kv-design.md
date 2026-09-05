---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y2Q1-T3-04
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T3-04 超长文档树状上下文与 PagedKV 块级缓存设计

## 1. 目标

针对数十万字级文档（卫生信息化方案/技术标书/全量 ADR），在 omlxc dataplane
构建分层树状上下文索引，复用既有 PagedKV 分页内存管理，实现超长文本的
常量内存占用、毫秒级检索与跨章节一致性（矛盾）检测。

## 2. In scope

1. `projects/omlxc/src/omlxc/dataplane/tree_context.py`（新文件）：
   - `TreeContextNode`：章节树节点（标题层级/字节区间/摘要/子节点）。
   - `TreeContextIndex`：
     - `build(text)`：按标题结构切分为层级树，叶子块注册进
       `PagedKVMemoryManager`（块级分页，不全量驻留内存）。
     - `locate(query)`：标题/关键词命中定位到节点区间（纯 Python，
       无 LLM 依赖）。
     - `detect_conflicts()`：跨章节一致性扫描——数值/日期/百分比类
       断言的同名条目跨节对比，输出冲突候选（条款 A vs 条款 B）。
     - `ttft_probe()`：加载后首查询首字响应计时（目标 ≤50ms）。
   - 内存水位：块表驻留 + 惰性加载叶子正文，峰值内存可测可断言。
2. `projects/omlxc/tests/unit/test_tree_context.py`（新文件）：
   - 树构建/定位/冲突检测/TTFT 上限/内存水位断言（50 万字合成语料）。

## 3. Out of scope

- 不做 LLM 语义摘要（树节点摘要为结构性摘录，非生成式）。
- 不引入向量库/新依赖；不改 paged_kv.py 既有契约。
- 不接入真实卫生文档语料（用合成语料验证机制）。

## 4. 验收（对齐 ledger done_when）

1. 50 万字合成文档：加载后 `ttft_probe()` ≤50ms。
2. `detect_conflicts()` 在植入矛盾（同一条款名下数值不一致）的语料上
   精准报出冲突对。
3. 峰值内存（resource.getrusage）恒定在 16GB 之下（实际断言 ≤2GB 以
   留安全边际，报告实测值）。
4. 单测全部通过。
