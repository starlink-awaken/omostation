# Cockpit

🌐 [简体中文](README.zh.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributing](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security](https://img.shields.io/badge/security-policy-blue.svg)](SECURITY.md)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-package%20manager-purple.svg)](https://docs.astral.sh/uv/)

    > L3 · 统一人类 CLI/Web 入口与 HITL 操作面
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    统一人类 CLI/Web 入口与 HITL 操作面.

    ### CLI 收敛

    `cockpit` 是 workspace 的 L3 唯一人类入口。新增命令对所有项目和核心能力做统一收敛：

    - **委派**：`agora`、`model-driven`、`gbrain` —— 直接调用对应项目 CLI。
    - **聚合**：`kairon` —— monorepo 内 kos / eidos / iris / code / ontoderive / minerva / sophia 的统一入口。
    - **能力化**：`bus`、`observe`、`family-hub`、`mesh`、`bos capability` —— 把无独立 CLI 的项目场景封装为 cockpit 子命令。

    详见 [`CAPABILITY-MAP.md`](CAPABILITY-MAP.md) 与 [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)。

    ## Installation

```bash
# Clone the workspace recursively
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation/projects/cockpit

# Install dependencies with uv
uv sync
```

Requires Python 3.13+ (see `pyproject.toml`).

## Quick Start

    ```bash
    uv sync
uv run pytest "src/cockpit/tests/" -q
uv run ruff check "src/"
    ```

    ## Key Surfaces

    - `src/cockpit/cli.py`
- `src/cockpit/commands/`
- `src/cockpit/dashboard_server.py`
- `scripts/cockpit_mcp.py`

    ## Documentation

    - Developer guide: [`AGENTS.md`](AGENTS.md)
    - AI context loader: [`CLAUDE.md`](CLAUDE.md) when present
    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer placement: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)
    - System index: [`../../docs/SYSTEM-INDEX.md`](../../docs/SYSTEM-INDEX.md) — 统一导航入口
    - Projects index: [`../../docs/INDEX-PROJECTS.md`](../../docs/INDEX-PROJECTS.md) — 项目索引
    - Tools index: [`../../docs/INDEX-TOOLS.md`](../../docs/INDEX-TOOLS.md) — 工具索引
    - Knowledge index: [`../../docs/INDEX-KNOWLEDGE.md`](../../docs/INDEX-KNOWLEDGE.md) — 知识索引
    - Agents index: [`../../docs/INDEX-AGENTS.md`](../../docs/INDEX-AGENTS.md) — Agent索引

    ## SSOT Rules

    Runtime facts, counts, ports, health, and generated inventories are intentionally not maintained here. Use the workspace registries and project source as the truth.
## Project Governance

- [Maintainers](MAINTAINERS.md)
- [Acknowledgments](ACKNOWLEDGMENTS.md)

- [Development](docs/DEVELOPMENT.md)
- [Release Process](RELEASE.md)

- [Governance](GOVERNANCE.md)
- [Support](SUPPORT.md)

- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Contributors](CONTRIBUTORS.md)
## Getting Help

- [FAQ](docs/FAQ.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [API / Usage Reference](docs/API.md)
- [Architecture Overview](docs/ARCHITECTURE.md)