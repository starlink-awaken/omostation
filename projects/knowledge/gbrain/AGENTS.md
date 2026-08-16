# AGENTS.md — GBrain

    > Scope: project-local developer guide for `gbrain`.
    > Workspace rules live in [`../../AGENTS.md`](../../AGENTS.md); project metadata lives in [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml).

    ## Role

    - Layer: L2
    - Stack: TypeScript / Bun
    - Responsibility: TypeScript 知识数据库与 brain runtime

    Do not copy volatile facts such as test counts, tool counts, service counts, ports, or current health into this file.

    ## Before Editing

    1. Read this file and [`CLAUDE.md`](CLAUDE.md) when it exists.
    2. Check `git status --short` inside this project and at the workspace root.
    3. Read the specific source or tests you are about to change.
    4. Prefer project-local commands and targeted tests.

    ## Commands

    ```bash
    bun install
bun run test
bun run verify
bun run ci:local
    ```

    ## Key Files

    - `src/core/`
- `src/commands/`
- `src/mcp/`
- `test/`
- `docs/`

    ## Gotchas

    - Trust boundary（信任边界）是核心：远程 MCP 调用不能获得本地 CLI 权限。
- `测试输出不要通过 tail/head 截断，失败信息必须完整保留。`
- `版本与发布规则以项目自身 VERSION/package/CHANGELOG 机制为准。`

    ## Verification

    - Documentation-only changes: run `uv run --with "pyyaml" python "../../bin/ssot/doc-ssot-lint.py" --json` from this project or from the workspace root.
    - Code changes: run the narrowest relevant project test first, then broaden if shared contracts changed.
    - Cross-layer behavior: verify the caller and the callee, not just the touched module.

    ## SSOT Pointers

    - Agent installation: [`INSTALL_FOR_AGENTS.md`](INSTALL_FOR_AGENTS.md)
    - Resolver contract: [`skills/RESOLVER.md`](skills/RESOLVER.md)
    - LLM context index: [`llms.txt`](llms.txt)
    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer index: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)
    - Project metadata: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)
    - Runtime state: [`../../.omo/state/system.yaml`](../../.omo/state/system.yaml)
