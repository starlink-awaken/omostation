# CLAUDE.md — runtime AI Context

    > Session loader for AI work inside `runtime`.
    > Keep durable engineering rules in [`AGENTS.md`](AGENTS.md) and volatile facts in SSOT files.

    ## Load First

    1. [`AGENTS.md`](AGENTS.md)
    2. [`README.md`](README.md) when present
    3. The source files and tests directly related to the task
    4. Workspace context in [`../../CLAUDE.md`](../../CLAUDE.md) when the task crosses project boundaries

    ## Project Role

    - Layer: L1
    - Responsibility: 服务生命周期、调度、健康监控与 KEI 沙箱
    - Stack: Python / uv / pytest

    ## Commands

    ```bash
    uv sync
uv run pytest "tests/" -q
make fmt
make sync-state
    ```

    ## Safe Editing Rules

    - `运行状态和健康事实写入 OMO/SSOT，不在 README 维护快照。`
- 端口和 daemon 暴露面以协议注册表为准。

    - Do not commit, push, reset, or bump submodule pointers unless the user explicitly asks.
    - Preserve unrelated dirty changes in this repository.
    - Keep Markdown pointed at SSOT files instead of copying generated facts.

    ## Closeout

    ```bash
    git status --short
    uv run --with "pyyaml" python "../../bin/ssot/doc-ssot-lint.py" --json
    ```

    Report the checks you actually ran and any pre-existing dirty state that remains.
