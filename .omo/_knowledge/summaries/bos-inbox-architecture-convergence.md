---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-18
type: ephemeral
status: archived
---
# BOS Inbox 多源私有知识神经网：架构收敛与双端落地总结

> **日期**: 2026-07-31  
> **领域**: Architecture Convergence / BOS Neural Mesh / Agora MCP / Cockpit CLI  
> **详细完整报告**: [BOS Inbox 架构整合与实证报告](../../../docs/reports/2026-07-31-BOS-INBOX-ARCHITECTURE-INTEGRATION-REPORT.md)  

## 1. 核心概述
针对早期散乱的个人/微信/办公助手采集脚本带来的数据碎片化与无鉴权直接调用的架构问题，实施了一揽子整合与规范接入：
- **数据面**：以 `_inbox/` 与 `@公共/_runtime/` 作为物理存储标准，收敛致远 OA、网易邮箱大师、Apple Mail 的待办快照与嵌入式向量库。
- **路由面**：通过 `bos://memory/inbox/{status|search|pending}` 进行语义寻址；修复了 `BOSRouter.seed_from_poc` 解析字典列表项时的属性读取缺陷（`getattr` vs `dict.get`）。
- **服务面 (Agora MCP)**：新增 top-level 异步方法 `bos_inbox_status()`, `bos_inbox_search()`, `bos_inbox_pending()`，通过 `mcp.tool()` 向大模型暴露。
- **控制面 (Cockpit CLI)**：落地 `cockpit bos inbox status|search|pending` 交互指令，支持终端表格与 Markdown 待办公文概览。

## 2. 实证与验收结果
- **全量测试通过**：`pytest projects/agora/tests/test_bos_inbox_mcp.py -v` (3/3 All Green)。
- **物理终端交互**：已通过真机终端验证 `cockpit bos inbox status` 呈现正确的来源统计，以及 `cockpit bos inbox pending --source seeyon_oa` 呈现真实的公文流转属性（AffairID, SummaryID, 拟稿人）。

## 3. 下一步建议
1. 建立自动切块嵌入程序，将新入库待办自动推送至 `vector_store.json`；
2. 按 CR-DOMAIN-AUTH-01 从默认放行向细粒度角色与域鉴权演进。
