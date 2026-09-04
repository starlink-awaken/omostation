---
title: ADR-0001-hybrid-rag
type: doc
---

# ADR-0001: Hybrid RAG 混合检索架构

> 状态: 接受 | 日期: 2026-07-08

## 背景

单一搜索模式无法覆盖所有查询类型:
- 关键词搜索无法处理语义相关但词汇不同的查询 (如"信息治理"匹配不到"数据治理")
- 语义搜索对精确术语匹配不佳 (如错误码、专有名词)
- 图谱搜索依赖实体覆盖度

## 决策

采用 **FTS5 + LanceDB + 图谱** 三路混合检索，通过 RRF (Reciprocal Rank Fusion) 融合结果。

## 技术细节

### 检索管线
```
Query ──┬── FTS5 (jieba分词) ───────── keyword results
        ├── LanceDB (embedding) ────── semantic results
        └── Graph (entity match) ────── graph results
                                          │
                                          ▼
                                   RRF Fusion + 提升排序
                                          │
                                          ▼
                                   最终搜索结果
```

### RRF 公式
```
score(d) = Σ w_s / (k + rank_s(d))

权重分配:
- keyword: 1.0 (基线)
- semantic: 1.2 (语义理解加权)
- graph: 0.8 (辅助补充)
- k = 60 (避免低排名过度奖励)

加成规则:
- 多源命中 (≥2 sources): +20% per additional source
```

### 降级策略
1. 向量索引未构建 → 仅关键词+图谱
2. omlx 不可用 → 本地 sentence-transformers
3. 实体图谱为空 → 仅关键词+语义

## 后果

### 正面
- 搜索命中率: ~80% → >95%
- 语义理解能力覆盖长尾查询
- 图谱推理发现隐含关联

### 负面
- 系统复杂度增加 (三路维护)
- 维护成本提高 (三方数据一致性)

## 参考

- Hybrid RAG 论文: https://arxiv.org/abs/2408.04948
- RRF 算法: Cormack et al. 2009
