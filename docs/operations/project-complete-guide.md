---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-31
review-state: metadata-only
metadata-migrated-at: 2026-07-31
type: ssot
last_updated: 2026-09-03
---
# omostation / eCOS v6 项目全景手册

> 本文是项目级总览与使用入口。稳定架构看 [`ARCHITECTURE.md`](../ARCHITECTURE.md)，项目元数据看 [`project-registry.yaml`](project-registry.yaml)，运行态看 [`.omo/state/system.yaml`](../.omo/state/system.yaml)，端口看 [`protocols/port-registry.yaml`](../protocols/port-registry.yaml)。本文不复制这些文件中的易变数量、端口和健康分数。

## 1. 项目是什么

omostation 是 eCOS v6 的多项目工作区，目标是把知识、Agent、治理、运行时和个人/家庭工作流收敛到一套可观察、可审计、可持续演进的系统中。

它解决的不是单一业务问题，而是四类连续问题：

1. **理解**：从代码、文档、外部资料和事件中形成可检索知识。
2. **决策**：把意图、提案和战略目标转成受治理的任务与执行计划。
3. **执行**：通过运行时、算力网格和工具能力完成工作。
4. **证明**：记录状态、验证、审计、健康和变更证据，使结果可以复盘和继续推进。

## 2. 总体架构

系统采用 `5+4+1+1` 的分层模型。分层的权威定义和依赖方向由 [`docs/project-registry.yaml`](project-registry.yaml) 与 [`docs/layer-contract.yaml`](layer-contract.yaml) 管理。

```text
人类 / Agent / 自动化
          |
    Cockpit / Agora / OMO
          |
     BOS URI 路由网
          |
协议、运行时、知识引擎、治理引擎、扩展能力
          |
       状态、任务、审计、验证证据
```

### 2.1 分层职责

| 层 | 主要项目 | 责任 |
|---|---|---|
| L0 协议层 | `ecos` | SSB 签名链、MOF 元模型、约束和协议工具 |
| L1 运行时层 | `runtime` | Matrix、Scheduler、KEI 沙箱和运行执行 |
| L2 引擎层 | `kairon`、`gbrain`、`omo`、`metaos`、`omo-debt`、`family-hub` | 知识、数据库、治理、编排、债务和家庭域能力 |
| L3 入口层 | `cockpit`、`cockpit-ui` | 人类 CLI、HTTP API、MCP 和 Web 控制台 |
| L4 自我层 | `l4-kernel` | 域注册、KEMS、自我管理和卡片约束 |
| I0 织层 | `agora` | MCP Hub、BOS URI 路由和跨项目调用 |
| M0 横切层 | `model-driven` | M3→M2→M1 生命周期和模型驱动能力 |
| X 扩展层 | `aetherforge`、`c2g`、`bus-foundation`、`observability` | 算力、战略入口、总线和可观测性 |

### 2.2 入口收敛

- **人类用户**：优先使用 `cockpit` CLI 或 Cockpit Web，不为单个子项目再创建新的顶层入口。
- **AI Agent**：通过 `agora` 的 `bos://` URI 调用跨域能力。
- **治理操作**：通过 `omo` CLI/MCP、C2G ingress 或已注册 broker 修改治理状态。
- **运行状态**：通过 `omo state sync` 和 Cockpit SystemMap 读取，不手工编辑运行投影。

## 3. 项目职责地图

项目的完整版本、语言、路径、端口、命令和能力清单以 [`docs/project-registry.yaml`](project-registry.yaml) 为准。下面是面向使用者的职责地图：

| 项目 | 使用者理解 |
|---|---|
| `cockpit` | 统一控制面：把 CLI、Web、MCP、健康、任务和领域命令聚合起来 |
| `cockpit-ui` | 统一表现面：展示系统地图、任务、告警、知识、算力、资产和个人/家庭视图 |
| `agora` | 能力路由层：把 `bos://memory`、`bos://governance`、`bos://analysis`、`bos://persona`、`bos://capability` 等域映射到服务 |
| `kairon` | 知识引擎：采集、解析、索引、检索、本体、代码分析和 KOS |
| `gbrain` | Postgres 知识数据库与结构化知识查询 |
| `omo` | Agent OS 与治理内核：任务、债务、审计、SSOT、broker、工作流和状态同步 |
| `metaos` | 日常编排和决策门控：把目标、仪式、免疫和路由接入执行闭环 |
| `runtime` | 执行与调度：把任务交给 Matrix、Scheduler、KEI 和沙箱 |
| `ecos` | 协议与元模型：SSB、MOF、L0 约束和工作流基础设施 |
| `l4-kernel` | 自我管理域、KEMS、CARDS 和域级健康能力 |
| `model-driven` | 生命周期元框架，提供模型到实例的桥接 |
| `aetherforge` | LLM Gateway、节点 Mesh、Swarm 和成本/健康报告 |
| `c2g` | 把战略意图或 pitch 物化为可执行、可治理任务 |
| `bus-foundation` | Data、Event、Control 三平面 Omni-Bus |
| `observability` | Langfuse、Postgres 和 Webhook Bridge 等运行观测设施 |
| `family-hub` | 家庭数字枢纽、Quest 和家庭域工作流 |
| `omo-debt` | 技术债务评分、登记和处理辅助 |
| `mesh-router` | 由 `bin/_archive/2026-08-conv3/gac-mesh-router.py` 提供的算力路由实现，不是独立仓库 |

## 4. 用户如何使用

### 4.1 新用户了解系统

1. 阅读本文了解概念和入口。
2. 阅读 [`docs/FUNCTIONAL-CAPABILITY-MAP.md`](FUNCTIONAL-CAPABILITY-MAP.md) 了解能力覆盖。
3. 使用 `cockpit system-map` 或打开 Cockpit Web 查看项目、域、页面和当前运行态。
4. 需要深入时，进入对应项目的 `README.md`、`ARCHITECTURE.md`、`CALLCHAIN.md` 和 `BOUNDARY.md`。

### 4.2 开发者查找和修改能力

```bash
cockpit search <关键词>
cockpit system-map
cockpit health --full
cockpit cards --check
```

修改前先读根目录 [`AGENTS.md`](../AGENTS.md)、[`CLAUDE.md`](../CLAUDE.md) 和目标项目指导文件。需求迭代必须经过：

```text
bootstrap → status → suggest → start → claim → edit/test → verify → closeout
```

### 4.3 知识工作流

```text
资料 / URL / 代码
      ↓
cockpit import 或 kairon pipeline
      ↓
解析、分块、向量化、本体派生、索引
      ↓
KOS / gbrain / Minerva / Iris
      ↓
cockpit research / search 或 Agora BOS 调用
```

常见入口包括 `cockpit research search`、`cockpit import`、Kairon 的 `kronos`、`minerva` 和 `iris` 能力。

### 4.4 需求到执行工作流

```text
用户意图 / Pitch
      ↓
C2G / cockpit iterate
      ↓
OMO task / debt / proposal
      ↓
MetaOS gate 与模型驱动生命周期
      ↓
Runtime Matrix / Scheduler / KEI
      ↓
执行日志、验证命令、closeout、审计
```

涉及治理状态、任务状态、SSOT 或 `.omo` 的操作，必须走注册 broker/CLI，不要直接改投影文件。

### 4.5 算力与 Agent 协作

```bash
cockpit compute gateway list
cockpit compute gateway generate
cockpit compute mesh list
cockpit compute mesh status
cockpit compute mesh health
```

AetherForge 负责 Provider 路由、节点健康、Mesh 拓扑、Swarm 编排和成本报告；跨项目 Agent 调用通过 Agora 的 BOS URI 进入。

## 5. Cockpit 使用面

Cockpit 是 L3 控制面，提供：

- **系统地图**：项目、层、域、运行态、覆盖度、缺口和下一步动作。
- **治理与任务**：任务队列、债务、提案审批、工作流、审计和 closeout。
- **知识与研究**：搜索、导入、研究任务、问答、摘要、档案和发布。
- **执行与算力**：Gateway、Mesh、Swarm、Runtime、队列和执行证据。
- **个人与家庭**：L4 健康、CARDS、Quest、家庭域和日常节奏。
- **观测与告警**：健康检查、事件流、Langfuse、运行日志和告警处置。

Web 视图的页面注册和能力成熟度由 Cockpit UI 代码与页面注册表维护；页面导航不应绕开统一 API 和治理动作。

## 6. 本地启动

### 6.1 环境准备

```bash
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation
uv --version
bun --version
docker --version
```

### 6.2 一键运行

```bash
python scripts/ecos-start.py --dry-run
python scripts/ecos-start.py
```

只启动核心服务：

```bash
python scripts/ecos-start.py --services cockpit,agora,l4-kernel,runtime
```

可观测性服务单独启动：

```bash
cd projects/observability
cp .env.example .env
docker compose --env-file .env up -d
docker compose --env-file .env ps
```

不要把真实密钥提交到 `.env`、日志或证据文件中。

### 6.3 常用入口

```bash
cockpit health --full
cockpit system-map
cockpit dashboard
omo state sync --json
```

端口和传输协议以 [`protocols/port-registry.yaml`](../protocols/port-registry.yaml) 为准，不要根据旧文档或个人习惯写死端口。

## 7. 测试与质量门禁

### 7.1 根仓检查

```bash
make check-layers
make ssot-status
make gac-local-gate
make ci-local-fast
bash tests/integration/run-all.sh
```

### 7.2 项目级检查

```bash
cd projects/knowledge/kairon && make test-diff
cd projects/knowledge/gbrain && bun test
cd projects/omo && uv run pytest tests/ -q
cd projects/runtime && uv run pytest tests/ -q
cd projects/cockpit && uv run pytest tests/ -q
cd projects/cockpit-ui && bun test
```

窄变更优先跑目标项目测试；触及入口、SSOT、注册表、治理 broker、跨项目契约或子模块指针时，必须扩大验证范围。

## 8. Git、Worktree 与 PR

主仓 `main` 变更采用 per-session worktree + PR。基本流程：

```bash
bash bin/gac/gac-worktree.sh claim <session>
cd ../ws-<session>
# 修改、测试、分层提交
git add <paths>
git commit -m "<type>(<scope>): <summary>"
bash bin/gac/gac-worktree.sh submit <session>
```

子模块先在各自仓库提交，再回到主仓提交子模块指针。合并前确认：

- PR 只包含当前 session 的改动。
- 不覆盖其他 worktree 或未提交文件。
- 根仓、子模块和 UI 的提交关系完整。
- `git diff --check`、目标测试和治理门禁通过。
- `.omo` 证据通过 broker/工作流生成，不能手工伪造。

## 9. 数据、状态与治理边界

| 目录 | 含义 | 操作规则 |
|---|---|---|
| `.omo/` | 状态、任务、审计、证据和治理投影 | 通过 OMO/C2G/broker 操作 |
| `projects/omo/` | 治理内核和工具实现 | 代码变更需走 workflow |
| `projects/ecos/` | 协议和 MOF/L0 | 遵循 L0 SSOT 与约束 |
| `projects/c2g/` | 战略需求入口 | 通过受控 ingress 物化任务 |
| `runtime/` | 运行日志和沙箱 | 不手工编辑运行日志 |
| `kos/` | 知识索引与快照 | 由运行时产品维护 |
| `protocols/` | 端口、路径和 X 轴注册表 | 作为只读事实源 |
| `scripts/` | 运维脚本子模块 | 遵循其项目指导文件 |

系统的核心质量标准不是“文件存在”，而是“入口可达、动作可执行、状态可观察、结果有证据”。

## 10. 故障排查顺序

1. 先运行 `git status --short`，确认是否是未提交或其他 worktree 造成的状态差异。
2. 运行 `cockpit health --full`，区分基础、运行、治理和外部依赖问题。
3. 用 `cockpit system-map` 定位项目、域、端口和缺口。
4. 查 `protocols/port-registry.yaml`、`.omo/state/system.yaml` 和对应服务日志。
5. 复现登记的验证命令，使用 agent-workflow 留证。
6. 只有在证据明确后才修代码、改配置或更新注册表。

常见边界：外部 Provider 密钥、Docker 服务、模型下载、宿主机端口、iCloud/Vault 路径和其他 agent 的并发修改都可能影响运行态；这些问题不能用修改静态 Markdown 掩盖。

## 11. 文档索引

- 总入口：[`README.md`](../README.md)
- 稳定架构：[`ARCHITECTURE.md`](../ARCHITECTURE.md)
- 系统导航：[`SYSTEM-INDEX.md`](SYSTEM-INDEX.md)
- 功能能力：[`FUNCTIONAL-CAPABILITY-MAP.md`](FUNCTIONAL-CAPABILITY-MAP.md)
- 系统全景：[`PANORAMA.md`](PANORAMA.md)
- 用户旅程：[`USER-JOURNEY-SOP.md`](USER-JOURNEY-SOP.md)
- 本地启动：[`LOCAL-RUNTIME-STARTUP.md`](LOCAL-RUNTIME-STARTUP.md)
- 项目索引：[`INDEX-PROJECTS.md`](INDEX-PROJECTS.md)
- 工具索引：[`INDEX-TOOLS.md`](INDEX-TOOLS.md)
- Agent 指南：[`INDEX-AGENTS.md`](INDEX-AGENTS.md)
- 知识与决策：[`INDEX-KNOWLEDGE.md`](INDEX-KNOWLEDGE.md)

本文是导航层，不替代各项目的代码级文档、SSOT、ADR 或运行日志。
