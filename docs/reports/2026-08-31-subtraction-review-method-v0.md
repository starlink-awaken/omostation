---
schema_version: report/v1
lifecycle: history
type: review-material
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
adr: ADR-0443
---

# 减法评审画像方法 v0（含已知缺陷，正式评审仍按 Q4 时机）

## 背景

77 条占位 justification 规则（ADR-0443 v5 首班后实测）。本轮尝试数据驱动
画像挑 8 条最可疑先行评审，**自审不合格降级为方法记录**。

## 画像三维度与实测缺陷

| 维度 | 方法 | 判定 |
|------|------|------|
| fire | governance-history check 名精确匹配 | ⚠️ 对 SSOT/drift 型规则语义偏移（此类规则靠 drift 检查非 fire）|
| refs | rg 搜规则关键词 | ❌ **实现缺陷**：整串搜索（"x4-mesh-executor-reliability"）而非词级——全部 0 命中失真 |
| pitfall 关联 | 词匹配 pitfall 库 | 可用但粒度粗 |

实测：Top 8 全部并列可疑分 6（0 fire / 0 refs）——refs 失真导致并列，
**该信号不可用于评审裁决**。

## Top 8 记录（仅存档，非评审结论）

CR-X4-MESH-EXECUTOR-RELIABILITY / CR-X4-DOC-SSOT / CR-X4-DOC-CLAIMS /
CR-X2-METRIC-TREND / CR-X2-GAC-BOOTSTRAP / CR-X2-FRESHNESS-SSOT /
CR-X1-POLICIES-SSOT / CR-SEC-SENSITIVE-WRITE

## 结论与下一步

1. **正式评审维持 Q4 时机**（ADR-0443 Q14 原决策不变——评审即回填时机）
2. v7+ 画像修复：refs 改词级搜索（复用 v4 symptom_overlap 的 tokenize）；
   fire 维度按 check_type 分流（gate 型看 fire、ssot 型看 drift 记录）
3. 本报告即"没有可信数据不评审"纪律（P95）的执行记录
