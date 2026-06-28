# AGENTS.md — ecos

    > Scope: project-local developer guide for `ecos`.
    > Workspace rules live in [`../../AGENTS.md`](../../AGENTS.md); project metadata lives in [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml).

    ## Role

    - Layer: L0
    - Stack: Python / uv / pytest
    - Responsibility: 协议层：SSB、MOF、L0 约束与治理规则

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

    - `src/ecos/ssot/registry/L0-constraints.yaml`
- `src/ecos/ssot/mof/`
- `src/ecos/ssot/tools/`
- `src/ecos/l0/`

    ## Gotchas

    - `M1/M2/M3 节点数量以 ssot/mof 实际文件为准。`
- 新增约束要落注册表、工具和验证链，不能只改文档。

    ## Verification

    - Documentation-only changes: run `uv run --with "pyyaml" python "../../bin/doc-ssot-lint.py" --json` from this project or from the workspace root.
    - Code changes: run the narrowest relevant project test first, then broaden if shared contracts changed.
    - Cross-layer behavior: verify the caller and the callee, not just the touched module.

    ## SSOT Pointers

    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer index: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)
    - Project metadata: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)
    - Runtime state: [`../../.omo/state/system.yaml`](../../.omo/state/system.yaml)
