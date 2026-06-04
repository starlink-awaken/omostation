# 架构健康快照 — Phase 16 完成后

> 日期: 2026-06-03
> 生成者: 架构分析与债务治理规划
> 基线: `.omo/diagrams/4-plus-1-3-architecture.md`, `LAYER-INDEX.md`

---

## 执行摘要

| 维度 | 评分 | 说明 |
|------|:----:|------|
| P0 产品层 | 🔴 **F** | hermes-webui 未运行；pallas/gstack/bos-skill-cli 不存在 |
| I0 路由层 | 🟡 **C** | Agora 代码完整但服务未启动；端口无监听 |
| L1-L4 能力层 | 🟢 **A** | 33 包 ruff 全绿；测试覆盖良好；仅 2 包零测试 |
| X1 治理层 | 🟢 **A-** | CI/备份/.omo 测试完整；无 freshness 脚本 |
| X2 抗熵层 | 🟡 **B** | 备份存在但无自动 freshness cron |
| X3 价值层 | 🟡 **B** | Provenance chain 有 evidence 目录但需人工确认活跃度 |
| 文档一致性 | 🔴 **D** | LAYER-INDEX 与实际状态多处不符 |

**综合评分: C+** — 核心能力层健康，但产品表面层和文档准确性是严重短板。

---

## 逐层详情

### P0 — 产品交互层

| 组件 | LAYER-INDEX 声称 | 实际状态 | 偏差 |
|------|-----------------|----------|------|
| hermes-webui | 端口 8787 | **端口未监听** | 🔴 |
| pallas | 7 CLI commands | **kairon 中不存在** | 🔴 |
| gstack | 10 orchestrators | **kairon 中不存在** | 🔴 |
| bos-skill-cli | Skill TUI | **kairon 中不存在** | 🔴 |

**实际存在的 P0 入口**：
- `projects/hermes-console/` — Hermes 控制台（目录存在，状态未知）
- `.hermes/hermes-agent/` — Hermes Agent 适配器
- `obsidian-claude-code-mcp/` — Obsidian MCP 集成（有 UI 目录）

**结论**: P0 层在 4+1+3 架构图中定义的四个组件全部缺失或不活跃。产品表面层是 Phase 16 主题（Knowledge Capture/Search Product Surface Convergence）的核心，但基础设施入口未就绪。

### I0 — 路由层

| 组件 | LAYER-INDEX 声称 | 实际状态 | 偏差 |
|------|-----------------|----------|------|
| agora | 🟢 运行中 (7430/7431) | **端口未监听** | 🔴 |
| agora-mcp | 🟢 运行中 (7423) | 未验证 | 🟡 |

**代码健康**: Agora 包代码完整（app.py, cli.py, 49 个测试），配置文件存在（agora-services.json, agora-routes.json 等）。

**结论**: Agora 作为代码库是健康的，但作为运行时服务未启动。LAYER-INDEX 的 🟢 状态是过时的。

### L1 — 契约层

| 包 | 测试数 | ruff | 状态 |
|----|:------:|:----:|------|
| eidos | 19 | 0 | 🟢 |
| ssot | 11 | 0 | 🟢 |
| pipeline:json | 间接测试 | — | 🟢 |

**问题**: 全部 33 个包**没有包级 AGENTS.md**。根目录 AGENTS.md 和项目级 AGENTS.md 存在，但包级开发者指南缺失。

### L2 — 能力层

| 包 | 测试数 | ruff | 状态 |
|----|:------:|:----:|------|
| ontoderive | 50 | 0 | 🟢 |
| minerva | 34 | 0 | 🟢 |
| sophia | 6 | 0 | 🟢 |
| forge | 11 | 0 | 🟢 |
| kos | 24 | 0 | 🟢 |
| kronos | 9 | 0 | 🟢 |
| iris | 10 | 0 | 🟢 |
| codeanalyze | 13 | 0 | 🟢 |
| metaos | 3 | 0 | 🟢 |
| gc-engine | 2 | 0 | 🟢 |

**零测试包（风险）**:
- `sharedbrain-standalone` (0 tests) — 分解后的残留包
- `wksp` (0 tests) — workspace CLI 工具

### L3 — 协作层

| 组件 | 状态 | 证据 |
|------|------|------|
| KOS collab (TaskObject CRUD) | 🟢 | 24 个测试通过 |
| phase-lock (EG5) | 🟢 | .omo 测试覆盖 |
| PipelineTracer | 🟢 | .omo evidence/ 存在执行记录 |

### L4 — 自我层

| 组件 | 状态 | 证据 |
|------|------|------|
| KOS self | 🟡 | 代码存在，需确认认知 KB 有有效数据 |
| metacog | 🟡 | 代码存在，需确认运行时数据 |

### X1 — 治理层

| 组件 | 状态 | 证据 |
|------|------|------|
| arcnode (17 constraints) | 🟢 | `.omo/standards/` 存在 |
| CI (pre-commit + Actions) | 🟢 | 10 个 workflows 存在 |
| dashboard (42 constraints) | 🟡 | `scripts/` 中有检查脚本，但未确认全部 42 条 |
| Agora (27 MCP + degrade) | 🟡 | 代码存在，服务未运行 |
| Security (fail-closed) | 🟢 | `.github/workflows/security.yml` 等存在 |

### X2 — 抗熵层

| 组件 | 状态 | 证据 |
|------|------|------|
| freshness cron | 🔴 | **无专门 freshness 脚本** |
| backup cron (43 files) | 🟢 | `scripts/daily-backup.sh` 存在 |
| zombie audit | 🟢 | `.omo/debt/` 机制运行中 |

### X3 — 价值层

| 组件 | 状态 | 证据 |
|------|------|------|
| KOS consensus (L1/L2/L3) | 🟡 | 代码存在，需验证运行时共识 |
| PipelineTracer | 🟢 | evidence/ 目录有 phase 执行记录 |
| provenance_chain | 🟡 | `.omo/evidence/` 存在但需结构化验证 |

---

## 关键不一致（LAYER-INDEX vs 实际）

| 条目 | LAYER-INDEX | 实际 | 严重度 |
|------|-------------|------|--------|
| Agora 运行状态 | 🟢 运行中 | 端口未监听 | 🔴 高 |
| SharedBrain organs | 🟢 19 organs, 4 delegated | organs/ 目录不存在（已归档） | 🔴 高 |
| SharedBrain D-Memory | 🟢 运行时记忆 | organs 已删除 | 🟡 中 |
| SharedBrain D-Harvest | 🟢 delegated | organs 已删除 | 🟡 中 |
| P0 组件存在性 | 列出 4 个 | 实际不存在或不活跃 | 🔴 高 |

**建议**: LAYER-INDEX.md 需要一次全面更新，或添加 "最后验证时间" 字段以避免状态漂移。

---

## 最近活跃度

| 项目 | 最近提交 | 说明 |
|------|----------|------|
| kairon | 2026-06-03 (omo live overlay) | 非常活跃 |
| kairon | 2026-06-02 (assistant, voice, billing 包) | 新增 5 个 governed 包 |
| agentmesh | 2026-05-28 | 自动提交 |
| gbrain | 2026-05-24 | schema packs |

---

*生成时间: 2026-06-03T14:50:00+08:00*
*验证命令: `lsof -i :7430`, `ls packages/*/AGENTS.md`, `ruff check packages/ --statistics`*
