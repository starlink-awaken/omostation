# OMO

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributing](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security](https://img.shields.io/badge/security-policy-blue.svg)](SECURITY.md)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-package%20manager-purple.svg)](https://docs.astral.sh/uv/)

    > L2 · 治理内核：Phase/Task/Debt/Audit 生命周期
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    治理内核：Phase/Task/Debt/Audit 生命周期.

    ## Installation

```bash
# Clone the workspace recursively
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation/projects/omo

# Install dependencies with uv
uv sync
```

Requires Python 3.13+ (see `pyproject.toml`).

## Quick Start

    ```bash
    uv sync
uv run pytest "tests/" -q
uv run python -m omo.cli governance audit
uv run python -m omo.cli lint direct-omo-io
    ```

    ## Key Surfaces

    - `src/omo/cli.py`
- `src/omo/mcp_server.py`
- `src/omo/omo_ingress*.py`
- `src/omo/omo_lint*.py`
- `src/omo/_shared/`

    ## CLI 子命令

    | 命令 | 功能 |
    |------|------|
    | `omo doctor` | 统一健康检查入口 (state + key files + agora + debt) |
    | `omo inspect` | 统一检查入口 (completeness + references + schemas + god-module) |
    | `omo report` | 综合报告生成 (doctor + inspect + audit) |
    | `omo watch` | 实时监控模式 (定期运行 doctor，检测状态变化) |
    | `omo docs` | CLI 文档自动生成 |
    | `omo health check` | 探活 agora-routes.json 注册的服务端点 |
    | `omo health dashboard` | Keeper Dashboard — 读取 .omo/ 状态文件渲染运维看板 |
    | `omo lint projection-guard` | P74: 验证 runtime-projections.yaml 声明的路径存在且可解析 |
    | `omo lint stamp-policy` | P74: 验证 runtime/ 下文件必须 gitignored/tracked/allowlisted |
    | `omo manage {status,health,tasks}` | .omo 目录管理工具集 |
    | `omo validate {completeness,references,state,all}` | .omo 目录验证工具集 |
    | `omo audit cards` | CARDS X3 value metrics (SQLite 聚合) |
    | `omo audit vault` | Vault X1 audit (Markdown content hash + author tracking) |
    | `omo audit freshness` | X2 freshness audit (3 条 P43 巡检规则) |

    ## Documentation

    - Developer guide: [`AGENTS.md`](AGENTS.md)
    - AI context loader: [`CLAUDE.md`](CLAUDE.md) when present
    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer placement: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)

    ## SSOT Rules

    Runtime facts, counts, ports, health, and generated inventories are intentionally not maintained here. Use the workspace registries and project source as the truth.
## Project Governance

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
