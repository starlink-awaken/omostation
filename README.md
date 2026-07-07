# runtime

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributing](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security](https://img.shields.io/badge/security-policy-blue.svg)](SECURITY.md)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-package%20manager-purple.svg)](https://docs.astral.sh/uv/)

    > L1 · 服务生命周期、调度、健康监控与 KEI 沙箱
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    服务生命周期、调度、健康监控与 KEI 沙箱.

    ## Quick Start

    ```bash
    uv sync
uv run pytest "tests/" -q
make fmt
make sync-state
    ```

    ## Key Surfaces

    - `src/runtime/matrix.py`
- `src/runtime/scheduler.py`
- `src/runtime/kei.py`
- `src/runtime/cron_service/`
- `src/runtime/mcp_server.py`

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