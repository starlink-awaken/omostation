# Cockpit

    > L3 · 统一人类 CLI/Web 入口与 HITL 操作面
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    统一人类 CLI/Web 入口与 HITL 操作面.

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

    ## SSOT Rules

    Runtime facts, counts, ports, health, and generated inventories are intentionally not maintained here. Use the workspace registries and project source as the truth.
