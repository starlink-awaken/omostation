# CLAUDE.md — GBrain AI Context

    > Session loader for AI work inside `gbrain`.
    > Keep durable engineering rules in [`AGENTS.md`](AGENTS.md) and volatile facts in SSOT files.

    ## Load First

    1. [`AGENTS.md`](AGENTS.md)
    2. [`README.md`](README.md) when present
    3. The source files and tests directly related to the task
    4. Workspace context in [`../../CLAUDE.md`](../../CLAUDE.md) when the task crosses project boundaries

    ## Project Role

    - Layer: L2
    - Responsibility: TypeScript 知识数据库与 brain runtime
    - Stack: TypeScript / Bun

    ## Commands

    ```bash
    bun install
bun test
bun run verify
bun run ci:local
    ```

    ## Safe Editing Rules

    - 信任边界是核心：远程 MCP 调用不能获得本地 CLI 权限。
- `测试输出不要通过 tail/head 截断，失败信息必须完整保留。`
- `版本与发布规则以项目自身 VERSION/package/CHANGELOG 机制为准。`

    - Do not commit, push, reset, or bump submodule pointers unless the user explicitly asks.
    - Preserve unrelated dirty changes in this repository.
    - Keep Markdown pointed at SSOT files instead of copying generated facts.

    ## Closeout

    ```bash
    git status --short
    uv run --with "pyyaml" python "../../bin/ssot/doc-ssot-lint.py" --json
    ```

    Report the checks you actually ran and any pre-existing dirty state that remains.
