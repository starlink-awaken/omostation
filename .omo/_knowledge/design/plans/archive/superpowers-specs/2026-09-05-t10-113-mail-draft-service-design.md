---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q3-T10-113
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T10-113 企业邮箱智能拟复与附件解析服务设计

## 1. 目标

提供 `bos://inbox/mail/draft` 标准服务：输入邮件正文与可选附件，输出
3 档拟复方案（简要确认 / 详尽批复 / 委婉谢绝），并支持表格类附件的
结构化 Markdown 提取。

## 2. In scope

1. `projects/agora/src/agora/server/tools_bos/mail.py`（新文件）：
   - `draft_three_tiers(body, context) -> dict`：3 档草稿生成器
     （brief/verbose/polite），文风约束来自 replay buffer 署名样本。
   - `extract_tables(attachment) -> markdown`：CSV/HTML 表格附件 →
     Markdown 表格还原（≥90% 结构还原度以行列数与单元格内容比对断言）。
   - BOS 工具注册与 `bos://inbox/mail/draft` 路由面。
2. `projects/cockpit/src/cockpit/commands/inbox.py`（新文件）：
   - `cockpit inbox draft` 命令：调用 BOS 服务，展示 3 档草稿。
3. 测试：3 档生成结构断言、表格还原度断言、BOS 路由契约测试。

## 3. Out of scope

- 不接真实 SMTP/IMAP 凭据（监听与发送通道属 T10-116 外发面）；
  服务以函数面 + BOS 路由为交付，邮件源注入为测试桩。
- PDF/Word 二进制解析不在本 bet（表格先覆盖 CSV/HTML 两类）。

## 4. 验收（对齐 ledger done_when）

1. `bos://inbox/mail/draft` 服务契约可调用，3 档草稿结构完整。
2. 表格附件 Markdown 还原度 ≥90%（行列/单元格断言）。
3. 单测全部通过。
