# SYSTEM-INDEX.md — Workspace 全景导航

> 维护: governance-team | 更新: 重大架构变更时 | 验证: 所有指针路径存在
> 本文件不持有任何数据，只做指针。数值见各 SSOT 源。

## 30 秒理解

- **5+4+1+1 架构**: L0 协议 → L1 运行时 → L2 引擎 → L3 入口 → L4 自我, I0 织层, M0 横切
- **17 个项目**: 见 `docs/project-registry.yaml`
- **139 条 GaC 规则**: 见 `.omo/_truth/registry/governance-checks.yaml`
- **89 个 ADR**: 见 `.omo/_knowledge/decisions/INDEX.md`

## SSOT 导航

| 我想知道 | 去哪里读 | 维度 |
|----------|---------|------|
| 项目元数据 (层/栈/版本/角色) | [`docs/project-registry.yaml`](docs/project-registry.yaml) | 事实层 |
| 项目按层分类 | [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md) | 事实层 |
| 运行时状态 (Phase/健康分) | [`.omo/state/system.yaml`](.omo/state/system.yaml) | 事实层 |
| 架构契约 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | 架构层 |
| 层索引 | [`LAYER-INDEX.md`](LAYER-INDEX.md) | 架构层 |
| 端口分配 | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) | 边界层 |
| Vault 路径 | [`protocols/vault-paths.yaml`](protocols/vault-paths.yaml) | 边界层 |
| X 轴保证 | [`protocols/x-axis-registry.yaml`](protocols/x-axis-registry.yaml) | 边界层 |
| GaC 规则 | [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml) | 事实层 |
| GaC 规则摘要 | [`docs/generated/agent-gac-rules.md`](docs/generated/agent-gac-rules.md) | 事实层 |
| ADR 决策 | [`.omo/_knowledge/decisions/INDEX.md`](.omo/_knowledge/decisions/INDEX.md) | 知识层 |
| 治理标准 | [`.omo/standards/`](.omo/standards/) | 架构层 |
| 注册表清单 | [`.omo/_truth/registry/INDEX.md`](.omo/_truth/registry/INDEX.md) | 事实层 |
| 文档 SSOT 契约 | [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) | 架构层 |

## 操作入口

| 我想做什么 | 用什么命令 |
|-----------|-----------|
| 检查治理状态 | `make gac-local-gate` |
| 启动 agent 工作流 | `uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap` |
| 查看可用工具 | `ls bin/*.py` 或 [`bin/README.md`](bin/README.md) |
| 查看项目列表 | `ls projects/` |
| 查看 ADR | `ls .omo/_knowledge/decisions/` |

## 项目层图

```
L4 自我层 ─ l4-kernel
L3 入口层 ─ cockpit (CLI/MCP/Web), cockpit-ui (React)
L2 引擎面 ─ kairon (知识引擎), gbrain (知识库), omo (治理), metaos (编排)
L1 运行时 ─ runtime
L0 协议层 ─ ecos (SSB/MOF/L0 约束)
I0 织层   ─ agora (MCP Hub/BOS 路由)
M0 横切   ─ model-driven (生命周期框架)
X  扩展   ─ aetherforge, c2g, bus-foundation, omo-debt, observability, family-hub
```

> 详细数据见 `docs/project-registry.yaml`，本图不含易变数值。

## 相关文档

| 文档 | 维度 | 用途 |
|------|------|------|
| [`AGENTS.md`](AGENTS.md) | 操作层 | 开发规则和命令 |
| [`CLAUDE.md`](CLAUDE.md) | 操作层 | AI 会话协议 |
| [`README.md`](README.md) | 入口层 | 快速开始 |
| [`PANORAMA.md`](docs/PANORAMA.md) | 架构层 | 全景架构图 |
