---
schema: md/v1
status: completed
lifecycle: history
owner: engineering-agent
last-reviewed: 2026-09-26
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-T3-02 Closeout Retro — 消费回路断在两层：未挂载 + 语料未摄入"
bet_id: BET-Y2Q4-T3-02
created: "2026-09-26"
run_id: 20260926T115016Z-project-code-change-2a698439
---

# BET-Y2Q4-T3-02 Closeout Retro

> **TL;DR**: KOS 复用消费回路端到端验证完成，结论诚实且比预期更深：回路今日
> **不可用于治理知识冷启动**，断点有两层——① kos-mcp 客户端未挂载（服务端已实现于
> kairon）；② 索引 12,553 篇语料里 **workspace 治理知识为 0**（455 ADR 全部未摄入，
> workspace 相关仅 8 篇白皮书）。skill v1.0 引用的三个 MCP 工具名在真实服务端
> **不存在**（按想象 API 编写，从未可执行）。v1.1 已校准至真实状态并补 kos-cli
> 今日可用路径。

## 计划 vs 实际

| 项 | 计划 | 实际 |
|---|---|---|
| 三步端到端留档 | BRIEF 解析 / ADR 命中 ≥3 / 实体样本 | 三步全部执行并留档（docs/reports/kos-reuse-loop-verification-2026-09-26.md）；**ADR 命中如实记 0**（索引无治理语料），实体 63 个已采样 |
| MCP 未挂载处置 | 提案 + skill 更新 | ✅ 且比预案多一层勘误：真实服务端在 `kairon/packages/kos/src/kos/mcp/fastmcp_app.py`（FastMCP kos-mcp），真实工具面 search_knowledge/get_knowledge/get_system_status/list_domains/get_entity/cross_domain_sync |
| skill 与实际一致 | — | ✅ v1.1：真实工具名 + kos-cli 三步（status/search/context）+ 覆盖缺口标注 |

## 关键实证（复算命令在验证报告 §1）

- `kos-cli.py status` → 12,553 docs（索引层健康，T1-04 校准值一致）
- `search "声明 执行鸿沟"` → 10 hits 全个人语料；`search "workflow-scene-map fallback"` → **0**
- `LIKE '%decisions%'` → 18 hits 全外部文件；455 条 workspace ADR **0 入索引**
- `context` 命令正常（LLM-ready JSON）——skill Step 3 即日用它

## 失败与反思

1. **skill 是"写了没跑过"的典型**：v1.0 的三个工具名连服务端都没有——技能沉淀若
   不做端到端验证，沉淀的是幻觉。教训：skill 交付的 done_when 必须含一次真实执行。
2. **"索引 12,553 篇"曾让我（T1-04 期）误判消费闭环只差口径**：数量指标掩盖了
   语料结构缺口——个人语料 99.9%，治理语料 0。数量型指标的反身性再次印证 D6。
3. 诚实关账选择：ADR 命中 ≥3 在本 bet 写面内**不可达成**（摄入被红线禁止），
   按 D1 如实记 0 + 出提案，value 轴 NOT_PROVEN，不换语料凑数。

## 后续（建议归属）

1. **治理语料摄入**（新工单，kairon ingest 通道）：摄入 decisions/retros/patterns/pitfalls
   约 1,100 篇 → 验收 `search_knowledge("ADR-0453")` ≥3 命中。建议挂靠
   KOS-Q-GROWTH-ROLLING 并加"治理语料覆盖率"分指标（防扩量只涨个人语料）。
2. **kos-mcp 挂载**（config 层，owner 执行）：stdio 注册 fastmcp_app 入口；
   建议摄入落地后再挂载，否则挂载后仍是个人语料。
3. CLAUDE.md §1 Startup Protocol 若引用本 skill 三步，需同步 v1.1 工具名（后续 PR）。
