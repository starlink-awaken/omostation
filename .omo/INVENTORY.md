# Workspace 项目资产清单

> 生成: 2026-05-29（基于 omostation unified repo 架构重写）
> 架构: 根仓库 omostation + 5 嵌入式子仓库

---

## 概览

| 维度 | 数值 |
|------|------|
| 根仓库 | omostation（starlink-awaken/omostation） |
| 嵌入式子仓库 | 5（kairon, SharedBrain, agentmesh, gbrain, _archived） |
| kairon Python 包 | 17 |
| SharedBrain Python | ~83,778 .py 文件 |
| agentmesh TypeScript | ~5,148 .ts 文件 |
| gbrain TypeScript | ~1,257 .ts 文件 |
| .omo 跟踪文件 | 89 |
| 已归档旧项目 | 22 |

---

## 一、kairon — 知识工程与研究栈（17 包 monorepo）

> 位置: `projects/kairon/`
> 构建: UV workspace + hatchling
> 源码布局: `src/<package>/`（除 ontoderive 使用 flat 布局）

### 1.1 运行时与基础设施

| 包 | 源码 | 状态 | 说明 |
|----|------|------|------|
| **agora** | 65 src .py | active | MCP 服务融合 Hub（pipeline/eventbus/路由/监控） |
| **agent-runtime** | 7 src .py | active | Agent 运行时环境 |
| **cron-service** | 11 src .py | active | 定时任务服务 |
| **wksp** | 53 src .py | active | 统一 CLI 工作台（研究对象管理 + MCP） |

### 1.2 知识工程核心

| 包 | 源码 | 状态 | 说明 |
|----|------|------|------|
| **ontoderive** | engine/ (~127 .py) | active | 事实驱动知识工程引擎（渊衍框架 v3.6.4） |
| **eidos** | 28 src .py | active | 元模型本体建模 / Schema 验证 |
| **sophia** | 9 src .py | active | 符号化研究范式引擎 v0.2.1 |
| **ssot** | 49 src .py | active | 单一真相源（配置/状态管理） |

### 1.3 研究与分析

| 包 | 源码 | 状态 | 说明 |
|----|------|------|------|
| **minerva** | 63 src .py | active | 本地优先深度研究系统（5 MCP tools） |
| **codeanalyze** | 63 src .py | active | 代码与文档分析工具集 |
| **iris** | 46 src .py | active | 个人知识平台连接器 Hub |

### 1.4 操作系统层

| 包 | 源码 | 状态 | 说明 |
|----|------|------|------|
| **kos** | 63 src .py | active | 知识操作系统 CLI（26 MCP tools） |
| **metaos** | 27 src .py | active | 元操作系统引擎 v7.1（9 MCP tools） |
| **ecos** | 18 src .py | active | 外化认知操作系统 v0.6.0 |

### 1.5 工具与通用

| 包 | 源码 | 状态 | 说明 |
|----|------|------|------|
| **forge** | 22 src .py | active | 内部工具注册与发现 |
| **kronos** | 14 src .py | active | 知识摄取管线 |
| **core-models** | 6 src .py | active | 核心数据模型定义 |

---

## 二、SharedBrain — 数字化生命 OS

| 属性 | 值 |
|------|-----|
| **位置** | `projects/SharedBrain/` |
| **规模** | ~83,778 .py 文件 |
| **入口** | `conductor` CLI |
| **技术栈** | FastAPI / uvicorn / Python |
| **关键目录** | conductor/, nucleus/, organs/, memory/, analysis/, forge-mcp/ |
| **状态** | 生产稳定 |

---

## 三、agentmesh — 多 Agent SDK（TypeScript monorepo）

| 属性 | 值 |
|------|-----|
| **位置** | `projects/agentmesh/` |
| **规模** | ~5,148 .ts 文件 |
| **运行时** | bun |
| **包数** | 7（core-types, model-orchestrator, gateway, engine, toolkit, server, cli） |
| **入口** | `agentmesh` CLI, HTTP :3000, MCP stdio |
| **状态** | 最活跃（持续提交） |

---

## 四、gbrain — 知识脑

| 属性 | 值 |
|------|-----|
| **位置** | `projects/gbrain/` |
| **规模** | ~1,257 .ts 文件 |
| **运行时** | bun |
| **数据库** | Postgres（TypeORM） |
| **状态** | 活跃 |

---

## 五、已归档（projects/_archived/）

| 项目 | 原位置 | 归档原因 |
|------|--------|----------|
| AggreResearch | `_archived/ecosystem/` | 功能被 minerva 覆盖 |
| hermes-agent-self-evolution | `_archived/ecosystem/` | 功能合并 |
| crush | `_archived/` | — |
| gstack_old | `_archived/` | 被 gstack 替代 |
| +18 其他 | `_archived/` | 迁移/清理 |

---

## 六、目录规范

```
omostation/
├── .omo/                    # 治理知识库
├── projects/
│   ├── kairon/              # Python monorepo（17 包）
│   │   └── packages/<name>/
│   ├── SharedBrain/         # 数字化生命 OS
│   ├── agentmesh/           # Agent SDK
│   ├── gbrain/              # 知识脑
│   └── _archived/           # 旧项目备份
├── README.md                # 项目总览
├── AGENTS.md                # 项目治理边界
├── Makefile                 # 跨项目命令
├── docker-compose.yml       # 服务编排
├── convergence.yaml         # 融合治理状态
├── CONTRIBUTING.md          # 贡献指南
├── CODE_OF_CONDUCT.md       # 行为准则
└── LICENSE                  # MIT
```

---

## 七、重点债务

1. SharedBrain 中遗留硬编码旧项目绝对路径（如 `/Users/xiamingxing/Workspace/Forge/`）
2. ontoderive 使用 flat 布局（engine/），未迁移到 src/ 布局
3. 部分 kairon 包测试覆盖率 < 50%
4. 跨项目集成测试未系统化

---

*维护: 2026-05-29 · 反映 omostation + kairon monorepo 架构*
