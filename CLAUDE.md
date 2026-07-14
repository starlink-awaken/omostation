# CLAUDE.md — Cockpit AI Context

    > Session loader for AI work inside `cockpit`.
    > Keep durable engineering rules in [`AGENTS.md`](AGENTS.md) and volatile facts in SSOT files.

    ## Load First

    1. [`AGENTS.md`](AGENTS.md)
    2. [`README.md`](README.md) when present
    3. The source files and tests directly related to the task
    4. Workspace context in [`../../CLAUDE.md`](../../CLAUDE.md) when the task crosses project boundaries
    5. System index in [`../../docs/SYSTEM-INDEX.md`](../../docs/SYSTEM-INDEX.md) for workspace navigation

    ## Project Role

    - Layer: L3
    - Responsibility: 统一人类 CLI/Web 入口与 HITL 操作面
    - Stack: Python / uv / pytest

    ## Commands

    ```bash
    uv sync
uv run pytest "src/cockpit/tests/" -q
uv run ruff check "src/"
    ```

    ## Safe Editing Rules

    - `测试主目录在 src/cockpit/tests/，不要默认写到根 tests/。`
- `Web/API 入口保持 L3 收敛，新入口先更新边界与端口注册表。`

    - Do not commit, push, reset, or bump submodule pointers unless the user explicitly asks.
    - Preserve unrelated dirty changes in this repository.
    - Keep Markdown pointed at SSOT files instead of copying generated facts.

    ## Closeout

    ```bash
    git status --short
    uv run --with "pyyaml" python "../../bin/doc-ssot-lint.py" --json
    ```

    Report the checks you actually ran and any pre-existing dirty state that remains.
