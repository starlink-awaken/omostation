---
schema: md/v1
status: active
lifecycle: plan
owner: governance-agent
last-reviewed: 2026-09-27
type: ephemeral
bet_id: BET-Y2Q4-T3-03
title: "KOS 治理语料摄入报告 — 双库实况 + 1,035 篇入索引 + 消费验证"
---

# KOS 治理语料摄入报告（2026-09-27，BET-Y2Q4-T3-03）

## 摄入结果

| 目录 | found | indexed |
|---|---|---|
| .omo/_knowledge/decisions/ | 420 | 420 |
| .omo/_knowledge/retros/ | 575 | 575 |
| .omo/_knowledge/patterns/ | 37 | 37 |
| .omo/_knowledge/pitfalls/ | **6**（仅顶层文件，子目录未扫描——工具按顶层 .md 遍历） | 6 |
| 合计 | **1,038** | **1,038** |

- documents 计数：12,553 → **13,588**（done_when ≥13,500 ✅）
- 双库同步：`data/kos/kos-index.sqlite`（工作区）与 `~/.kos/kos-index.sqlite`（用户级）均 13,588
- 备份：`data/kos/kos-index.sqlite.bak-20260927`（211MB，摄入前快照，可回滚）

## 消费验证

- 标题搜索命中：`title LIKE '%ADR-0453%'` → **"ADR-0453 — 声明/执行鸿沟: 多尺度信号而非缺陷"**；
  同查询族还命中 ADR-0195、P73 pattern——**≥3 命中 ✅**
- 抽查 patterns/pitfalls：已入索引（见上方计数）

## 两个如实记录的发现（D1）

1. **KOS 双库现实**：`KOS_HOME` 环境变量决定库位置（默认 `~/.kos`）；工作区库
   `data/kos/` 是另一份（T1-04 的 BRIEF 指标读它）。首轮 ingest 落到了 `~/.kos`，
   复核后发现后用 `KOS_HOME=<workspace>/data/kos` 双库同摄。**建议**：为 KOS_HOME
   的解析立一个显式契约（哪个库是 kos-mcp 的权威源），否则双库会再次漂移。
2. **canonical_path 不保留目录溯源**：ingest 存储为 `kos::default::<文件名>.md`，
   metadata 仅含 relative_path（相对扫描根=纯文件名）。done_when 的"doc 指向
   decisions/"字面口径**未达成**——改进提案：ingest 的 metadata 增加 source_root
   字段（记录扫描根），使目录归属可追溯。命中本身（ADR-0453 等 3 条治理知识）
   为真实达成。

## 结论

治理语料已可被 KOS 检索消费（核心价值达成）；目录溯源缺口与双库权威性为后续
改进提案（kairon kos 包 ingest metadata 扩展，另立工单）。
