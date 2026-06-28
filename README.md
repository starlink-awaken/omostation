# omostation · eCOS v6

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![CI Status](https://img.shields.io/badge/CI-20%20workflows-brightgreen)](.github/workflows/)
[![Tests](https://img.shields.io/badge/tests-16,800+-blue)](AGENTS.md)
[![SOTI](https://img.shields.io/badge/health-SSOT-success)](.omo/state/system.yaml)

> **eCOS v6** — 多项目知识工程与研究 Workspace。5+4+1+1 架构（5 层 L0-L4 + 4 维 X1-X4 + 1 织 I0 + 1 横切 M0），20 子项目（8 活跃核心 + 12 扩展），~520K 行代码，16,800+ 测试。
> **当前 Phase 42** — 治理面 SSOT 同步纪元。健康分/governance 见 SSOT ([.omo/state/system.yaml](.omo/state/system.yaml) 为 SSOT）。
>
> **eCOS v6** — Multi-project knowledge engineering & research workspace. 5+4+1+1 architecture (5 layers L0-L4 + 4 dimensions X1-X4 + 1 weave I0 + 1 cross-cutting M0), 20 sub-projects (8 active core + 12 extensions), ~520K LOC, 16,800+ tests.
> **Phase 42** — Governance SSOT Catch-up Era. Health 见 SSOT · governance 100 A+ (double-perfect; see [.omo/state/system.yaml](.omo/state/system.yaml) as SSOT).

[English](#english) | [中文](#中文)

---

<a name="english"></a>

## English

### Architecture

```
 L4  Self      ── Personal CARDS + Learning Evolution (SQLite/MD)
 L3  Entry     ── cockpit (CLI 18 commands + MCP + FastAPI Web Dashboard)
 I0  Weave     ── agora (Dynamic MCP Proxy Mesh, 90+ tools)
 L2  Engine    ── kairon (19 packages) · gbrain (TypeScript) · omo · metaos
 L1  Runtime   ── runtime (Compute Gateway + Scheduler + KEI Sandbox)
 L0  Protocol  ── ecos (SSB Protocol Layer + Emergence + M1 MOF Models)
```

### Core Spines (Phase 2-9)
- **🧠 Memory Spine**: Unified cross-domain knowledge aggregation (`bos://memory/local/all-search`) over KOS, gbrain, and local Vaults.
- **📡 Swarm Spine**: Distributed multi-node agent coordination with A2ANetworkTransport, Auto-Proxying, and **Ed25519 Trust Verification (X1)**.
- **⚙️ Compute Spine**: Centralized LLM orchestration with **Real-time Atomic Budget Deductions (X2)** and Quota-Low adaptive scheduling.
- **⚖️ Evolution Loop**: OMO daemon for active debt remediation with **Cockpit HITL Gate (X4)** and **MetaOS Admission Gates (X3)**.

### Active Projects

| Project | Layer | Language | Source | Tests | Pass Rate |
|---------|-------|----------|--------|-------|-----------|
| [agora](./projects/agora/) | I0 | Python | 38,905 LOC | 1,200 | 97.1% |
| [cockpit](./projects/cockpit/) | L3 | Python | 16,260 LOC | 514 | 96.9% |
| [kairon](./projects/kairon/) | L2 | Python | 208,540 LOC | 4,199 | 99.8% |
| [gbrain](./projects/gbrain/) | L2 | TypeScript | 163,204 LOC | ~9,737 | ~99.6% |
| [omo](./projects/omo/) | L2 | Python | 19,921 LOC | 530 | 97.4% |
| [metaos](./projects/metaos/) | L2 | Python | 7,341 LOC | 188 | 100% |
| [runtime](./projects/runtime/) | L1 | Python | 25,012 LOC | 176 | 97.2% |
| [ecos](./projects/ecos/) | L0 | Python | 10,601 LOC | 122 | 91.8% |

### Quick Start

```bash
# Clone workspace
git clone https://github.com/starlink-awaken/omostation.git
cd omostation

# Run all integration tests
bash tests/integration/run-all.sh

# Per-project tests
cd projects/kairon && make test         # Kairon: all 19 packages
cd projects/agora && uv run pytest      # Agora: 1165/1200 pass
cd projects/gbrain && bun test          # Gbrain: ~9,700 pass
```

### Governance

- **[OMO](./projects/omo/)** — Operating System for AI Agents (debt registry, task management, health monitoring)
- **[Self-Healing Engine](./projects/omo/src/omo/omo_self_healing.py)** — Automatic error detection, debt generation, and fix execution
- **[Audit Report](./.omo/_delivery/audits/architecture_audit_20260607.md)** — Comprehensive architecture audit (2026-06-07)
- **[Tech Debt Roadmap](./.omo/_delivery/audits/tech_debt_roadmap_20260607.md)** — Remaining debt items

### AppendOnlyLog Pattern (Round 1-5 收口)

L0 SSOT 抽象, 5 个领域共享同一 JSONL 物理写盘. 详见 [.omo/_knowledge/management/append-only-log-pattern-2026-06-09.md](.omo/_knowledge/management/append-only-log-pattern-2026-06-09.md).

| Consumer | 落点 | 角色 |
|----------|------|------|
| `omo_audit` | `~/runtime/audit/governance-audit.jsonl` | governance actions |
| `omo_bos_metrics` | `.omo/_knowledge/bos-metrics.jsonl` | BOS invocations |
| `omo_sync` | `.omo/_knowledge/omo-sync.jsonl` | omo state sync |
| `omo_alert` | `.omo/_knowledge/omo-alerts.jsonl` | KEI threshold alerts |
| `omo_event` | `.omo/_knowledge/omo-events.jsonl` | 用户面向 emit (P3 样板) |

**关键命令**:

```bash
# 观测
omo bos status                          # BOS invoke metrics (p50/p95/p99)
omo bos discover                        # Pydantic 验证后的注册表
omo bos health                          # endpoint + metrics 健康
omo observability log tail --type knowledge   # 多文件 tail

# 用户写
omo event emit --type my_event --source my_script --payload '{"k":"v"}'

# 跨项目桥接
from omo.model_driven_bridge import make_pipeline_tracker_with_log
tracker = make_pipeline_tracker_with_log(entity_id="my-domain")
# PipelineTracker.on_event 自动流到 .omo/_knowledge/pipeline-events.jsonl
```

### Documentation

| Document | Description |
|----------|-------------|
| [AGENTS.md](./AGENTS.md) | Development guide for AI agents |
| [CLAUDE.md](./CLAUDE.md) | AI assistant operational rules |
| [LAYER-INDEX.md](./LAYER-INDEX.md) | 7-layer architecture index |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Contribution guidelines |
| [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) | Community code of conduct |
| [SECURITY.md](./SECURITY.md) | Security policy |
| [WIKI.md](./WIKI.md) | Technical Wiki |

### CI/CD

19 workflows covering all 8 projects. See [.github/workflows/](./.github/workflows/).

### License

MIT © [starlink-awaken](https://github.com/starlink-awaken)

---

<a name="中文"></a>

## 中文

### 架构

```
 L4  自我层     ── ~/Documents/驾驶舱/CARDS/ (SQLite) + ~/Documents/学习进化/ (MD)
 L3  入口层     ── cockpit (CLI 13 + MCP + Web 仪表板)
 I0  织层       ── agora (动态反向代理 MCP 网格, 42+ 工具)
 L2  引擎面     ── kairon (19 包) · gbrain (67 MCP 工具) · omo · metaos
 L1  运行时     ── runtime (Matrix + Scheduler + KEI 沙箱)
 L0  协议层     ── ecos (SSB 签名链 + 涌现计算)
```

### 活跃项目

| 项目 | 层级 | 语言 | 代码量 | 测试数 | 通过率 |
|------|------|------|--------|--------|--------|
| [agora](./projects/agora/) | I0 | Python | 38,905 行 | 1,200 | 97.1% |
| [cockpit](./projects/cockpit/) | L3 | Python | 16,260 行 | 514 | 96.9% |
| [kairon](./projects/kairon/) | L2 | Python | 208,540 行 | 4,199 | 99.8% |
| [gbrain](./projects/gbrain/) | L2 | TypeScript | 163,204 行 | ~9,737 | ~99.6% |
| [omo](./projects/omo/) | L2 | Python | 19,921 行 | 530 | 97.4% |
| [metaos](./projects/metaos/) | L2 | Python | 7,341 行 | 188 | 100% |
| [runtime](./projects/runtime/) | L1 | Python | 25,012 行 | 176 | 97.2% |
| [ecos](./projects/ecos/) | L0 | Python | 10,601 行 | 122 | 91.8% |

### 快速开始

```bash
# 克隆工作区
git clone https://github.com/starlink-awaken/omostation.git
cd omostation

# 运行所有集成测试
bash tests/integration/run-all.sh

# 单项目测试
cd projects/kairon && make test         # Kairon: 19 个包全量测试
cd projects/agora && uv run pytest      # Agora: 1165/1200 通过
cd projects/gbrain && bun test          # Gbrain: ~9,700 通过
```

### 治理体系

- **[OMO](./projects/omo/)** — AI Agent 操作系统 (债务注册、任务管理、健康监控)
- **[自愈引擎](./projects/omo/src/omo/omo_self_healing.py)** — 自动错误检测、债务生成、修复执行
- **[审计报告](./.omo/_delivery/audits/architecture_audit_20260607.md)** — 全面架构审计 (2026-06-07)
- **[技术债务路线图](./.omo/_delivery/audits/tech_debt_roadmap_20260607.md)** — 剩余债务项目

### 文档

| 文档 | 说明 |
|------|------|
| [AGENTS.md](./AGENTS.md) | AI Agent 开发指南 |
| [CLAUDE.md](./CLAUDE.md) | AI 助手操作规则 |
| [LAYER-INDEX.md](./LAYER-INDEX.md) | 7 层架构索引 |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | 贡献指南 |
| [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) | 社区行为准则 |
| [SECURITY.md](./SECURITY.md) | 安全策略 |
| [WIKI.md](./WIKI.md) | 技术 Wiki |

### CI/CD

20 个 workflows 覆盖全部 8 个项目。详见 [.github/workflows/](./.github/workflows/)。

### 许可证

MIT © [starlink-awaken](https://github.com/starlink-awaken)
