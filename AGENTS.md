# AGENTS.md — OMO

    > Scope: project-local developer guide for `omo`.
    > Workspace rules live in [`../../AGENTS.md`](../../AGENTS.md); project metadata lives in [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml).

    ## Role

    - Layer: L2
    - Stack: Python / uv / pytest
    - Responsibility: 治理内核：Phase/Task/Debt/Audit 生命周期

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
uv run python -m omo.cli governance audit
uv run python -m omo.cli lint direct-omo-io
    ```

    ## Key Files

    - `src/omo/cli.py`
- `src/omo/mcp_server.py`
- `src/omo/omo_ingress*.py`
- `src/omo/omo_lint*.py`
- `src/omo/_shared/`

    ## Gotchas

    - `不要直接写 ../../.omo/，状态变更走 OMO CLI/MCP/broker。`
- `新增治理写面必须同时有 runtime 实现、truth registry、lint/CI 门禁。`
- `CLI/MCP 工具数量以代码和 docs/project-registry.yaml 为准。`

    ## Verification

    - Documentation-only changes: run `uv run --with "pyyaml" python "../../bin/doc-ssot-lint.py" --json` from this project or from the workspace root.
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
