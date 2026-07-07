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

    ## CLI 子命令

    | 命令 | 功能 |
    |------|------|
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
