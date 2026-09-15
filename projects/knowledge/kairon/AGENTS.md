---
title: AGENTS
type: doc
status: active
---

# AGENTS.md — kairon

    > Scope: project-local developer guide for `kairon`.
    > Workspace rules live in [`../../AGENTS.md`](../../AGENTS.md); project metadata lives in [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml).

    ## Role

    - Layer: L2
    - Stack: Python / uv workspace / pytest
    - Responsibility: 知识工程与研究引擎 monorepo

    Do not copy volatile facts such as test counts, tool counts, service counts, ports, or current health into this file.

    ## Before Editing

    1. Read this file and [`CLAUDE.md`](CLAUDE.md) when it exists.
    2. Check `git status --short` inside this project and at the workspace root.
    3. Read the specific source or tests you are about to change.
    4. Prefer project-local commands and targeted tests.

    ## Commands

    ```bash
    uv sync
make test-diff
make lint
    ```

    ## Key Files

    - `pyproject.toml`
- `packages/`
- `packages/kos/`
- `packages/eidos/`
- `packages/minerva/`
- `packages/ontoderive/`

    ## Gotchas

    - `包清单和数量以 ../../docs/project-registry.yaml 与 pyproject.toml 为准。`
- 修改单包优先 make test-diff，跨包契约变更再扩大测试。
- 不要把派生日志或运行快照写进长期说明文档。

    ## Verification

    - Documentation-only changes: run `uv run --with "pyyaml" python "../../bin/ssot/doc-ssot-lint.py" --json` from this project or from the workspace root.
    - Code changes: run the narrowest relevant project test first, then broaden if shared contracts changed.
    - Cross-layer behavior: verify the caller and the callee, not just the touched module.

    ## SSOT Pointers

    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer index: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)
    - Project metadata: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)
    - Runtime state: [`../../.omo/state/system.yaml`](../../.omo/state/system.yaml)

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **kairon** (18989 symbols, 35261 relationships, 490 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact analysis before editing.** Use `impact({target: "symbolName", direction: "upstream"})` (MCP) or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .` (CLI fallback); report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/kairon/context` | Codebase overview, check index freshness |
| `gitnexus://repo/kairon/clusters` | All functional areas |
| `gitnexus://repo/kairon/processes` | All execution flows |
| `gitnexus://repo/kairon/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
