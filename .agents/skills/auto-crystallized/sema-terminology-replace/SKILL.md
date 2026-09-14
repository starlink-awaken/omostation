---
name: sema-terminology-replace
description: 术语统一：「高度重视」应替换为署名偏好用语
metadata:
  node_type: skill
  origin: sema-crystallizer
  trigger_key: "terminology_replace:\u9ad8\u5ea6\u91cd\u89c6"
  evidence_count: 2
  created: 2026-09-06
---

# 术语统一：「高度重视」应替换为署名偏好用语

## 触发条件

起草/修订公文与技术文档时，当出现与以下模式匹配的内容即应触发本技能：

- 模式: `高度重视`
- 类型: `terminology_replace`
- 证据: 2 次同类人工纠偏（sample ids: buf-doc-review-1, buf-doc-review-2）

## 操作步骤

1. 定位草稿中匹配该模式的内容。
2. 按terminology_replace语义处理：
   按署名偏好改写并复核上下文衔接。
3. 输出前自检：全文不再命中该模式。

## 反例（不应发生）

- 草稿包含 `高度重视` 却未处理即提交署名流程。
- 处理后引入新的同类模式（应再次触发结晶）。

## 依据

由 SEMA 结晶管线自 signature_diff 事件自动生成（BET-Y2Q2-T6-01）。
