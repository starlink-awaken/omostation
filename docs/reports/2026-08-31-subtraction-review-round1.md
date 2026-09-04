---
schema_version: report/v1
lifecycle: history
type: review-evidence
owner: governance-team
created: 2026-08-31
last_updated: 2026-08-31
adr: ADR-0443
supersedes: docs/reports/2026-08-31-subtraction-review-method-v0.md
---

# 减法评审第一轮（真执行版）

## 方法修复（supersede v0 报告的缺陷）

| v0 缺陷 | v1 修复 | 结果 |
|----------|---------|------|
| refs 整串搜索全 0 | 词级 tokenize（len≥4 + 通用词降噪）+ rg 多词 OR | Top10 全部 refs=68~1283 |
| fire 对 SSOT 型语义偏移 | 评分权重调整：refs 缺失（3 分）> fire=0（2 分），fire 对 drift 型标注"非活性指标" | 可疑分有区分度 |

## 评审结论（诚实版）

**77 条占位 justification 规则：零 retire。**

修复后的画像推翻了 v0 的"可疑 Top 8"假象——词级搜索证明每条规则都有活跃代码
引用（最低 67 处，最高 1283 处）。fire=0 对 ssot_pointer/drift_audit 型规则不是
死信号（它们的执行形态是 drift 检测，不是 fail fire）。

**数据不支持的删除一条都不删**——这正是 v3 确立的"删之前先证明"纪律的反向应用：
**不删之前也要先证明可删**。

## 执行记录

- Top 10 justification 证据化回填（含 refs 计数+样本路径+fire 说明），review_before
  以评审日重起（2026-11-29）——评审即回填时机（Q14 原决策兑现）
- 剩余 67 条保持占位（未评不填——诚实原则），下轮入口：批量画像回填或随触发评审

## Top 10 回填清单

CR-M0-STAGE-GATE / CR-L0-BOS-RESOLVE / CR-X2-GAC-DRIFT / CR-X1-AGENT-AUDIT /
CR-L3-COCKPIT-ENTRY / CR-L2-DIRECT-IO / CR-X4-DOC-SSOT / CR-L0-PROTOCOLS-SSOT /
CR-X2-GAC-BOOTSTRAP / CR-X2-GOVERNANCE-SEMANTIC-GATE
