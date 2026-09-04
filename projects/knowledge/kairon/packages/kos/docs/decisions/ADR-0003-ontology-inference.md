---
title: ADR-0003-ontology-inference
type: doc
---

# ADR-0003: 本体推理策略

> 状态: 接受 | 日期: 2026-07-08

## 背景

知识图谱的实体关系推导面临两种极端：
- 纯规则推理（正则匹配）覆盖不全，无法从非结构化文本提取关系
- 纯 LLM 推理成本高（API 费用 + 延迟），不适合批量处理

## 决策

采用 **共现推导 + 文本匹配 + 治理规则** 三级推理策略，零 API 成本实现实体关系自动推导。

## 技术细节

### 推理策略栈

| 策略 | 优先级 | 置信度 | 说明 |
|------|--------|--------|------|
| 共现推导 | 1 | 0.5-0.9 | 同文档实体建立 related_to 关系 |
| 文本匹配 | 2 | 0.5 | 实体标签在文档中出现即建立关系 |
| 治理规则 | 3 | 0.95 | L0 层级架构依赖冲突检测 |

### 共起推导算法
```sql
-- 找到共享文档的实体对
SELECT ed1.entity_id AS a, ed2.entity_id AS b, COUNT(*) AS shared_docs
FROM kos_entity_docs ed1
JOIN kos_entity_docs ed2 ON ed1.doc_id = ed2.doc_id AND ed1.entity_id < ed2.entity_id
GROUP BY ed1.entity_id, ed2.entity_id
HAVING shared_docs >= 1

-- 置信度: min(0.5 + shared_docs * 0.1, 0.9)
```

### 治理规则推理
- L0 层级依赖冲突: L1 项目引用 L3 项目 → 标记 `violates_layer_dependency`
- X4 规则链审计: 未绑定 ADR 的规则 → 标记 `lacks_adr_evidence`

### 去重策略
- 基于标签精确匹配去重 (LOWER(label))
- 合并后保留最高置信度
- 合并别名列表

## 后果

### 正面
- 零 API 成本（纯本地计算）
- 推理速度快（~231 relations/s）
- 可重复执行（幂等）

### 负面
- 准确率低于 LLM 推理（~75% vs ~90%）
- 共现 ≠ 因果（可能引入噪声）
- 需定期清理低置信度关系

## 参考

- Association Rule Mining: Apriori, FP-Growth
- Knowledge Graph Embedding: TransE, RotatE, ComplEx
