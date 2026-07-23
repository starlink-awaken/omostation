# CLAUDE.md — omostation AI Context Loader

> 最后更新: 2026-07-03
> Purpose: session startup protocol for AI agents.
> Detailed engineering rules live in [`AGENTS.md`](AGENTS.md).
> Stable architecture contracts live in [`ARCHITECTURE.md`](ARCHITECTURE.md).
> Document ownership is governed by [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md).

## 0. This Repo At A Glance

`omostation` is the root workspace for **eCOS v6**: a multi-project workspace for knowledge engineering, agent governance, BOS service routing, runtime orchestration, and personal/work knowledge operations.

- **Shape**: a polyglot monorepo. Sub-projects live under `projects/*` and are mostly independent git submodules — Python via `uv`, TypeScript via `bun`, plus Docker. Each sub-project has its own `AGENTS.md` / `CLAUDE.md` / `Makefile`; read it before editing that project.
- **Architecture skeleton** (concepts only — full contracts in [`ARCHITECTURE.md`](ARCHITECTURE.md)): the `5+4+1+1` layering (L0 protocol → L1 runtime → L2 kernel → L3 entry → L4 docs), the `X1-X4` governance axes, and BOS URI domain routing. Layer/project placement → [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md); BOS domains → ARCHITECTURE.md §4; entry surfaces → ARCHITECTURE.md §3.
- **Document division of labor** (orthogonal SSOT — each doc owns one dimension):

  - runtime facts → machine-readable SSOT (`.omo/state/system.yaml`, `docs/project-registry.yaml`, `protocols/*-registry.yaml`)
  - stable architecture → [`ARCHITECTURE.md`](ARCHITECTURE.md) / [`LAYER-INDEX.md`](LAYER-INDEX.md)
  - operating rules → [`AGENTS.md`](AGENTS.md) + this file
  - front-door entry → [`README.md`](README.md)
  - **system navigation** → [`docs/SYSTEM-INDEX.md`](docs/SYSTEM-INDEX.md) (NEW: unified navigation hub)

> **First Stop**: Read [`docs/SYSTEM-INDEX.md`](docs/SYSTEM-INDEX.md) to understand the workspace structure, then use the specialized indexes:
>
> - [`docs/INDEX-PROJECTS.md`](docs/INDEX-PROJECTS.md) — find projects by layer/stack
> - [`docs/INDEX-TOOLS.md`](docs/INDEX-TOOLS.md) — find tools and scripts
> - [`docs/INDEX-KNOWLEDGE.md`](docs/INDEX-KNOWLEDGE.md) — find ADRs, audits, patterns
> - [`docs/INDEX-AGENTS.md`](docs/INDEX-AGENTS.md) — find skills and agent setup
>
> **This file is a navigation layer only.** It does not duplicate project counts, ports, service inventories, test counts, phase, health scores, layer tables, or rule registries. Hard-coding those violates `doc-ssot-contract` and fails `bin/ssot/doc-ssot-lint.py`.

## 1. Startup Protocol

Load context before changing code or governed state. Two phases — run Step A when you need to align your mental model with historical decisions; run Step B before every editing session.

### Step A · Situational load (KOS cold-start — first turn, or when realigning to architecture)

> [!IMPORTANT]
> **KOS (Knowledge Operating System) Hardware Cold-Start Protocol**
> You are equipped with `mcp-server-kos` as your external read-only hard drive.
> To align your mental model and avoid historical architectural regressions, run this KOS query sequence:
>
> 1. **Query Current Decisions & Goals**:
>    `mcp-server-kos::query_custom_sql(sql="SELECT doc_id, title, canonical_path FROM documents WHERE canonical_path LIKE '%BRIEF.md%' LIMIT 1")`
>    Read the resulting BRIEF.md path. It carries active technical debts (needs-human) and X3 metrics.
> 2. **Traverse ADR Decisions**:
>    `mcp-server-kos::search_kos(query="ADR-012")`
>    Pay attention to ADR-0124 (S1 retrospective) and ADR-0125 (S2 retrospective).
> 3. **Identify Domain Schemas**:
>    `mcp-server-kos::list_entities(limit=50)`

### Step B · Workflow load (every editing session)

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
```

Read the SSOT files reported by `bootstrap` for task-specific runtime facts — **do not copy their values into this document** (they drift quickly). If MCP context is available, prefer the cockpit `workspace_context` tool.

### Step B.1 · RED LINE — 需求迭代强制 Workflow（ADR-0203）

**所有需求迭代（功能/缺陷/运维落地、治理/SSOT/ADR、交付 closeout）必须先 `start` 再改文件。**  
SSOT: `agent-workflows.yaml::requirement_iteration_policy`（`mode: required`）。  
细节: [`AGENTS.md` §1.6](AGENTS.md) · [`.omo/standards/agent-workflow-contract.md` §3.1](.omo/standards/agent-workflow-contract.md) · [ADR-0203](.omo/_knowledge/decisions/0203-requirement-iteration-workflow-mandatory.md)。

```bash
# 有 diff 时先选对 workflow（防错位 project-code-change）
uv run --with "pyyaml" python "bin/agent-workflow.py" suggest --from-diff --profile <agent-profile>
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> \
  --profile <agent-profile> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
```

豁免仅限：纯只读、`observer-audit`、用户书面 waiver（模板 [`docs/operations/workflow-waiver-template.md`](docs/operations/workflow-waiver-template.md)）。跳过 workflow 直接交付 = 违规。

## 1.5 P74 Workflow Solidification Check (ADR-0130)

After bootstrap, every agent MUST verify P74 health. P74 is the常态化 mechanism
(常态化机制) for agent-workflow silence detection — see `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`.

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance --json
```

Read `.p74_solidification.warn_count`:

- `0`: continue
- `> 0` (any silent workflow counts; `handoff-resume` and `observer-audit` no longer
  excluded per ADR-0211 §D1): treat as governance signal.
  Read `.omo/standards/p74-solidification-contract.md` §3 decision tree for actions.
  If workflow has neither `has_recent_run` nor `has_check_coverage`, register it via
  `agent-workflows.yaml::diff_checks`. Extending `silent_workflow_policy.excluded_workflows`
  is no longer supported (field removed in ADR-0211 §D1).

The `silent_workflow_policy` field in `agent-workflows.yaml` is the SSOT for
silent workflow classification. Per-workflow `run_frequency` field (on_demand /
periodic / continuous) drives the warn_after threshold (30d / 7d / 1d).

## 2. Session Role

`CLAUDE.md` is the lightweight context loader. It answers only:

- What must be read first?
- Which files are authoritative?
- Which operations are unsafe without a broker or explicit user request?
- Where is deeper guidance found?

It must not duplicate project tables, architecture diagrams, historical closeout reports, rule registries, test counts, port values, or generated snapshots.

## 3. Mandatory Boundaries

The authoritative SSOT map (all fact types and sources) lives in [`ARCHITECTURE.md` §1](ARCHITECTURE.md). The table below lists only the boundaries most relevant to session startup.

| Topic | Rule | Read More |
|------|------|-----------|
| Runtime state | Read from `.omo/state/system.yaml`; do not hard-code | [`ARCHITECTURE.md` §1](ARCHITECTURE.md) |
| Runtime projection refresh | Use `uv run --project projects/omo omo state sync`; do not run ad-hoc generator scripts from hooks | [`.omo/_knowledge/decisions/0128-state-generation-concurrency.md`](.omo/_knowledge/decisions/0128-state-generation-concurrency.md) |
| Governed `.omo/` writes | Use `omo` CLI/MCP or approved broker, not ad-hoc file I/O | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |
| Ports | Read and register through `protocols/port-registry.yaml` | [`ARCHITECTURE.md` §1](ARCHITECTURE.md) |
| Vault paths | Read from `protocols/vault-paths.yaml`; do not hard-code `~/Documents/` paths | [`ARCHITECTURE.md` §1](ARCHITECTURE.md) |
| Project metadata | Read from `docs/project-registry.yaml` | [`docs/project-registry.yaml`](docs/project-registry.yaml) |
| Agent workflows | Use `bin/agent-workflow.py`; do not rely on prompt memory alone | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |

## 4. Working Discipline

1. For work with more than a couple of steps, keep a visible todo list.
2. Read the target project `AGENTS.md` / `CLAUDE.md` before editing that project.
3. Use `rg` for text discovery; for callers/impact prefer codebase-memory MCP (see [`docs/operations/codebase-memory.md`](docs/operations/codebase-memory.md)).
4. Use the available file-editing tools (Edit, Create, MultiEdit, or `apply_patch`) for manual edits.
5. Do not delete, reset, move, commit, or push unless explicitly confirmed. See [`AGENTS.md` §6](AGENTS.md#6-git-and-submodules) for the full git and submodule policy.
6. If a governance protocol demands a commit but the current user/session policy does not authorize one, finish the working-tree changes, report the exact files, and ask for explicit commit confirmation.

## 5. Common Commands

**Gate & lint:**

```bash
make ci-local                               # 本地一键跑全部门 (ci-local-fast 超集, Makefile:105)
make check-layers                           # 分层依赖检查 (docs/layer-contract.yaml)
make gac-local-gate
uv run --with "pyyaml" python "bin/gac/gac-local-gate.py" --scope files --file <path> --json
uv run --with "pyyaml" python "bin/ssot/doc-ssot-lint.py" --json
uv run --with "pyyaml" python "bin/ssot/ssot-guardian.py"
```

**SSOT 变更追踪:**

```bash
make ssot-status                            # SSOT 变更状态检查
make ssot-log                               # SSOT 审计日志查看
make ssot-sync                              # SSOT 变更记录到审计日志
make sync-submodules                        # 推送子模块未推送的 commit 到远程
```

**Agent workflow lifecycle** (`bootstrap` → inspect → `start` → `claim` → `verify` → `closeout` → `compliance`):

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
uv run --with "pyyaml" python "bin/agent-workflow.py" list
uv run --with "pyyaml" python "bin/agent-workflow.py" agents
uv run --with "pyyaml" python "bin/agent-workflow.py" integrations
uv run --with "pyyaml" python "bin/agent-workflow.py" adapters
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> --profile <agent-profile> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" verify <run-id> --from-diff --execute
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" doctor
```

**State sync:**

```bash
uv run --project "projects/omo" omo state sync --dry-run --json
uv run --project "projects/omo" omo state sync --json
```

**Tests — project-level and single-test:**

```bash
bash "tests/integration/run-all.sh"          # root integration suite
cd "projects/kairon" && make test-diff        # kairon (Python) — changed-surface tests
cd "projects/gbrain" && bun test              # gbrain (TypeScript)
```

Run a single test with each framework's native filter (see the target project's `AGENTS.md` for project-specific targets):

- Python (`uv run pytest`): `pytest -k "test_name"` or `pytest path/to/test.py::TestClass::test_method`
- TypeScript (`bun test`): `bun test --filter "pattern"`
- cockpit-ui: `npm run build` / `bun run build`
- observability: `docker compose config -q`

## 6. Routing Hints

### 6a. By document

| Need | Route |
|------|-------|
| Workspace architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Layer/project placement | [`LAYER-INDEX.md`](LAYER-INDEX.md) |
| Current debts & goals | [`BRIEF.md`](BRIEF.md) · [`.omo/goals/current.yaml`](.omo/goals/current.yaml) |
| Agent development rules | [`AGENTS.md`](AGENTS.md) — esp. §6 git/submodules, §9 closeout, §10 Round Workflow (ADR-0148) |
| Project metadata | [`docs/project-registry.yaml`](docs/project-registry.yaml) |
| System panorama & BOS routing | [`docs/PANORAMA.md`](docs/PANORAMA.md) |
| Architecture deep-dive | [`docs/ARCHITECTURE-DETAILED-MAP.md`](docs/ARCHITECTURE-DETAILED-MAP.md) |
| Functional capability map | [`docs/FUNCTIONAL-CAPABILITY-MAP.md`](docs/FUNCTIONAL-CAPABILITY-MAP.md) |
| Agora callchain | [`docs/I0-AGORA-CALLCHAIN.md`](docs/I0-AGORA-CALLCHAIN.md) |
| Vision & roadmap | [`docs/VISION-ROADMAP.md`](docs/VISION-ROADMAP.md) |
| OMO governance kernel rules | [`projects/omo/CLAUDE.md`](projects/omo/CLAUDE.md) |
| Executable agent workflows | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) |
| AGCP status/scoped gate/claim policy | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |
| Internal integration contracts | `uv run --with "pyyaml" python "bin/agent-workflow.py" integrations` |
| MOF capabilities | [`.omo/_truth/registry/mof-capabilities.yaml`](.omo/_truth/registry/mof-capabilities.yaml) |
| External adapter contracts | `uv run --with "pyyaml" python "bin/agent-workflow.py" adapters` |
| External adapter health | `uv run --with "pyyaml" python "bin/agent-workflow.py" doctor` |
| L0/SSOT/M0/MOF alignment audit | [`.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md`](.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md) |
| Agent 红线/灰线 (severity) | `docs/generated/agent-redlines.md` (gitignored 运行时生成; `make gen-agent-redlines` 或 `python3 bin/mof/gen-agent-redlines.py`; executor ∈ {hook_pre_edit, ci_gate} → red, 否则 gray; ADR-0171) |
| Codebase knowledge graph (callers/impact) | [`docs/operations/codebase-memory.md`](docs/operations/codebase-memory.md) |

### 6b. By task — "I want to change X, where do I look first?"

| Task | First read |
|------|-----------|
| BOS service / route | [`projects/agora/etc/bos-services.yaml`](projects/agora/etc/bos-services.yaml) · [`docs/I0-AGORA-CALLCHAIN.md`](docs/I0-AGORA-CALLCHAIN.md) |
| Governance rule (X1-X4 / GaC) | [`.omo/_truth/registry/governance-checks.yaml`](.omo/_truth/registry/governance-checks.yaml) · [`docs/generated/agent-gac-rules.md`](docs/generated/agent-gac-rules.md) |
| Port assignment | [`protocols/port-registry.yaml`](protocols/port-registry.yaml) (read-only for agents; register through it) |
| Runtime state / health | [`.omo/state/system.yaml`](.omo/state/system.yaml) · refresh via `omo state sync` |
| L0 / MOF constraint | [`projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`](projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml) |
| Add / change an agent workflow | [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) · [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |
| Document SSOT contract | [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md) |
| Write an ADR | [`.omo/_knowledge/decisions/INDEX.md`](.omo/_knowledge/decisions/INDEX.md) · [`.omo/standards/adr-process.md`](.omo/standards/adr-process.md) |
| Project layer placement | [`docs/project-registry.yaml`](docs/project-registry.yaml) → [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md) |
| Land changes to root `main` | [`bin/gac/gac-worktree.sh`](bin/gac/gac-worktree.sh) (claim/submit/merge) · [`AGENTS.md` §6.1](AGENTS.md) · [`docs/AGENT-ISOLATION-ROLLOUT.md`](docs/AGENT-ISOLATION-ROLLOUT.md) |
| Code callers / impact / structure graph | [`docs/operations/codebase-memory.md`](docs/operations/codebase-memory.md) · MCP `codebase-memory-mcp` · skill `codebase-memory` |

## 7. Closeout

```bash
git status --short
make gac-local-gate
uv run --with "pyyaml" python "bin/ssot/ssot-guardian.py"
```

Run broader tests only when the edited surface warrants them. Documentation-only changes usually need the documentation SSOT check plus a clear diff review. For the full closeout checklist (including reporting files changed and checks skipped), see [`AGENTS.md` §9](AGENTS.md#9-closeout-checklist).

## 🧬 Onboarding Consensus (🧬 历史演进避坑基因)

> **自动刷新时间**: 2026-07-06 15:44:53 | 模式: RAG Top-2 按需激活
> 新进 Agent 必须通读并深度对齐以下前人沉淀的历史避坑基因，严禁在同一坑中二次栽倒：

- **P74 — Workflow Solidification Pattern (常态化工作流沉默治理)** ([p74-workflow-solidification-pattern.md](file:///Users/xiamingxing/Workspace/.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md))
  > 任一即触发 P74 评估: 1. **沉默 workflow**:registry 登记 ≥ 1 周,无 `agent_workflow_start` 事件。 2. **错位 workflow**:实际做的事 ≥ 3 次,却走通用 `project-code-change` 而非专属 workflow。

- **P73 Truth-Driven Engineering Pattern — eCOS 多迁移/并发/声明执行鸿沟下的工程纪律** ([p73-truth-driven-engineering-pattern.md](file:///Users/xiamingxing/Workspace/.omo/_knowledge/patterns/p73-truth-driven-engineering-pattern.md))
  > | 陷阱 | 症状 | 本轮案例 | |------|------|---------| | **D1** 凭路径直觉判存在性 | 报"X 零实现/不存在/悬空" 其实文件已迁移或运行时写面未创建 | 连续 3 轮把 debt(空=运行时写面正常) / task(卡 ingress delivery) / GaC(3 drift 非 129) 判错 |
