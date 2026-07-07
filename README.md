# ecos

    > L0 · 协议层：SSB、MOF、L0 约束与治理规则
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    协议层：SSB、MOF、L0 约束与治理规则.

    ## Quick Start

    ```bash
    uv sync
uv run pytest "tests/" -q
uv run ruff check "src/"
    ```

    ## Key Surfaces

    - `src/ecos/ssot/registry/L0-constraints.yaml`
- `src/ecos/ssot/mof/`
- `src/ecos/ssot/tools/`
- `src/ecos/l0/`

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
