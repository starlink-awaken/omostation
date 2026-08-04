# CLAUDE.md — Agora AI Context

    > Session loader for AI work inside `agora`.
    > Keep durable engineering rules in [`AGENTS.md`](AGENTS.md) and volatile facts in SSOT files.

    ## Load First

    1. [`AGENTS.md`](AGENTS.md)
    2. [`README.md`](README.md) when present
    3. The source files and tests directly related to the task
    4. Workspace context in [`../../CLAUDE.md`](../../CLAUDE.md) when the task crosses project boundaries
    5. System index in [`../../docs/SYSTEM-INDEX.md`](../../docs/SYSTEM-INDEX.md) for workspace navigation

    ## Project Role

    - Layer: I0
    - Responsibility: BOS URI 路由与 MCP Hub
    - Stack: Python / uv / pytest

    ## Commands

    ```bash
    uv sync
uv run pytest "tests/" -q
uv run ruff check "src/"
    ```

    ## Safe Editing Rules

    - `BOS 服务清单以 etc/bos-services.yaml 为唯一读源。`
- `端口以 ../../protocols/port-registry.yaml 为准，不在文档里硬编码。`
- `server/mcp 类入口不要继续膨胀，新增能力优先落到专门模块。`
- `能力治理三层闭环 (B1→B2→B3): bos_metrics 度量 → capability_catalog 有效状态 → bos_router 语义路由。修改能力状态从度量驱动，不硬编码 deprecated。`
- `新增能力暴露: 改 etc/bos-services.yaml 后, external_resources/capability_provider 自动纳入能力目录 (external-resource-catalog --directory 可见)。`

    - Do not commit, push, reset, or bump submodule pointers unless the user explicitly asks.
    - Preserve unrelated dirty changes in this repository.
    - Keep Markdown pointed at SSOT files instead of copying generated facts.

    ## Closeout

    ```bash
    git status --short
    uv run --with "pyyaml" python "../../bin/ssot/doc-ssot-lint.py" --json
    ```

    Report the checks you actually ran and any pre-existing dirty state that remains.
