# INDEX-PROJECTS.md — 项目索引

> **维护规则**
> - owner: governance-team
> - trigger: 新项目加入 / 项目归档 / 层级变更
> - method: 脚本生成 (bin/ssot/gen-projects-index.py)
> - validation: 与 project-registry.yaml 项目数一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: 2026-07-14T07:22:23.729246

---

## 按层分类

| 层 | 项目 | 栈 | 入口文档 |
|----|------|-----|---------|
| I0 | agora | Python (uv, pytest) | 各项目 `AGENTS.md` |
| L0 | ecos | Python (uv, pytest) | 各项目 `AGENTS.md` |
| L1 | runtime | Python (uv, pytest) | 各项目 `AGENTS.md` |
| L1-L3 | toolbox | Multi (TypeScript MCP / JS Skills / Python CLI) | 各项目 `AGENTS.md` |
| L2 | family-hub, gbrain, kairon, metaos, omo, omo-debt | Python (FastMCP) + Python (uv, pytest) + TypeScript (bun) | 各项目 `AGENTS.md` |
| L3 | cockpit, cockpit-ui | Python (uv, pytest) + TypeScript (Vite, React) | 各项目 `AGENTS.md` |
| L4 | l4-kernel | Python (uv, pytest) | 各项目 `AGENTS.md` |
| M0 | model-driven | Python (uv, pytest) | 各项目 `AGENTS.md` |
| X | aetherforge, bus-foundation, c2g, observability | Docker + Python (uv) + Python (uv, pytest) | 各项目 `AGENTS.md` |

---

## 按栈分类

| 栈 | 项目 |
|----|------|
| Docker | observability |
| Multi (TypeScript MCP / JS Skills / Python CLI) | toolbox |
| Python (FastMCP) | family-hub |
| Python (uv) | c2g |
| Python (uv, pytest) | aetherforge, agora, bus-foundation, cockpit, ecos, kairon, l4-kernel, metaos, model-driven, omo, omo-debt, runtime |
| TypeScript (Vite, React) | cockpit-ui |
| TypeScript (bun) | gbrain |

---

## 项目清单

### Python (uv) 项目

| 项目 | 层 | 角色 | AGENTS.md |
|------|----|------|-----------|
| aetherforge | X | 能力与算力框架 (gateway/mesh/swarm) | ✅ |
| agora | I0 | MCP Hub · BOS URI 路由 | ✅ |
| bus-foundation | X | Omni-Bus (Data/Event/Control) | ✅ |
| c2g | X | 战略需求引擎 (V2P → C2G) | ✅ |
| cockpit | L3 | 统一入口 (CLI + MCP + Web) | ✅ |
| ecos | L0 | SSB 签名链 + MOF 元模型 + L0 约束 | ✅ |
| family-hub | L2 | 家庭数字枢纽 | ✅ |
| kairon | L2 | 知识引擎 monorepo | ✅ |
| l4-kernel | L4 | 自我层管理面 · 域统一注册 · KEMS | ✅ |
| metaos | L2 | 编排引擎 · 决策门控/免疫/路由 | ✅ |
| model-driven | M0 | 生命周期横切框架 · M3→M2→M1 桥接 | ✅ |
| omo | L2 | 治理中枢 · Agent OS 内核 | ✅ |
| omo-debt | L2 | 技术债务评分 CLI | ✅ |
| runtime | L1 | 运行时 · Matrix/Scheduler/KEI 沙箱 | ✅ |
| toolbox | L1-L3 | 本地服务入口 — L1 寻址 / L2 分区 / L3 实例 (MCP / Skill / CLI) | ✅ |

### TypeScript (bun) 项目

| 项目 | 层 | 角色 | AGENTS.md |
|------|----|------|-----------|
| cockpit-ui | L3 | Web 控制台 UI (作为 cockpit 前端表现层挂载至/) | ✅ |
| gbrain | L2 | Postgres 知识数据库 | ✅ |

### Docker 项目

| 项目 | 层 | 角色 | AGENTS.md |
|------|----|------|-----------|
| observability | X | Langfuse 可观测性 | ✅ |

---

## 归档项目参考

| 项目 | 合并到 | 说明 |
|------|--------|------|
| compute-mesh | aetherforge/packages/mesh |  |
| swarm-engine | aetherforge/packages/swarm |  |
| hermes-console | cockpit-ui |  |
| agora-dashboard | cockpit HTTP :8090 |  |

---

## 说明

> 数据来源: `docs/project-registry.yaml` + 扫描 `projects/*/` 目录
> 
> 本索引文件只包含指针，不持有任何硬编码数值（数值以 `project-registry.yaml` 为准）
> 
> 完整的项目元数据请见: `docs/project-registry.yaml`
