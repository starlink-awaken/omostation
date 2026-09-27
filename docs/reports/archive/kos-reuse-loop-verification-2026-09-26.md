---
schema: md/v1
status: completed
lifecycle: history
owner: engineering-agent
last-reviewed: 2026-09-26
type: ephemeral
title: "KOS 复用消费端回路端到端验证与挂载/摄入提案（BET-Y2Q4-T3-02）"
---

# KOS 复用消费端回路端到端验证（2026-09-26）

> BET-Y2Q4-T3-02 交付物。结论先行：**回路今日不可用于治理知识冷启动，断点在两层**——
> ① 客户端未挂载 kos-mcp（服务端已实现）；② 索引语料不含 workspace 治理知识。
> skill 已更新至真实状态（v1.1，kos-cli 路径今日可用），挂载 + 摄入提案见 §3/§4。

## 1. 三步探针实测记录

| 步骤 | 命令 | 实测输出 |
|---|---|---|
| 系统状态 | `kos-cli.py status` | Documents indexed: **12,553** · Domains registered: 0 |
| 检索（治理主题） | `kos-cli.py search "声明 执行鸿沟"` | 10 results —— 全部来自个人语料（eCOS-v5 方案/创作系统等），**0 条 workspace ADR** |
| 检索（workspace 专属词） | `kos-cli.py search "workflow-scene-map fallback"` | **0 results** |
| BRIEF 路径解析 | `sqlite3 ... WHERE canonical_path LIKE '%BRIEF.md%'` | 命中 2 条外部同名文件（skill-video-brief 等），**workspace BRIEF.md 未入索引** |
| ADR 覆盖 | `... WHERE canonical_path LIKE '%decisions%'` | 18 hits 全为外部文件；455 条 ADR **0 条入索引** |
| workspace 语料覆盖 | `... WHERE canonical_path LIKE '%omostation%' OR '%Workspace%'` | **仅 8 篇**（白皮书/架构分析），无 ADR/retro/pattern |
| 实体样本 | `SELECT COUNT(*) FROM kos_entities` | **63**；样本：CARDS / Cockpit-CLI / KOS（system 类 SSOT 实体） |
| context 命令 | `kos-cli.py context "KOS 治理"` | 正常输出 LLM-ready JSON（task/knowledge 分节） |

## 2. kos-mcp 服务端实况（v1.0 skill 勘误依据）

- 实现：`projects/knowledge/kairon/packages/kos/src/kos/mcp/fastmcp_app.py`
  → `FastMCP("kos-mcp")`，依赖 `fastmcp>=2.0`（pyproject 已声明）。
- 真实工具面：`search_knowledge` / `get_knowledge` / `get_system_status` /
  `list_domains` / `get_entity` / `cross_domain_sync`（另有 onto/memory 等经 server.py）。
- **勘误**：v1.0 skill 引用的 `query_custom_sql` / `search_kos` / `list_entities`
  在服务端不存在——skill 文档系按想象 API 编写，从未可执行。

## 3. 挂载提案（需 config 层决策，本 bet 未动手）

1. 在客户端 MCP 配置注册 `kos-mcp`（stdio）：启动命令指向
   kairon kos 包 fastmcp_app 入口（`uv run --project projects/knowledge/kairon ...`）。
2. 注册前先解决 §4 摄入——否则挂载后工具返回的仍是个人语料，冷启动价值有限。
3. 归属：MCP 配置属 `config/**`（机器身份，不在本 bet 写面），需 owner 执行。

## 4. 治理语料摄入提案（消费闭环的第二层断点）

- **对象**：`.omo/_knowledge/decisions/`（455 ADR）＋ `retros/`（550）＋ `patterns/`（37）
  ＋ `pitfalls/`（47），约 1,100 篇治理知识。
- **通道**：kairon kos 包自带 ingest/indexer（`kos-cli.py ingest` / `kos_index_builder.py`），
  增量摄入 workspace 语料（本 bet 红线禁止动索引数据，需独立工单）。
- **验收建议**：摄入后 `search_knowledge("ADR-0453 声明执行鸿沟")` ≥3 命中且
  doc_id 指向 `.omo/_knowledge/decisions/`；BRIEF.md 可被 Step1 解析。
- **挂靠建议**：并入活跃任务 KOS-Q-GROWTH-ROLLING 的 Q4 扩量口径
  （measured_documents 已 12,553，Q4≥3000 floor 早已达成——建议该任务增加
  "治理语料覆盖率" 分指标，防止扩量只涨个人语料）。

## 5. 本次交付清单

- `.agents/skills/kos-cold-start/SKILL.md` → v1.1（真实 API + kos-cli 今日路径 + 缺口如实标注）
- 本验证报告（三步探针输出留档）
- retro：`.omo/_knowledge/retros/BET-Y2Q4-T3-02.md`

**诚实声明**：done_when 的「ADR 命中 ≥3」今日不可达成（索引层缺口），
按 D1 如实记录 0 命中而非换语料凑数；价值轴 NOT_PROVEN，消费价值待摄入落地后复验。
