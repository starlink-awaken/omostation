---
type: ssot
owner: governance-team
last_updated: 2026-09-04
---

# AGENTS.md — Workspace Development Guide

> 最后更新: 2026-09-03
> Root operating guide for AI coding agents and developers. Keep this file operational. Put runtime facts in SSOT files, not here.

## 0. Worktree Policy (Mandatory)

> **Main workspace is read-only. Every new change starts from an isolated worktree.**

| Action | Required |
|--------|----------|
| New feature / fix / cleanup | `gac-worktree.sh claim <session>` |
| Submodule work | Child worktree via PASW |
| Direct commit to main | ❌ Prohibited |

```bash
# Create isolated worktree
bash bin/gac/gac-worktree.sh claim <session-name>
cd /Users/xiamingxing/ws-<session-name>

# After PR merged, retire
bash bin/gac/gac-worktree.sh retire <session-name>
```

**Full policy**: [`GOVERNANCE.md`](GOVERNANCE.md) § Worktree Isolation Policy

---

## 1. Read This First

Before editing:

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check `git status --short`.
4. **需求迭代强制 Workflow（ADR-0203）** — see §1.1. Run `bootstrap` → `status` → `start` → `claim` **before** any requirement delivery edit.
5. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
6. For multi-file or high-risk changes, explain the edit surface before applying patches.
7. **B.D.S.K. Virtual Board** — For high-risk architectural changes, refer to [`.agents/skills/bdsk-virtual-board/SKILL.md`](.agents/skills/bdsk-virtual-board/SKILL.md). All local/edge LLM inference MUST route through **AetherForge + omlxc v3.4.0 (`bos://compute/aetherforge/infer`)**.
8. **Multi-Agent Observability** — `make omo-status` (<0.2s Rich Panel) and `make omo-top` (real-time Textual 1.x control plane).

### Governance Capabilities (ADR-0190..0199)

| ADR | Purpose | Entry / CLI |
|-----|---------|-------------|
| ADR-0190 MOF Dynamic Constraint | Real-time action governance (<0.2ms) | `ecos-constraint explain/audit/eval/drift` |
| ADR-0191 Dual-Plane (Workspace × Documents) | Documents = truth/SOPs; Workspace = code/CLIs | `ecos-constraint documents audit/guardrail` |
| ADR-0192 Domain Truth & Hygiene Patrol | `_entities/facts/*.yaml` (14-day freshness) | `make hygiene-patrol` |
| ADR-0193 Domain Policy-as-Code | `E-POL-WJ-001/002`, `E-POL-TF-001/002` | `ecos-constraint policy audit/explain/list` |
| ADR-0194 Truth Canvas, Chaos Drills, Pitfalls | Interactive observability, mutation testing | `make canvas-serve`, `make chaos-drill` |
| ADR-0195 Intent-to-Spec Compiler | NL prompt → structured execution DAG | `ecos-constraint intent compile` |
| ADR-0196 Shadow Challenger Loop | Multi-perspective adversarial red-team | `ecos-constraint challenge [--auto-patch]` |
| ADR-0197 Sovereign Compute & KV Snapshots | Local speculative execution (8B/14B Q4_K_M) | `omlxc fabric snapshot` |
| ADR-0198 Domain Cartridge Factory | Vertical governance package manager | `ecos-constraint cartridge list/export/validate` |
| ADR-0199 Unified BOS URI, Cockpit & Cognitive Workflow | Full-lifecycle integration | `cockpit intent/challenge/cartridge/fabric` |

**Binding architecture (DFSQ / SFOP) — obey, do not grow a parallel OS.**

- Theory: [`docs/architecture/dao-fa-shu-qi.md`](docs/architecture/dao-fa-shu-qi.md)
- Runtime slots: [`docs/architecture/os-operating-pattern-v1.md`](docs/architecture/os-operating-pattern-v1.md)
- Blocking law: `python3 bin/gac/check-sfop-slots.py` (CR-SFOP-01/02); `python3 bin/gac/check-execution-chain.py` (CR-EXEC-CHAIN-01)

Do **not** add a second dispatcher, a fifth ontology, or a new top-level human entry. Mesh (`COMP-WS-omo`) is the only active `S` slot. AGE-v2 / resident / BCOS are backends, projectors, or meters — not a second operating system.

## 1.1 RED LINE — Requirement iterations MUST use Agent Workflow (ADR-0203)

> SSOT: `.omo/_truth/registry/agent-workflows/::requirement_iteration_policy`
> 契约: `.omo/standards/agent-workflow-contract.md` §3.1

| 必须 | 禁止 |
|------|------|
| 任何功能/缺陷/运维落地、治理/SSOT/ADR、交付 closeout | 无 `start` 的 run-id 就改需求相关文件 |
| `bootstrap → start --profile → claim → verify → closeout` | 「先改完再补 workflow」 |
| 用 `list` 选对 workflow | 把 `observer-audit` / 只读探索当成可写豁免 |

**窄豁免**：纯只读问答；`observer-audit`；用户书面明确 waiver。

愿景→落地→复盘硬门：`start --bet` 把 `bet_id` 写入 run，`closeout`/`complete` 缺北极星/绑定/retro 会 halt。执行器 [`bin/plan/chain-bind-check.py`](bin/plan/chain-bind-check.py)，红线 `redlines.yaml::vision-to-retro-chain`。

**可执行闸门（ADR-0204）**：`compliance` / `status` 对 **已 stage** 的需求面路径检查是否存在 active run；无 run → **halt**（exit 1）。旁路：`AGCP_REQUIREMENT_ITERATION_GATE=0`。

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance
make agent-workflow-bootstrap && make agent-workflow-status
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> --profile <agent-profile> --bet <BET-ID> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" suggest --from-diff --profile <agent-profile>
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> \
  --profile <agent-profile> --bet <BET-ID> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>
```

## 1.2 P74 Solidification Quick Reference (ADR-0130)

常态化 agent-workflow silence 检测。详见 [ADR-0130](.omo/_knowledge/decisions/0130-p74-workflow-solidification.md)。

**SSOT**：`agent-workflows/::silent_workflow_policy`；`governance-checks.yaml`（4 CR-P74-* rules）。
**Tools**：`omo lint projection-guard` · `agent-workflow.py suggest --from-diff --profile <agent>` · `agent-workflow.py compliance --json`
**Skill**：[`.agents/skills/workflow-silence-detection/SKILL.md`](.agents/skills/workflow-silence-detection/SKILL.md)

若 `p74_solidification.warn_count > 0`，禁止投机启动 workflow。

## 1.3 Swarm coordination (G-CONV.7 / ADR-0220)

M1 hard pre-gate（并发 main conflict = 0）：

| Gate | Command | 状态 |
|------|---------|------|
| D1 ADR claim | `python3 bin/adr/next-adr-id.py --session <s> --claim` | ✅ 活跃 |
| D2 branch lock | ~~`gac-worktree.sh claim`~~ | 🏁 退役 |
| D3 shared claim | ~~pre-commit `claim-check`~~ | 🏁 退役 |
| D4 escape | `SWARM_ESCAPE_ID=...` · `bin/gac/swarm-git` | ✅ 活跃 |
| D5 submodule | pre-commit `submodule-guard` | ⚠️ 部分退役 |

**D0 铁律**：交付物必须 `git add` → `commit` → **`tag`**（或推独立远端分支）。
**逃生口唯一入口**：`SWARM_ESCAPE_ID=<id> bin/gac/swarm-git ...`。
**独立 clone 拓扑（T1-05）**：每个 delivery attempt 使用独立 clone。新 writer 使用 `~/agents/<actor>/attempts/<attempt>/ws`。

```bash
python3 bin/gac/agent-clone-onboard.py --apply
python3 bin/gac/clone-lifecycle.py onboard/snapshot/changeset/integrate/retire
```

> **共享 checkout 并发吸收**：并发 agent 会把共享树上 staged 改动直接 `add -A && commit` 成混合 commit。处理：① 不贸然 reset — 先 `git reflog -8` + `git show <sha> --stat`；② 验证是否已合入 main；③ 已合入则 `agent-workflow close --status blocked` 记录；④ 本地 main 分叉时 **勿 reset --hard**。
> **chore(state) 禁止直连 main (T10-58)**：state-sync / submodule-pointer 快照类提交一律走 worktree+PR（#2519 模式）。分支保护本就会拒绝 main 直推，留在本地 main 的 `chore(state)` 提交只会被 reset 成孤儿。`.githooks/commit-msg` 会在 main 上拦截该类提交（逃生口 `SWARM_ESCAPE_ID`）。

## 1.4 我该做什么 — 三年规划执行台账

不要自行拟定任务。读台账：
```bash
uv run --with pyyaml python bin/plan/bet-ledger.py status
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check <BET-ID>
```
SSOT [`docs/plans/3y-bet-ledger.yaml`](docs/plans/3y-bet-ledger.yaml) · 视图 [`docs/plans/3Y-BET-LEDGER.md`](docs/plans/3Y-BET-LEDGER.md) · skill `bet-execution`.

## 1.5 8D 全景元架构与全仓四大入口契约

系统由 **LifeOS 意图 ➔ C2G 策略 ➔ Goals 目标 ➔ Agora 蜂群 ➔ AetherForge 算力 ➔ AGE-v2 落地 ➔ MOS/KOS 记忆 ➔ X-Plane 熵减** 8 维空间组成。

1. **7D 终极可观测**：`cockpit panorama` / `make panorama`
2. **8D 全景追溯**：`cockpit compass trace <GOAL-ID>` / `make compass-trace`
3. **16 项目 4D 体检**：`cockpit project inspect <PROJ>` / `make project-inspect`
4. **场景卡与 Journey 校验**：`cockpit journey` / `make journey-validate`
5. **常态化守护**：必须维持 `make gac-local-gate` ALL GREEN PASS

## 2. Documentation SSOT Contract

| Document | Owns | Must Reference |
|----------|------|----------------|
| [`README.md`](README.md) | Front door and quick orientation | Architecture, registry, governance docs |
| [`CLAUDE.md`](CLAUDE.md) | AI session startup protocol | This file and target project docs |
| [`AGENTS.md`](AGENTS.md) | Workspace operating rules | SSOT registries for facts |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Stable architecture contracts | Registry files for counts and runtime values |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | Human-readable layer placement | `docs/project-registry.yaml` |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | Project metadata facts | Actual project metadata |
| [`.omo/_truth/registry/agent-workflows/`](.omo/_truth/registry/agent-workflows/) | Agent workflow facts | Executable workflow runner |
| [`.omo/_truth/registry/omo-governance-surfaces.yaml`](.omo/_truth/registry/omo-governance-surfaces.yaml) | OMO governance surfaces | Governance surface registry SSOT |
| [`.omo/_truth/registry/runtime-projections.yaml`](.omo/_truth/registry/runtime-projections.yaml) | Runtime projection registry | `omo-state-projection-guard.py` (P74) |
| [`.omo/_truth/registry/ci-surfaces.yaml`](.omo/_truth/registry/ci-surfaces.yaml) | CI 平面检查接线登记 | `check-ci-surfaces.py` |
| [`.omo/_truth/x1-governance-policies.yaml`](.omo/_truth/x1-governance-policies.yaml) | X1 governance policies | Governance policy SSOT |
| [`.omo/_truth/x2-freshness-rules.yaml`](.omo/_truth/x2-freshness-rules.yaml) | X2 freshness rules | Doc freshness SSOT |
| [`.omo/_truth/x3-value-stack.yaml`](.omo/_truth/x3-value-stack.yaml) | X3 value stack | Value chain SSOT |
| [`.omo/_truth/x4-consistency-rules.yaml`](.omo/_truth/x4-consistency-rules.yaml) | X4 consistency rules | Consistency SSOT |
| [`projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`](projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml) | L0 protocol constraints | Constraint SSOT |
| [`.omo/state/system.yaml`](.omo/state/system.yaml) | Runtime state | Runtime probes and OMO state sync |
| [`.omo/_control/governance-data.json`](.omo/_control/governance-data.json) | Runtime governance projection | `omo state sync` broker |

Do not hard-code current phase, health score, test counts, tool counts, service counts, source-file counts, port values, or generated rule inventories in Markdown. Use pointers.

The full documentation contract is [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md).

## 3. Architecture Summary

Stable architecture contracts live in [`ARCHITECTURE.md`](ARCHITECTURE.md). Project layer placement is generated from [`docs/project-registry.yaml`](docs/project-registry.yaml) into [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md).

**道法术器 (DFSQ/v1)** nests on MOF. Slot grammar + unique Mesh dispatcher (`COMP-WS-omo` = S): `python3 bin/gac/check-sfop-slots.py --json`. Constitution stack fuses into one execution-chain check: `python3 bin/gac/check-execution-chain.py --json`. Do not invent a parallel OS or a second dispatcher.

## 4. Governance Boundaries

| Surface | Rule |
|---------|------|
| `.omo/` | State/evidence plane. Do not add long-lived execution logic here. |
| `projects/omo/` | Governance kernel: schema, audit, sync, broker, lint, task/debt lifecycle. |
| `projects/c2g/` | Strategy ingress: pitch/bet materialization into governed tasks. |
| `projects/ecos/` | Protocol and MOF layer. |
| `spaces/` | User/tenant-space manifests. Treat as governed configuration. |
| `scripts/` | Removed 2026-08 (see ADR-0394). Tools live in [`bin/README.md`](bin/README.md). |
| `runtime/` | Runtime execution logs, sandbox, server.log. Do not edit manually. |
| `kos/` | Knowledge index (SQLite + snapshots). Runtime product, do not edit manually. |
| `bin/` | Governance tools (gac-*, doc-ssot-*, ssot-guardian, agent-workflow). |
| `config/` | Machine identity (X1 swarm trust `node_identity.json`). Do not edit manually. |
| `protocols/` | SSOT registries: port-registry, vault-paths, x-axis-registry. Read-only for agents. |
| `tests/` | Root-level unit and integration tests. Run via `bash tests/integration/run-all.sh`. |

For `.omo` or `spaces` mutations, use the registered broker/CLI path.

## 5. Essential Commands

### Agent Workflow 生命周期 (单入口)

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap       # 加载 SSOT 运行时事实
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance      # 合规审计 (P74)
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>   # 闭环收尾
```

### 治理门禁 (Gate & lint)

```bash
make gac-local-gate                          # 全量治理-as-Code 门禁
make ci-local                                # 本地一键全部门
make check-layers                            # 分层依赖检查
make doc-ssot-lint && make ssot-guardian
make gac-validate && make gac-drift
```

### 道法术器槽位 & 执行链覆盖 (DFSQ/v1)

```bash
python3 bin/gac/check-sfop-slots.py --json             # CR-SFOP-01/02/04/05/06 + CR-DFSQ-01/02
python3 bin/gac/check-execution-chain.py --json        # CR-EXEC-CHAIN-01
```

- **sfop-slots**: `COMP-WS-*` 必须自报合法 `sfop_slot` / `dao_layer`；活跃 Project 中 `S` 槽恰好一个且为 `COMP-WS-omo`。
- **execution-chain**: 融合 script-registry × ci-surfaces × cron × capability-registry × agent-workflows × `.agents/skills` × `.githooks`。

### 能力防腐 & 投影强制 (差距治理 S1/S5)

```bash
python3 bin/gac/check-capability-ownership.py          # CAP-OWN: 能力所有权 + 删除防腐
python3 bin/gac/check-derived-only-fast-track.py       # GOV-REBAL: 派生文档-only fast-track 判定
python3 bin/gac/auto-fix-loop.py                       # AUTO-FIX: 漂移检测→分类→修复闭环
python3 bin/gac/command-discovery.py                   # UX-NOISE: 命令密度/重复/易混淆定位
```

### SSOT 变更追踪 & Agent 工作流

```bash
make ssot-status && make ssot-log && make ssot-sync
make agent-workflow-bootstrap && make agent-workflow-status
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> --profile <agent-profile> --bet <BET-ID> --objective "<summary>"
make agent-workflow-closeout RUN_ID=<run-id>
```

### 运行态与治理状态

```bash
make state-sync-dry && make state-sync
uv run --with "pyyaml" python "bin/gac/governance-evolution.py" status --json
```

### 项目测试

```bash
bash "tests/integration/run-all.sh"          # root integration suite
cd "projects/knowledge/kairon" && make test-diff       # kairon (Python)
cd "projects/knowledge/gbrain" && bun test             # gbrain (TypeScript)
```

### 附加诊断工具

```bash
make gac-healthcheck && make evidence-smoke
python3 bin/gac/check-ci-surfaces.py                    # CI 平面可观测性 (ADR-0379)
python3 bin/gac/ci-check-runner.py --workflow governance-check.yml
```

### 模型驱动治理闭环 (L0↔MOF)

```bash
python3 bin/ssot/consumer_index.py           # L0 约束 → 16 抽象族/规则反向索引
python3 bin/ssot/m0_feedback.py              # M0 运行时快照 → 派生面漂移检测
python3 bin/ssot/governance_closed_loop.py   # 闭环端到端验证 (真实数据)
cd projects/ecos && uv run python3 bin/inference_engine.py  # DR-01~08 推理
```

### 链路闭环工具 (Phase 1-3)

```bash
# 决策收件箱
python3 bin/cockpit decide list / add / status

# 统一桥接运行时 (MetaOS↔OMO, Model-Driven↔ECOS, L4↔记忆层)
python3 bin/gac/bridge-runtime.py --status
python3 bin/gac/bridge-runtime.py --delegate metaos-omo audit_log

# 防腐管道接线 (G1/G2)
python3 bin/gac/corrosion-pipeline-connector.py --to-inbox

# 场景卡 → Journey
python3 bin/gac/scene-journey-connector.py --auto-create

# 价值证明闭环
python3 bin/gac/value-tracker.py --record 15.5
python3 bin/gac/value-tracker.py --update-north-star

# 自进化反馈循环
python3 bin/gac/self-evolution-loop.py --cycle
python3 bin/bc-os/evolution-proposal-triage.py --generate
python3 bin/bc-os/evolution-proposal-triage.py --auto-approve

# Goal 模式测试
python3 bin/gac/goal-mode-test.py --full-test

# 信号路由 (日历)
python3 bin/bc-os/signal_router.py --calendar events.ics

# 探测器心跳矩阵 (M3 仪式)
python3 bin/gac/probe-heartbeat-monitor.py --status

# 持续迭代
python3 bin/gac/weekly-review.py --generate
python3 lib/monthly_healthcheck.py --full
```

See [`bin/README.md`](bin/README.md) for the full tool catalog.

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, destructive checkout, or branch switching unless explicitly asked.
- **Submodule pointer update**: prefer `bash bin/ssot/submodule-pointer-transaction.sh --message "..."`.
- Never revert unrelated dirty files. Treat them as user or concurrent-agent work.
- **禁止 `sed -i` 做添加/删除条目操作**：用 Python `read → check → modify → write` 模式。
- **Check-before-fix 协议**：修改治理检查输入文件前，先读脚本的 `DEFAULT_*` 路径常量。
- **死循环自检**：连续两次执行相同操作得到相同异常结果时，立即停止并换策略。
- **子模块 commit 三步走**：① `cd projects/<sub> && git add && git commit` ② `git push`（子模块内）③ `cd 主仓 && git add projects/<sub> && git commit && push`。直接在主仓 commit 子模块内容会失败（`is in submodule`）。
- **pull --rebase 风险**：本地 commit 基于旧 main 时，`git pull --rebase` 可能丢弃本地改动。rebase 后用 `git reflog` 确认 commit 仍在；若丢失，用 `git cherry-pick` 恢复。

#### 高危 git 操作守门

- **`reset --hard` 前三确认**：① 当前分支 ② reset 目标 = 该分支的 origin 状态 ③ 工作树干净。
- **改"看起来是子项目"的代码前确认仓库边界**：先 `ls -d <path>/.git` + `git -C <path> remote -v`。

### 治理活性自检 (自进化框架)

```bash
python3 bin/gac/meta-doctor.py --workspace . --json    # 治理机制活性巡检
python3 bin/scheduler-compile.py --check               # 登记↔安装一致性校验
bash bin/gac/heartbeat-wrapper.sh <job_name> <command...>  # cron 心跳包装器
```

### Resident Agent 体系 (ADR-0396)

事件驱动常驻 agent 运行时（五类角色 + 规则级路由订阅），规格见 [`docs/architecture/resident-agent-system-v1.md`](docs/architecture/resident-agent-system-v1.md)。

```bash
make resident-status && make resident-roles && make resident-daemon
```

- 路由表 SSOT: `projects/omo/src/omo/resident/resident-routes.yaml`
- 角色 SSOT: `projects/omo/src/omo/resident/roles.py`
- BOS: `bos://resident/*`

### BCOS 业务域系统 (W1~W4)

业务闭环系统（信号路由 → 进化引擎 → 北极星价值度量），规格见 [`docs/architecture/bcos-system-v1.md`](docs/architecture/bcos-system-v1.md)。

```bash
make bcos-evolve && make bcos-signals && make bcos-north-star
python3 bin/bc-os/evolution_engine.py --json     # 四阶段 JSON 输出
```

### 6.1 PR 工作流

主仓 main 变更走 **per-session worktree + PR**。工具:`bin/gac/gac-worktree.sh`。

> **主树只读纪律（ADR-4443 v8 / P96，2026-08-31 起）**：workspace 根目录（主树）
> 不再作为任何 agent 的工作落点——只用于基线同步（`git pull --ff-only`）与
> gitignore 运行时区（台账/state/pitfalls）。所有编辑、commit、push 一律在专属
> worktree 执行。实证（2026-08-31 swarm retro，14 起 A 类事故）：主树曾被并行
> agent 分支接管 4 次、共享 index 卡 push、merge 污染分支——专属 worktree 是
> 零成本方案，gate 拦截是 5 分钟成本方案，主树工作是无上限成本方案。

```bash
bash bin/gac/gac-worktree.sh claim <session>   # 起隔离 worktree
bash bin/gac/gac-worktree.sh submit <session>   # push 分支 + 开 PR
bash bin/gac/gac-worktree.sh merge <session>    # squash 合并 PR
```

- **当前状态**: ✅ **blocking + branch protection 已启用** — 所有 main 变更必须走 worktree+PR。
- **子模块**: 已启用分支保护，但仍允许 direct push。详见 [`docs/SUBMODULE-PR-STRATEGY.md`](docs/SUBMODULE-PR-STRATEGY.md)。

## 7. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Root governance docs | `make gac-local-gate` plus `make ssot-guardian` |
| Python code (generic) | Targeted `uv run pytest` or project Makefile `test` target |
| kairon package | `make test-diff` from `projects/knowledge/kairon` |
| gbrain | `bun test` or targeted Bun test |
| cockpit-ui (TypeScript) | `npm run build` or `bun run build` from `projects/cockpit-ui` |
| observability (Docker) | `docker compose config -q` from `projects/observability` |
| Cross-project contract | Targeted tests on every touched consumer plus relevant integration smoke |
| Code exploration | Prefer codebase-memory MCP (`list_projects` → `search_graph` / `trace_path`) |

If a test cannot run, report why and what risk remains.

**已知 flaky 测试**：
- `tests/test_agent_workflow.py::test_start_run_dry_run_does_not_write_state`：并发 agent 写入 runs 目录导致断言失败，非代码问题。

## 8. Historical Patterns

Historical closeout details are useful evidence. Each pattern links to its full doc:

- [Agent mutation protocol](.omo/standards/agent-mutation-protocol.md) · [OMO governance surfaces](.omo/standards/omo-governance-surfaces.md) · [GaC North Star](.omo/_knowledge/gac/NORTH-STAR.md)
- [P75 convergence round](.omo/_knowledge/patterns/p75-convergence-round-pattern.md) · [P91 pyright sweep](.omo/_knowledge/patterns/p91-pyright-sweep-pattern.md) · [Delegation infra diagnosis](.omo/_knowledge/patterns/delegation-infra-diagnosis-pattern.md)
- [P43 closed-loop](.omo/_knowledge/patterns/p43-closed-loop-pattern.md) · [P71 baseline recovery](.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md) · [P72 follow-up completion](.omo/_knowledge/patterns/p72-follow-up-completion-pattern.md)
- [L0/SSOT/M0/MOF 对齐审计](.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md)
- [Executable agent workflows](.omo/standards/agent-workflow-contract.md) · [Governance evolution roadmap](docs/GOVERNANCE-EVOLUTION-ROADMAP.md)
- [State generation convergence](.omo/_knowledge/decisions/0128-state-generation-concurrency.md)
- [P78 triple-axis diagnostic](.omo/_knowledge/patterns/p78-triple-axis-diagnostic-pattern.md)
- **分支等价性判据**：判断"分支内容是否已合入 main"只用 **内容 diff**（`git diff origin/main...<branch>`）。

## 9. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Prefer `make agent-workflow-closeout RUN_ID=<run-id>` for governed runs.
4. Mention files changed and checks run.
5. Do not create commits unless explicitly requested and confirmed.
6. **大任务后复盘+固化** (P74 常态化精神):
   - **复盘触发**: 系统性分析/方案任务 / 多轮返工 / Stop hook 反馈后
   - **诊断前置 4 问 (P78)**: ①反证找了吗 ②查运行时实证了吗 ③读相关 ADR 了吗 ④扫了 `bin/ssot` + `.github/workflows` 确认"缺的"真缺
   - **三层固化**: 教训写 memory + AGENTS.md/CLAUDE.md (协议层) + hook (harness 层)

## 10. Round Workflow Playbook (ADR-0148, M4 时代)

每轮 (Round X) 工程是 **commit → ADR → 测 → closeout 的闭环**。

```
Round X 的 7 步:
0. baseline: make m4-health
1. single-worktree: bash bin/gac/gac-worktree.sh claim round-{X}
2. deliver: 实施 N 个 deliverable (每 PR 1 deliverable)
3. tests: 加 T-X 系列测试, 跑 regression
4. self-reflex: bin/mof/mof-bootstrap.py all (5-check strict)
5. ADR: 写新 ADR
6. health-check: make m4-health-compare (delta ≥ 0)
7. close: 写 docs/M4-DECISIONS-INDEX.md, 准备 PR
```

### 10.1 Round 类型参考

| Round | 触发 | 输出 |
|-------|------|------|
| **R-patch** | 修缺陷 / 守门 | 1-2 ADR + 测试, Health 持平或↑ |
| **R-feature** | 新增能力 | 3+ ADR + 工具, Health ↑ |
| **R-meta** | 治本 | 4-5 ADR + 元模型扩展, Health ↑ |
| **R-archive** | 决策回顾 | 0 实改, 1-2 ADR 治理声明 |

### 10.2 P72 / P52 / P74 守门

每 Round 必须显式回答 3 个门槛: **P72** 路径不过载 · **P52** 不动元模型/引擎 · **P74** governance 自闭环。

### 10.3 历史 milestone

R0 (5 ADR): 主决策 + L0↔M2 桥接 · R2 (3 ADR): 派生落点 + MetaElement 提升 · R3 (2 ADR): Health Score 量化 · R4 (4 ADR): 速查 + 45 m2 datetime · R5 (3 ADR): 8 阶段稳定性。每 Round 都新增 ADR + 测试 + history 沉淀。

## 架构标准 (Agent 必读)

> 最后更新: 2026-08-31
> 本节引用 `.omo/standards/` 下的架构标准，Agent 在创建/修改架构相关文件时必须遵守。

### 场景卡生命周期 (5 级)

标准: `.omo/standards/scene-card-lifecycle.yaml`

```
draft → shadow → assisted → supervised → routine
```

约束:
- 升级必须按顺序，不可跳级
- 升级到 assisted/supervised/routine 必须有 `promotion_evidence`
- shadow 需要 3-sample useful 才能升级
- assisted 需要 30-sample + calibration >= 0.6

### 业务域分类 (5 域)

标准: `.omo/standards/business-domains.yaml`

每个场景卡必须有 `domain` 字段:
- `work`: 公文、文档、会议、项目
- `health`: 个人与家庭健康
- `research`: 调研与学术
- `knowledge`: 知识沉淀与学习
- `governance`: 系统治理与合规

### 维度系统 (12 维度)

标准: `.omo/standards/dimension-system.yaml`

架构变更需评估对所有维度的影响:
- 治理维 (4): X1审计 / X2保鲜 / X3价值 / X4一致性
- 业务维 (7): 场景 / 功能 / 旅程 / 体验 / 愿景 / 运营 / 运维
- 新增维 (2): 防腐 / 约束 / 进化 / 信任

### 价值循环 (5 阶段)

标准: `.omo/standards/value-loop-standard.yaml`

新增能力必须接入价值循环:
信号感知 → 信号分类 → 旅程执行 → 价值记录 → 进化反馈

### SSOT 收敛

标准: `.omo/standards/architecture-ssot-index.yaml`

核心文档:
- `ARCHITECTURE.md`: 稳定架构契约 (层/路由/边界)
- `docs/PANORAMA.md`: 全景导航 (5+4+1-1 总图)
- `.omo/state/system.yaml`: 运行时状态

### 架构校验命令

```bash
# 全量架构检查
make architecture-check

# 场景卡生命周期检查
python3 bin/ssot/scene-card-lifecycle.py --validate --all

# 维度健康度报告
python3 bin/gac/dimension-health.py --report

# 架构漂移检测
python3 bin/gac/architecture-drift.py
```

### 架构变更流程

1. 评估变更对所有 12 维度的影响
2. 运行 `make architecture-check` 确保合规
3. 更新相关 SSOT 文档
4. 提交 PR，CI 自动检查架构合规

<!-- GaC-RULES-START -->
<!-- AUTO-GENERATED by bin/gac/gac-export-agents.py — do not edit manually -->

### GaC Rules Pointer

> SSOT: `.omo/_truth/registry/governance-checks.yaml::gac.rules`
> Full generated digest: `docs/generated/agent-gac-rules.md`
> Validate: `python3 bin/gac/gac-validate.py --gate` | Drift: `python3 bin/gac/gac-drift.py`
> Regenerate: `python3 bin/gac/gac-export-agents.py`

Do not paste the full rule inventory into `AGENTS.md`; keep this file as an operational pointer.

<!-- GaC-RULES-END -->

## Harness 集成 (Phase 8)

> SSOT: `.omo/_truth/registry/harness-policy.yaml`
> Skill: `.agents/skills/harness-compliance/SKILL.md`

### 核心入口

- **Cockpit CLI**: `cockpit harness <command>` (12 子命令)
- **MCP Tool**: `harness_compliance_check`, `harness_run`, `harness_verify`, `harness_probe`
- **BOS URI**: `bos://harness/*` (9 个服务)
- **直接调用**: `bin/harness run/verify/probe/audit/closeout`

### 8 阶段 DAG

```
admission → spec → grill → dispatch → execute → verify → audit → accept
```

### 强制约束

- Hook 层: 6 个 exit 1 拦截点 (pre-commit)
- GaC 规则: 32 个强制/高优先级规则
- Harness 策略: 19 个强制约束 (blocking/halt/deny/require)
- Agent 约束: 16 个 enforcement 点

### 检查命令

```bash
# 全量合规检查
python3 bin/gac/harness-compliance-check.py --report

# MOF 约束联动
python3 bin/gac/harness-mof-bridge.py

# OMO 状态同步
python3 bin/gac/harness-omo-bridge.py

# 统一约束驱动 (CI 模式)
python3 bin/gac/harness-constraint-enforcer.py --ci

# Cockpit 入口
cockpit harness compliance|mof|omo|enforce|full|status
```

## 归档/收敛项目说明 (project-registry-ssot 契约)

- agora-dashboard 独立入口已收敛 (历史快照, 能力并入 cockpit/agora)
- (归档) hermes-console 与 dashboard_server 作为子应用挂载 (历史, L3 入口能力收敛到 cockpit/agora)
