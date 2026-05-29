# 工作区状态

> omostation — Personal AI Operating System
> 最后更新: 2026-05-29

---

## 架构概览

```text
omostation/                        ← 根 git 仓库（starlink-awaken/omostation）
├── projects/kairon/               ← Python monorepo（UV workspace, 17 包）
│   ├── agora                      MCP 服务融合 Hub（65 src .py）
│   ├── agent-runtime              Agent 运行时（7 src .py）
│   ├── codeanalyze                代码/文档分析（63 src .py）
│   ├── core-models                核心数据模型（6 src .py）
│   ├── cron-service               定时任务服务（11 src .py）
│   ├── ecos                       外化认知 OS（18 src .py）
│   ├── eidos                      元模型本体/Schema（28 src .py）
│   ├── forge                      内部工具注册（22 src .py）
│   ├── iris                       知识平台连接器（46 src .py）
│   ├── kos                        知识 OS（63 src .py）
│   ├── kronos                     知识摄取管线（14 src .py）
│   ├── metaos                     元操作系统（27 src .py）
│   ├── minerva                    深度研究系统（63 src .py）
│   ├── ontoderive                 知识工程引擎（src 空, 引擎在 engine/）
│   ├── sophia                     符号化研究范式（9 src .py）
│   ├── ssot                       单一真相源（49 src .py）
│   └── wksp                       CLI 工作台（53 src .py）
│
├── projects/SharedBrain/          ← 数字化生命 OS（83,778 .py 文件）
├── projects/agentmesh/            ← Agent SDK（5,148 .ts 文件）
├── projects/gbrain/               ← 知识脑（1,257 .ts 文件）
├── projects/_archived/            ← 已迁移旧项目归档（22 项）
│
├── AGENTS.md            → 项目治理边界
├── convergence.yaml     → 融合治理状态
├── README.md            → 项目总览
├── Makefile             → 跨项目命令
├── CONTRIBUTING.md      → 贡献指南
├── LICENSE (MIT)        → 开源许可
├── CODE_OF_CONDUCT.md   → 行为准则
│
├── .omo/                → 治理知识库（89 跟踪文件）
└── docker-compose.yml   → 服务编排
```

## 架构演进里程碑

| 阶段 | 日期 | 变更 |
|------|------|------|
| **前身** | ~2026-05-20 | 43+ 独立 git 仓库，硬编码路径耦合 |
| **收敛 1** | 2026-05-24 | 17 个 Python 包合并入 kairon UV workspace monorepo |
| **汇聚 2** | 2026-05-29 | 统一根 repo omostation，projects/ 结构成型，清理 12K+ 行旧文件 |
| **当前** | 2026-05-29 | 5 项目（kairon + SharedBrain + agentmesh + gbrain + _archived），omostation 做统一入口 |

## 关键统计

| 维度 | 数值 |
|------|------|
| 根仓库 | omostation（starlink-awaken/omostation） |
| 嵌入式子仓库 | 5（kairon, SharedBrain, agentmesh, gbrain, _archived） |
| kairon 包数 | 17 |
| kairon 源码 | ~600+ .py 文件（各 packages/*/src/） |
| SharedBrain | 83,778 .py 文件，71K 行 |
| agentmesh | 5,148 .ts 文件，monorepo（7 packages） |
| gbrain | 1,257 .ts 文件 |
| .omo 文件 | 89 跟踪 / 140 磁盘 / 51 忽略 |
| 已归档项目 | 22 项（projects/_archived/） |

## 跨项目通信

```
Kairon (内部 pip 依赖):  UV workspace source dependencies
Kairon → SharedBrain:     CLI subprocess / MCP
Kairon → agentmesh:       MCP / HTTP
agentmesh → gbrain:       Postgres (TypeORM)
SharedBrain → Kairon:     subprocess / hard-coded path（待治理）
```

## 当前焦点

1. **kairon 统一构建/测试** — UV workspace 全量测试
2. **硬编码路径清理** — SharedBrain 中遗留的旧项目绝对路径
3. **.omo 知识库更新** — 已完成 INDEX.md + STATE.md + PROJECTS.yaml + INVENTORY.md + ONBOARDING.md
4. **CI/CD 构建** — sharedbrain-kairon-integration.yml 工作流

## 已知债务

- SharedBrain 部分脚本仍硬编码旧项目绝对路径
- ontoderive 使用 flat 布局（engine/）而非 src/ 布局
- 部分包测试覆盖率不足
- 跨项目集成测试未系统化

---

*维护: 2026-05-29 · 基于 omostation unified repo 架构*
