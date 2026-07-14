# CLAUDE.md — OMO AI Context

    > Session loader for AI work inside `omo`.
    > Keep durable engineering rules in [`AGENTS.md`](AGENTS.md) and volatile facts in SSOT files.

    ## Load First

    1. [`AGENTS.md`](AGENTS.md)
    2. [`README.md`](README.md) when present
    3. The source files and tests directly related to the task
    4. Workspace context in [`../../CLAUDE.md`](../../CLAUDE.md) when the task crosses project boundaries
    5. System index in [`../../docs/SYSTEM-INDEX.md`](../../docs/SYSTEM-INDEX.md) for workspace navigation

    ## Project Role

    - Layer: L2
    - Responsibility: 治理内核：Phase/Task/Debt/Audit 生命周期
    - Stack: Python / uv / pytest

    ## Commands

    ```bash
    uv sync
uv run pytest "tests/" -q
uv run omo state sync --dry-run --json
uv run omo state sync --json
uv run python -m omo.cli governance audit
uv run python -m omo.cli lint direct-omo-io
    ```

    ## Safe Editing Rules

    - `不要直接写 ../../.omo/，状态变更走 OMO CLI/MCP/broker。`
- `新增治理写面必须同时有 runtime 实现、truth registry、lint/CI 门禁。`
- `CLI/MCP 工具数量以代码和 docs/project-registry.yaml 为准。`

    - Do not commit, push, reset, or bump submodule pointers unless the user explicitly asks.
    - Preserve unrelated dirty changes in this repository.
    - Keep Markdown pointed at SSOT files instead of copying generated facts.

    ## Closeout

    ```bash
    git status --short
    uv run --with "pyyaml" python "../../bin/doc-ssot-lint.py" --json
    ```

    Report the checks you actually ran and any pre-existing dirty state that remains.
