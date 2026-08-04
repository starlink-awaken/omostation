# AGENTS.md — Agora

    > Scope: project-local developer guide for `agora`.
    > Workspace rules live in [`../../AGENTS.md`](../../AGENTS.md); project metadata lives in [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml).

    ## Role

    - Layer: I0
    - Stack: Python / uv / pytest
    - Responsibility: BOS URI 路由与 MCP Hub

    Do not copy volatile facts such as test counts, tool counts, service counts, ports, or current health into this file.

    ## Before Editing

    1. Read this file and [`CLAUDE.md`](CLAUDE.md) when it exists.
    2. Check `git status --short` inside this project and at the workspace root.
    3. Read the specific source or tests you are about to change.
    4. Prefer project-local commands and targeted tests.

    ## Commands

    ```bash
    uv sync
uv run pytest "tests/" -q
uv run ruff check "src/"
    ```

    ## Key Files

    - `etc/bos-services.yaml`
- `src/agora/mcp/resolver/`
- `src/agora/auth/`
- `src/agora/bus/`
- `src/agora/mcp/bos_metrics.py` — B1 能力使用度量 (capability_status: 按 domain/package/action 聚合)
- `src/agora/mcp/capability_catalog.py` — B1/B2 能力目录 + 僵尸识别 (有效状态: zombie→deprecated)
- `src/agora/mcp/bos_router.py` — B2 语义路由 (resolve_with_capability: 能力声明+准入生命周期过滤)
- `src/agora/external_connections.py` — B2 能力准入 (register_capability 使用度量驱动生命周期)
- `src/agora/external_resources/capability_provider.py` — BOS 能力经 external.resources 暴露给 mesh 能力目录

    ## Gotchas

    - `BOS 服务清单以 etc/bos-services.yaml 为唯一读源。`
- `端口以 ../../protocols/port-registry.yaml 为准，不在文档里硬编码。`
- `server/mcp 类入口不要继续膨胀，新增能力优先落到专门模块。`
- `能力治理三层闭环 (B1→B2→B3): 度量 → 准入 → 发现。修改 capability 状态必须从使用度量 (bos_metrics) 驱动，不要硬编码 deprecated。`
- `僵尸能力 (active 声明 + 超 stale_days 零调用) 经 capability_catalog.get() 返回 deprecated 被语义路由拦截；无使用记录的新能力不判僵尸 (避免误杀)。`

    ## Verification

    - Documentation-only changes: run `uv run --with "pyyaml" python "../../bin/ssot/doc-ssot-lint.py" --json` from this project or from the workspace root.
    - Code changes: run the narrowest relevant project test first, then broaden if shared contracts changed.
    - Cross-layer behavior: verify the caller and the callee, not just the touched module.

    ## SSOT Pointers

    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer index: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)
    - Project metadata: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)
    - Runtime state: [`../../.omo/state/system.yaml`](../../.omo/state/system.yaml)
    - System index: [`../../docs/SYSTEM-INDEX.md`](../../docs/SYSTEM-INDEX.md) — 统一导航入口
    - Projects index: [`../../docs/INDEX-PROJECTS.md`](../../docs/INDEX-PROJECTS.md) — 项目索引
    - Tools index: [`../../docs/INDEX-TOOLS.md`](../../docs/INDEX-TOOLS.md) — 工具索引
    - Knowledge index: [`../../docs/INDEX-KNOWLEDGE.md`](../../docs/INDEX-KNOWLEDGE.md) — 知识索引
    - Agents index: [`../../docs/INDEX-AGENTS.md`](../../docs/INDEX-AGENTS.md) — Agent索引
