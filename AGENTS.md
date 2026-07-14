# AGENTS.md — runtime

    > Scope: project-local developer guide for `runtime`.
    > Workspace rules live in [`../../AGENTS.md`](../../AGENTS.md); project metadata lives in [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml).

    ## Role

    - Layer: L1
    - Stack: Python / uv / pytest
    - Responsibility: 服务生命周期、调度、健康监控与 KEI 沙箱

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
make fmt
make sync-state
    ```

    ## Key Files

    - `src/runtime/matrix.py`
- `src/runtime/scheduler.py`
- `src/runtime/kei.py`
- `src/runtime/cron_service/`
- `src/runtime/mcp_server.py`

    ## Gotchas

    - `运行状态和健康事实写入 OMO/SSOT，不在 README 维护快照。`
- 端口和 daemon 暴露面以协议注册表为准。

    ## Verification

    - Documentation-only changes: run `uv run --with "pyyaml" python "../../bin/ssot/doc-ssot-lint.py" --json` from this project or from the workspace root.
    - Code changes: run the narrowest relevant project test first, then broaden if shared contracts changed.
    - Cross-layer behavior: verify the caller and the callee, not just the touched module.

    ## SSOT Pointers

    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer index: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)
    - Project metadata: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)
    - Runtime state: [`../../.omo/state/system.yaml`](../../.omo/state/system.yaml)
