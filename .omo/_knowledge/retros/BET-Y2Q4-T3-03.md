---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-27
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-T3-03 Closeout Retro — 摄入达成，双库与溯源缺口如实入档"
bet_id: BET-Y2Q4-T3-03
created: "2026-09-27"
run_id: (见 ledger run_ref)
---

# BET-Y2Q4-T3-03 Closeout Retro

> **TL;DR**: 1,038 篇治理语料摄入 KOS（12,553→13,588，双库同步），标题搜索
> "ADR-0453" 命中实证。两个架构级发现：① KOS 双库（KOS_HOME 默认 ~/.kos vs
> 工作区 data/kos）——首轮摄入写错库，复核后双库同摄；② ingest 的 canonical_path
> 不保留目录溯源（kos::default::<文件名>），done_when 字面口径未达成，已提
> metadata source_root 改进提案。

## 计划 vs 实际

| 项 | 结果 |
|---|---|
| 四目录摄入 ≥13,500 | ✅ 13,588（1,038 篇；pitfalls 仅顶层 6 篇——子目录不扫描，工具局限） |
| 治理搜索 ≥3 命中 | ✅ ADR-0453/ADR-0195/P73 命中（标题口径） |
| doc 指向 decisions/ | ⚠️ 字面未达成（canonical_path 无目录溯源）——改进提案入报告 |
| 备份先行 | ✅ 211MB .bak-20260927 |
| 报告 | ✅ docs/reports/kos-governance-ingestion-2026-09-27.md |

## 失败与反思

1. **首轮摄入写错库**（~/.kos 而非 data/kos）："indexed 1,038 但计数不动"暴露双库
   现实。KOS_HOME 契约缺位让"哪个库是权威"处于隐式状态——这本身就是一条待立
   规则（建议进 standards 或 debt）。
2. pitfalls 子目录不扫描：47 篇里只有顶层 6 篇入索引——工具遍历局限，建议
   ingest 支持 rglob（提案）。
3. done_when 写"doc 指向 decisions/"时假设了 canonical_path 保路径——实际通道
   不保。写验收条款前应先实证通道行为（本会话第二次踩"想象 API"坑的变体）。

## 后续

- KOS_HOME 权威性契约（standards/debt 立项）
- ingest source_root 元数据扩展提案（kairon kos 包，另案）
- kos-mcp 挂载（config 层）——双库权威定了之后再挂
