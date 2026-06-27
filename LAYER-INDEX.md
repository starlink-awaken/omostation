# LAYER-INDEX.md — 5+4+1+1 项目分层索引

> 基于 eCOS v6 架构 (5 层 L0-L4 + 4 维 X1-X4 + 1 织 I0 + 1 横切 M0) · 2026-06-27 · 17 项目 · 16 包
> 运行时状态 (Phase/健康分/任务数) 见 `.omo/state/system.yaml`，不在此硬编码

## I0 — 集成织层

| 项目 | 角色 | 端口 | 状态 |
|------|------|------|------|
| **agora** | MCP 服务发现 + 代理 + 断路器 | 7422 (HTTP), 7431 (SSE) | 🟢 运行中 · 100 BOS 声明式服务 |

## L0 — 协议编织

| 项目 | 位置 | 说明 |
|------|------|------|
| **protocols** | `protocols/` | 16 协议 YAML + 端口注册表 |
| **ecos** | `projects/ecos/` | SSB 签名链 + 涌现计算 · MOF + L0 约束 |

## L1 — 运行时基础设施

| 项目 | 位置 | 核心模块 | 状态 |
|------|------|---------|------|
| **runtime** | `projects/runtime/` | Matrix 注册表 · 健康监控 · KEI 沙箱 · Scheduler | 🟢 |

## L2 — 内核三平面

### 治理面
| 项目 | 位置 | 说明 |
|------|------|------|
| **omo** | `projects/omo/` | Phase 管理 · 债务追踪 · 状态管理 |

### 引擎面 (kairon · 16 包)
| 领域 | 包 |
|------|-----|
| 知识查询 | eidos · kos · minerva |
| 知识推导 | ontoderive · sophia · kronos |
| 知识存储 | iris |
| 工具注册 | forge · codeanalyze |
| 数据模型 | core-models |
| 支撑 | health-profile · kairon-lib-events · kairon-observability · kairon-pipeline · kairon-plugin-sdk · kairon-utils |

### 记忆面
| 项目 | 位置 | 说明 |
|------|------|------|
| **gbrain** | `projects/gbrain/` | TypeScript · Postgres 知识脑 |

### 编排
| 项目 | 位置 | 说明 |
|------|------|------|
| **metaos** | `projects/metaos/` | 决策门控 · 免疫监控 · 路由 |

## L3 — 统一入口

| 项目 | 位置 | 说明 | 接口 |
|------|------|------|------|
| **cockpit** | `projects/cockpit/` | Agent 桥接层 · CLI + MCP + Web | CLI 18 · MCP 20 · HTTP 8090 |

## L4 — 自我层 (管理面 + 数据面)

### 管理面

| 项目 | 位置 | 说明 | 接口 |
|------|------|------|------|
| **l4-kernel** | `projects/l4-kernel/` | 21域统一注册 · KEMS六面 · 跨域场景 · 联邦 | CLI + MCP 43 tools (:7455) + Python API |

### 数据面 (21域)

| 域 | 路径 | 类型 | bos:// URI |
|----|------|------|------------|
| **驾驶舱** | `~/Documents/@驾驶舱/` | DocumentDomain | `bos://cockpit/` |
| **学习进化** | `~/Documents/@学习进化/` | DocumentDomain | `bos://vault/` |
| **个人** | `~/Documents/@个人/` | DocumentDomain | `bos://personal/` |
| **公共** | `~/Documents/@公共/` | DocumentDomain | `bos://shared/` |
| **家庭生活** | `~/Documents/@家庭生活/` | DocumentDomain | `bos://family/` |
| **卫健委** | `~/Documents/@工作文档/卫健委` | DocumentDomain | `bos://work-weijian/` |
| **国转中心** | `~/Documents/@工作文档/国转中心` | DocumentDomain | `bos://work-guozhuan/` |
| **Obsidian Vault** | `~/Library/Mobile Documents/iCloud~md~obsidian/Documents` | DocumentDomain | `bos://obsidian-vault/` |
| **AI 配置** | `~/.ai` | ConfigDomain | `bos://ai-config/` |
| **Agent 配置** | `~/.agents` | ConfigDomain | `bos://agents-config/` |
| **iCloud 共享** | `~/SharedConf` | ConfigDomain | `bos://icloud-sharedconf/` |
| **Minerva 引擎** | `~/minerva` | EngineDomain | `bos://minerva/` |
| **Knowledge 引擎** | `~/knowledge` | EngineDomain | `bos://knowledge/` |
| **L4 Kernel** | `~/Workspace/projects/l4-kernel` | EngineDomain | `bos://l4-kernel/` |
| **脚本工具** | `~/bin` | ToolDomain | `bos://bin/` |
| **工具箱** | `~/ToolBox` | ToolDomain | `bos://toolbox/` |
| **共享工作** | `/Users/SharedWork` | WorkspaceDomain | `bos://sharedwork/` |
| **共享磁盘** | `/Volumes/SharedDisk` | StorageDomain | `bos://shareddisk/` |
| **模型卷** | `/Volumes/Model` | ModelDomain | `bos://model-volume/` |
| **共享模型** | `/Volumes/SharedModel` | ModelDomain | `bos://sharedmodel/` |
| **eCOS Workbench** | `~/Workspace` | WorkspaceDomain | `bos://ecos/` |
| **Vault** | `~/Documents/@学习进化/` | 方法论 + 洞察 + 经验 (Obsidian 知识库) | `bos://vault/` |
| **Personal** | `~/Documents/@个人/` | 个人档案 | `bos://personal/` |
| **Family** | — | 家庭生活 | — |
| **Shared** | — | 共享工作空间 | — |
| **SharedWork** | — | 共享工作文档 | — |
| **SharedDisk** | — | 共享存储盘 | — |
| **Work-Weijian** | — | 卫健工作 | — |
| **Work-Guozhuan** | — | 国转工作 | — |
| **AI-Config** | — | AI 配置 | — |
| **Obsidian-Vault** | — | Obsidian 移动端 | — |
| **iCloud-SharedConf** | — | iCloud 共享配置 | — |

**原则**: L4 通过 l4-kernel 管理面提供统一操作接口。Agent 通过 l4-kernel MCP Server (43 tools, :7455) 或 cockpit MCP 访问 L4 数据。L4 域模型定义在 L0 MOF `ecos/src/ecos/ssot/mof/m1/domain/`。

---

## X 轴保障体系 (贯穿所有层)

| 切面 | 定义 | 原则 |
|------|------|------|
| **X1 审计链** | 操作是否安全 | 沙箱拦截 · 认证鉴权 · 操作审计 |
| **X2 抗熵** | 数据是否新鲜 | 健康监控 · 自愈 · 过期检测 |
| **X3 价值栈** | 投入是否合理 | 成本追踪 · 优先级驱动 |
| **X4 一致性** | 规则是否被遵守 | CLI/端口/依赖/文档/CI/Phase 全量检查 |

**实现注册表**: `.omo/_knowledge/management/x-axis-implementation-registry.md`
**加入原则**: 新机制 → X1-X4 归类 → 注册到实现表 → CI → Memory

---

## 术语消歧

本工作区存在三种 "workflow" 概念，按上下文区分：

| 术语 | 含义 | 位置 |
|------|------|------|
| **lifecycle stage** | model-driven 7 阶段生命周期引擎 (M0) | `projects/model-driven/src/model_driven/mof/m3_extended.py` + `ecos/m1/lifecycle/` |
| **execution DAG** | M1 执行编排工作流 (29 个 WORKFLOW-*.yaml) | `ecos/src/ecos/ssot/mof/m1/workflow/` |
| **CI workflow** | GitHub Actions 工作流 | `.github/workflows/*.yml` |

文档中 "workflow" 不带限定词时，按上下文判断；新建文档应使用上表限定词。

---

*架构定义完成。实现细节见注册表。最后更新: 2026-06-28*
