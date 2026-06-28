# runtime

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
