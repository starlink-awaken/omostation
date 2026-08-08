# Agora

🌐 [简体中文](README.zh.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributing](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security](https://img.shields.io/badge/security-policy-blue.svg)](SECURITY.md)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-package%20manager-purple.svg)](https://docs.astral.sh/uv/)

    > I0 · BOS URI 路由与 MCP Hub
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    BOS URI 路由与 MCP Hub.

    ## Installation

```bash
# Clone the workspace recursively
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation/projects/agora

# Install dependencies with uv
uv sync
```

Requires Python 3.13+ (see `pyproject.toml`).

## Quick Start

    ```bash
    uv sync
uv run pytest "tests/" -q
uv run ruff check "src/"
    ```

    ## Key Surfaces

    - `etc/bos-services.yaml`
- `src/agora/mcp/resolver/`
- `src/agora/auth/`
- `src/agora/bus/`
- `src/agora/mcp/bos_metrics.py` — 能力使用度量 (capability 粒度)
- `src/agora/mcp/capability_catalog.py` — 能力目录 + 僵尸识别
- `src/agora/mcp/bos_router.py` — 语义路由 (能力感知)
- `src/agora/external_resources/capability_provider.py` — BOS 能力暴露给 mesh 能力目录

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