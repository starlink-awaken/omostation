---
type: ssot
owner: governance-team
last_updated: 2026-09-03
---

# CLAUDE.md — omostation AI Context Loader

> 最后更新: 2026-09-03
> Purpose: session startup protocol for AI agents.
> Detailed engineering rules live in [`AGENTS.md`](AGENTS.md).
> Stable architecture contracts live in [`ARCHITECTURE.md`](ARCHITECTURE.md).
> Document ownership is governed by [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md).

## 0. This Repo At A Glance

`omostation` is the root workspace for **eCOS v6**: a multi-project workspace for knowledge engineering, agent governance, BOS service routing, runtime orchestration, and personal/work knowledge operations.

- **Shape**: a polyglot monorepo. Sub-projects live under `projects/*` and are mostly independent git submodules — Python via `uv`, TypeScript via `bun`, plus Docker. Each sub-project has its own `AGENTS.md` / `CLAUDE.md` and may expose project-local build commands; read its guidance before editing.
- **Architecture skeleton** (concepts only — full contracts in [`ARCHITECTURE.md`](ARCHITECTURE.md)): the `5+4+1+1` layering (L0 protocol → L1 runtime → L2 kernel → L3 entry → L4 docs), the `X1-X4` governance axes, and BOS URI domain routing. Binding runtime grammar is **道法术器 (DFSQ)** nested on MOF plus **脊面运行模式 (SFOP)** slots — [`docs/architecture/dao-fa-shu-qi.md`](docs/architecture/dao-fa-shu-qi.md) and [`docs/architecture/os-operating-pattern-v1.md`](docs/architecture/os-operating-pattern-v1.md). Agents must obey slot grammar (unique Mesh dispatcher, no parallel OS) rather than adding AGE-v2/resident/BCOS as a second control plane. Layer/project placement → [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md); BOS domains → ARCHITECTURE.md §4; entry surfaces → ARCHITECTURE.md §3.
- **Document division of labor** (orthogonal SSOT — each doc owns one dimension):

  - runtime facts → machine-readable SSOT (`.omo/state/system.yaml`, `docs/project-registry.yaml`, `protocols/*-registry.yaml`)
  - stable architecture → [`ARCHITECTURE.md`](ARCHITECTURE.md) / [`LAYER-INDEX.md`](LAYER-INDEX.md)
  - operating rules → [`AGENTS.md`](AGENTS.md) + this file
  - front-door entry → [`README.md`](README.md)
  - **system navigation** → [`docs/SYSTEM-INDEX.md`](docs/SYSTEM-INDEX.md) (NEW: unified navigation hub)
  - **agent capabilities & board consensus** → [`.agents/skills/bdsk-virtual-board/SKILL.md`](.agents/skills/bdsk-virtual-board/SKILL.md) (B.D.S.K. Mode-A/B 4-Corner debate matrix & AetherForge/omlxc local compute architecture)

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
make agent-workflow-bootstrap
make agent-workflow-status
```

Read the SSOT files reported by `bootstrap` for task-specific runtime facts — **do not copy their values into this document** (they drift quickly). If MCP context is available, prefer the cockpit `workspace_context` tool.

### Step B.0 · 全局状态快速感知 (Multi-Agent Swarm Status)

在开工或排查前，先运行状态快照：

```bash
make omo-status        # 或 bin/omo-status：<0.2s 秒级 Rich 快照 (Agent心跳/锁/子仓/BET)
make omo-top           # 或 bin/omo-top：Textual 实时 4 象限互动大盘
```

### Step B.0.5 · 架构约束检查 (每次编辑会话)

编辑架构相关文件前，必须检查以下约束:

1. **场景卡生命周期**: 必须按 draft→shadow→assisted→supervised→routine 顺序升级
2. **业务域分类**: 每个场景卡必须有 domain 字段 (work/health/research/knowledge/governance)
3. **脚本配额**: 新增 bin/ 脚本必须同步归档旧脚本 (add 1 = delete 1)
4. **SSOT 引用**: 优先引用 `.omo/standards/` 下的标准文件，不要硬编码运行时值

### Step B.1 · 需求迭代强制 Workflow（ADR-0203）

所有需求迭代必须先 `start` 再改文件。详见 [`AGENTS.md` §1.1](AGENTS.md)。

### Step B.2 · 三年规划执行台账

不确定当前该做哪件事时，读台账，不要自行拟定任务。详见 [`AGENTS.md` §1.4](AGENTS.md)。

### Step B.3 · 多 Agent 并行的 Git 纪律

共享主树上并行的 agent 会互相删除产物。详见 [`AGENTS.md` §1.3](AGENTS.md) · skill `git-discipline`。

## 1.5 P74 Workflow Solidification Check (ADR-0130)

After bootstrap, every agent MUST verify P74 health. P74 is the常态化 mechanism
(常态化机制) for agent-workflow silence detection — see `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md`.

```bash
make agent-workflow-compliance
```

Read `.p74_solidification.warn_count`:

- `0`: continue
- `> 0` (any silent workflow counts; `handoff-resume` and `observer-audit` no longer
  excluded per ADR-0211 §D1): treat as governance signal.
  Read `.omo/standards/p74-solidification-contract.md` §3 decision tree for actions.
  If workflow has neither `has_recent_run` nor `has_check_coverage`, register it via
  `agent-workflows/::diff_checks`. Extending `silent_workflow_policy.excluded_workflows`
  is no longer supported (field removed in ADR-0211 §D1).

The `silent_workflow_policy` field in `agent-workflows/` is the SSOT for
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

The authoritative SSOT map (all fact types, sources, and boundaries) lives in [`ARCHITECTURE.md` §1](ARCHITECTURE.md). Read it before hard-coding any runtime fact, port, vault path, or governed-state write.

## 4. Working Discipline

1. For work with more than a couple of steps, keep a visible todo list.
2. Read the target project `AGENTS.md` / `CLAUDE.md` before editing that project.
3. Use `rg` for text discovery; for callers/impact prefer codebase-memory MCP (see [`.omo/_archive/operations-2026H1/codebase-memory.md`](.omo/_archive/operations-2026H1/codebase-memory.md)).
4. Use the available file-editing tools (Edit, Create, MultiEdit, or `apply_patch`) for manual edits.
5. Do not delete, reset, move, commit, or push unless explicitly confirmed. See [`AGENTS.md` §6](AGENTS.md#6-git-and-submodules) for the full git and submodule policy.
6. If a governance protocol demands a commit but the current user/session policy does not authorize one, finish the working-tree changes, report the exact files, and ask for explicit commit confirmation.

## 5. Common Commands

<!-- doc-ssot-lint: raw form "bin/agent-workflow.py" bootstrap, "bin/agent-workflow.py" closeout, "bin/agent-workflow.py" compliance -->

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap   # 单入口: 加载 SSOT 运行时事实
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>   # 闭环收尾
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance  # 合规审计
```

For the full command reference (gate & lint, SSOT tracking, agent workflow lifecycle, state sync, scene cards & journeys, tests), see [`AGENTS.md` §5](AGENTS.md).

## 6. Routing Hints

The authoritative SSOT map (fact types → sources) lives in [`ARCHITECTURE.md` §1](ARCHITECTURE.md). Use the INDEX docs to narrow by category:

| Need | Route |
|------|-------|
| Projects by layer/stack | [`docs/INDEX-PROJECTS.md`](docs/INDEX-PROJECTS.md) |
| Tools and scripts | [`docs/INDEX-TOOLS.md`](docs/INDEX-TOOLS.md) |
| ADRs, audits, patterns | [`docs/INDEX-KNOWLEDGE.md`](docs/INDEX-KNOWLEDGE.md) |
| Agent skills & setup | [`docs/INDEX-AGENTS.md`](docs/INDEX-AGENTS.md) |
| System navigation hub | [`docs/SYSTEM-INDEX.md`](docs/SYSTEM-INDEX.md) |
| Scene cards & journeys | [`docs/scene-cards/`](docs/scene-cards/) · [`docs/journey-specs/`](docs/journey-specs/) |
| Code callers / impact | [`.omo/_archive/operations-2026H1/codebase-memory.md`](.omo/_archive/operations-2026H1/codebase-memory.md) |

For task-level routing (BOS, governance, ports, ADRs, main landing, scene admission), see [`ARCHITECTURE.md` §1](ARCHITECTURE.md) and the INDEX docs above.

## 6.5 Anti-Corrosion Five-Layer Framework (ADR-0431)

Rules carry lifecycles (`added_at`/`review_before`/`justification` in `governance-checks.yaml::gac.rules`). Check health: `python3 bin/gac/rules-lifecycle.py` (weekly cron; expired → subtraction candidates). Human authority layers L1-L5 (charter/context/decision/constraints/unknown) are orthogonal — see `.omo/_knowledge/decisions/0431-anti-corrosion-five-layer-framework.md`. BOS: `bos://governance/anti-corrosion/*`. MCP: `rules_lifecycle` tool.


## 7. Closeout

```bash
git status --short
make gac-local-gate
make ssot-guardian
make scene-card-check    # scene card 变更时
make journey-check       # journey spec 变更时
make adr-number-check    # ADR 变更时
```

Run broader tests only when the edited surface warrants them. Documentation-only changes usually need the documentation SSOT check plus a clear diff review. For the full closeout checklist (including reporting files changed and checks skipped), see [`AGENTS.md` §9](AGENTS.md#9-closeout-checklist).

## 🧬 Onboarding Consensus (🧬 历史演进避坑基因)

> **自动刷新时间**: 2026-07-06 15:44:53 | 模式: RAG Top-2 按需激活
> 新进 Agent 必须通读并深度对齐以下前人沉淀的历史避坑基因，严禁在同一坑中二次栽倒：

- **P74 — Workflow Solidification Pattern (常态化工作流沉默治理)** ([p74-workflow-solidification-pattern.md](.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md))
  > 任一即触发 P74 评估: 1. **沉默 workflow**:registry 登记 ≥ 1 周,无 `agent_workflow_start` 事件。 2. **错位 workflow**:实际做的事 ≥ 3 次,却走通用 `project-code-change` 而非专属 workflow。

- **P73 Truth-Driven Engineering Pattern — eCOS 多迁移/并发/声明执行鸿沟下的工程纪律** ([p73-truth-driven-engineering-pattern.md](.omo/_knowledge/patterns/p73-truth-driven-engineering-pattern.md))
  > | 陷阱 | 症状 | 本轮案例 | |------|------|---------| | **D1** 凭路径直觉判存在性 | 报"X 零实现/不存在/悬空" 其实文件已迁移或运行时写面未创建 | 连续 3 轮把 debt(空=运行时写面正常) / task(卡 ingress delivery) / GaC(3 drift 非 129) 判错 |

## 治理活性自检 (2026-08-22 自进化框架)

```bash
python3 bin/gac/meta-doctor.py --workspace . --json   # 治理活性巡检
python3 bin/scheduler-compile.py --check               # 调度一致性
```

## Resident Agent 体系 (2026-08-23, WP-A~I / ADR-0396)

事件驱动常驻 agent 运行时：五类角色（sediment/decision/execute/monitor/heartbeat）+ 规则级路由订阅。详见 [`docs/architecture/resident-agent-system-v1.md`](docs/architecture/resident-agent-system-v1.md)。

```bash
make resident-status       # 运行状态快照 (daemon/events/sediment/alert/ledger)
make resident-roles        # 五类角色配置
make resident-daemon       # 单次 tick 调试
```

- 路由表 SSOT: `projects/omo/src/omo/resident/resident-routes.yaml`
- 角色 SSOT: `omo resident roles`（`projects/omo/src/omo/resident/roles.py`）
- MOF: `mof/m2/digital_agent.yaml`（DigitalAgent, tier=resident）· BOS: `bos://resident/*`
- agora MCP: `resident_status` / `resident_roles`（`projects/agora/src/agora/server/tools_resident.py`，委派 `omo resident status/roles`）

## BCOS 业务域系统 (2026-08-23, W1~W4)

业务闭环系统：信号路由 → 进化引擎 → 北极星价值度量。详见 [`docs/architecture/bcos-system-v1.md`](docs/architecture/bcos-system-v1.md)。

```bash
make bcos-evolve       # 进化引擎四阶段 (observe/propose/evaluate/approve, dry-run 默认)
make bcos-signals      # 统一信号路由 (W1-D2)
make bcos-north-star   # 北极星价值度量 v2
```

- 进化引擎: `bin/bc-os/evolution_engine.py`（EvolutionEngine 四阶段）
- 信号路由: `bin/bc-os/signal_router.py`（W1-D2, 公文/会议/调研/代码）
- 北极星: `bin/bc-os/north_star_meter_v2.py`（排除 self-data）
- MOF: `mof/m2/bcos_system.yaml`（BCOSystem）· BOS: `bos://bcos/*`
