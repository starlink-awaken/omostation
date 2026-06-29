# omostation · eCOS v6

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI](https://github.com/starlink-awaken/omostation/actions/workflows/workspace.yml/badge.svg)](https://github.com/starlink-awaken/omostation/actions)

> Multi-project knowledge engineering and AI operating-system workspace.
> Runtime state lives in [`.omo/state/system.yaml`](.omo/state/system.yaml).
> Project metadata lives in [`docs/project-registry.yaml`](docs/project-registry.yaml).

[English](#english) | [中文](#中文)

---

<a name="english"></a>

## English

### What This Is

`omostation` is the root workspace for eCOS v6: a layered system for knowledge engineering, agent governance, BOS service routing, runtime orchestration, and personal/work knowledge operations.

This README is only the front door. It intentionally avoids hard-coded runtime numbers such as phase, health score, test counts, tool counts, service counts, and ports.

### Architecture

```
L4  Self       -> l4-kernel
L3  Entry      -> cockpit (cockpit-ui: layer=X, 挂载至 cockpit)
I0  Weave      -> agora
L2  Engine     -> kairon / gbrain / omo / metaos
L1  Runtime    -> runtime
L0  Protocol   -> ecos
M0  Lifecycle  -> model-driven
X   Frameworks -> aetherforge / c2g / bus-foundation / omo-debt / observability / family-hub
```

For the complete architecture, read [`ARCHITECTURE.md`](ARCHITECTURE.md). For layer placement, read [`LAYER-INDEX.md`](LAYER-INDEX.md).

### Entry Points

| Audience | Entry | Source Of Truth |
|----------|-------|-----------------|
| Human CLI/Web | `cockpit` | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |
| AI agent | `agora` MCP with `bos://` URIs | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Agent workflow | `bin/agent-workflow.py` / `cockpit agent-workflow` | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| Governance | `omo` CLI/MCP broker | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |

### Quick Start

```bash
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation

bash tests/integration/run-all.sh

cd projects/kairon && make test-diff
cd projects/agora && uv run pytest tests/ -q
cd projects/gbrain && bun test
```

### Documentation Map

| Document | Purpose |
|----------|---------|
| [`AGENTS.md`](AGENTS.md) | Agent/developer operating guide |
| [`CLAUDE.md`](CLAUDE.md) | AI session context loader |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Stable architecture contracts |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | Layer and project placement |
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | Product and capability panorama |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | Project metadata SSOT |
| [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) | Documentation SSOT contract |

### Governance

- Runtime state: [`.omo/state/system.yaml`](.omo/state/system.yaml)
- Current goals: [`.omo/goals/current.yaml`](.omo/goals/current.yaml)
- Governance kernel: [`projects/omo/`](projects/omo/)
- Governance-as-Code registry: [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml)
- Executable agent workflows: [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml)

### License

MIT © [starlink-awaken](https://github.com/starlink-awaken)

---

<a name="中文"></a>

## 中文

### 这是什么

`omostation` 是 eCOS v6 的根工作区，用来承载知识工程、Agent 治理、BOS 服务路由、运行时编排，以及个人/工作知识操作。

本 README 只做入口导航，不维护 Phase、健康分、测试数、工具数、服务数、端口等易漂移事实。那些事实有各自的 SSOT。

### 架构速览

```
L4  自我层     -> l4-kernel
L3  入口层     -> cockpit (cockpit-ui: layer=X, 挂载至 cockpit)
I0  织层       -> agora
L2  引擎面     -> kairon / gbrain / omo / metaos
L1  运行时     -> runtime
L0  协议层     -> ecos
M0  生命周期   -> model-driven
X   横切框架   -> aetherforge / c2g / bus-foundation / omo-debt / observability / family-hub
```

完整架构见 [`ARCHITECTURE.md`](ARCHITECTURE.md)，分层项目索引见 [`LAYER-INDEX.md`](LAYER-INDEX.md)。

### 入口

| 受众 | 入口 | 权威来源 |
|------|------|----------|
| 人类 CLI/Web | `cockpit` | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) |
| AI Agent | `agora` MCP + `bos://` URI | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) |
| Agent 工作流 | `bin/agent-workflow.py` / `cockpit agent-workflow` | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| 治理操作 | `omo` CLI/MCP broker | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |

### 快速开始

```bash
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation

bash tests/integration/run-all.sh

cd projects/kairon && make test-diff
cd projects/agora && uv run pytest tests/ -q
cd projects/gbrain && bun test
```

### 文档地图

| 文档 | 用途 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | Agent / 开发者操作指南 |
| [`CLAUDE.md`](CLAUDE.md) | AI 会话上下文加载器 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 稳定架构契约 |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | 分层与项目位置索引 |
| [`docs/PANORAMA.md`](docs/PANORAMA.md) | 产品与能力全景 |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | 项目元数据 SSOT |
| [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) | 文档 SSOT 契约 |

### 治理

- 运行时状态: [`.omo/state/system.yaml`](.omo/state/system.yaml)
- 当前目标: [`.omo/goals/current.yaml`](.omo/goals/current.yaml)
- 治理内核: [`projects/omo/`](projects/omo/)
- Governance-as-Code 注册表: [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml)
- 可执行 Agent 工作流: [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml)

### 许可证

MIT © [starlink-awaken](https://github.com/starlink-awaken)
