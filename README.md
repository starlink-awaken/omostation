# OMO

    > L2 · 治理内核：Phase/Task/Debt/Audit 生命周期
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    治理内核：Phase/Task/Debt/Audit 生命周期.

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

    ## Documentation

    - Developer guide: [`AGENTS.md`](AGENTS.md)
    - AI context loader: [`CLAUDE.md`](CLAUDE.md) when present
    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer placement: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)

    ## SSOT Rules

    Runtime facts, counts, ports, health, and generated inventories are intentionally not maintained here. Use the workspace registries and project source as the truth.
