# AGENTS.md — Workspace Development Guide

> 最后更新: 2026-08-22
> Root operating guide for AI coding agents and developers. Keep this file operational. Put runtime facts in SSOT files, not here.

## 1. Read This First

Before editing:

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check the current working tree with `git status --short`.
4. **需求迭代强制 Workflow（ADR-0203）** — see §1.1. Run `bootstrap` → `status` → `start` → `claim` **before** any requirement delivery edit. Prompt-only execution is non-compliant.
5. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
6. For multi-file or high-risk changes, explain the edit surface before applying patches.
7. **B.D.S.K. Virtual Board & Compute** — For high-risk architectural changes, trade-offs, or local LLM/edge compute integration, refer to [`.agents/skills/bdsk-virtual-board/SKILL.md`](.agents/skills/bdsk-virtual-board/SKILL.md) for the 4-Corner (`@Builder`/`@Devil`/`@Sage`/`@Keeper`) consensus engine. All local/edge LLM inference MUST route through **AetherForge + omlxc v3.4.0 (`bos://compute/aetherforge/infer`)** with 0ms TTFT system prefix caching, dynamic VRAM budgeting, thermal guard penalty, and FastMCP fabric tools (`make fabric-inspect`, `make fabric-warm`, `make fabric-vram`, `make fabric-bench`).
8. **Multi-Agent Observability** — `make omo-status` (<0.2s Rich Panel: Agent heartbeats, locks, submodules, BETs) and `make omo-top` (real-time Textual 1.x control plane).

### Governance Capabilities (ADR-0190..0199)

| ADR | Purpose | Entry / CLI |
|-----|---------|-------------|
| ADR-0190 MOF Dynamic Constraint | Real-time action governance (<0.2ms), self-healing | `ecos-constraint explain/audit/eval/drift`, FastMCP `runtime_governance_*` |
| ADR-0191 Dual-Plane (Workspace × Documents) | Documents = truth/SOPs/facts (no scripts/caches); Workspace = code/CLIs/daemons | `ecos-constraint documents audit/guardrail/sync-clients` |
| ADR-0192 Domain Truth & Hygiene Patrol | `_entities/facts/*.yaml` (14-day freshness), fabric warm, 6-pillar patrol | `make hygiene-patrol` / `ecos-constraint patrol` |
| ADR-0193 Domain Policy-as-Code | `E-POL-WJ-001/002`, `E-POL-TF-001/002` regulatory red-lines | `ecos-constraint policy audit/explain/list` |
| ADR-0194 Truth Canvas, Chaos Drills, Pitfalls | Interactive observability, mutation testing, anti-pattern scan | `make canvas-serve`, `make chaos-drill`, `ecos-constraint pitfall scan` |
| ADR-0195 Intent-to-Spec Compiler | NL prompt → structured execution DAG | `ecos-constraint intent compile`, FastMCP `runtime_intent_compile` |
| ADR-0196 Shadow Challenger Loop | Multi-perspective adversarial red-team + auto-patch | `ecos-constraint challenge [--auto-patch]`, FastMCP `runtime_shadow_challenge` |
| ADR-0197 Sovereign Compute & KV Snapshots | Local speculative execution (8B/14B Q4_K_M), 0ms TTFT KV pre-warming | `omlxc fabric snapshot` / `fabric speculative-eval` |
| ADR-0198 Domain Cartridge Factory | Vertical governance package manager (health / tech transfer) | `ecos-constraint cartridge list/export/validate` |
| ADR-0199 Unified BOS URI, Cockpit & Cognitive Workflow | Full-lifecycle integration across Human Terminal → BOS → Agent Workflow | `cockpit intent/challenge/cartridge/fabric`, `bos://governance/*`, `bos://fabric/*` |

Project-specific instructions override this guide only within that project and only when they do not violate workspace governance.

## 1.1 RED LINE — Requirement iterations MUST use Agent Workflow (ADR-0203)

> **适用全部 agent 运行时**（Claude Code / Cursor / OMC / 自建 / 脚本化 agent）。
> SSOT: `.omo/_truth/registry/agent-workflows/::requirement_iteration_policy`
> 契约: `.omo/standards/agent-workflow-contract.md` §3.1
> ADR: `.omo/_knowledge/decisions/0203-requirement-iteration-workflow-mandatory.md`

| 必须 | 禁止 |
|------|------|
| 任何功能/缺陷/运维落地、治理/SSOT/ADR、交付 closeout | 无 `start` 的 run-id 就改需求相关文件并宣称完成 |
| `bootstrap → start --profile → claim → verify → closeout` | 「先改完再补 workflow」 |
| 用 `list` 选对 workflow（勿默认错位 `project-code-change`） | 把 `observer-audit` / 只读探索当成可写豁免 |

**窄豁免**：纯只读问答；`observer-audit`；用户书面明确 waiver（模板 [`docs/operations/workflow-waiver-template.md`](docs/operations/workflow-waiver-template.md)）。

愿景→落地→复盘硬门（BET-Y1Q1-T6-02/T6-03/T6-04）：`start --bet` 把 `bet_id` 写入 run，`closeout`/`complete` 缺北极星/绑定/retro 会 halt。执行器 [`bin/plan/chain-bind-check.py`](bin/plan/chain-bind-check.py)，红线 `redlines.yaml::vision-to-retro-chain`（详见 [`docs/generated/agent-redlines.md`](docs/generated/agent-redlines.md)），对照 [`docs/architecture/wave-gate-bet-map.md`](docs/architecture/wave-gate-bet-map.md)。

**可执行闸门（ADR-0204）**：`compliance` / `status` 对 **已 stage** 的需求面路径检查是否存在 active run；无 run → **halt**（exit 1）。仅 unstaged dirty → warn。旁路：`AGCP_REQUIREMENT_ITERATION_GATE=0`（须用户授权并写入 waiver 证据）。

```bash
make agent-workflow-bootstrap
make agent-workflow-status
uv run --with "pyyaml" python "bin/agent-workflow.py" suggest --from-diff --profile <agent-profile>
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> \
  --profile <agent-profile> --bet <BET-ID> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>
# ADR 占号 / worktree 清理 / ACL ops / 钩子重装：
python3 bin/adr/next-adr-id.py --session <session> --claim
bash bin/gac/gac-worktree-prune.sh          # dry-run
bash bin/gac/omo-acl-ops-window.sh          # dry-run (ADR-0206)
make install-hooks
```

参考：Worktree 卫生 [`docs/operations/worktree-hygiene.md`](docs/operations/worktree-hygiene.md) · ACL ops [`docs/operations/omo-path-acl-runbook.md`](docs/operations/omo-path-acl-runbook.md) · Codebase 结构图 [`docs/operations/codebase-memory.md`](docs/operations/codebase-memory.md)（skill `codebase-memory`）。

## 1.2 P74 Solidification Quick Reference (ADR-0130)

常态化 agent-workflow silence 检测。详见 [ADR-0130](.omo/_knowledge/decisions/0130-p74-workflow-solidification.md)、[pattern](.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md)、[contract](.omo/standards/p74-solidification-contract.md)。

**SSOT**：`agent-workflows/::silent_workflow_policy`（A1/A2 + per-workflow `run_frequency`，`excluded_workflows` 已移除 per ADR-0211 §D1）；`governance-checks.yaml`（4 CR-P74-* rules）。

**Tools**：`omo lint projection-guard` · `omo lint stamp-policy` · `agent-workflow.py suggest --from-diff --profile <agent>` · `agent-workflow.py compliance --json` → `.p74_solidification`。

**Skill**：[`.agents/skills/workflow-silence-detection/SKILL.md`](.agents/skills/workflow-silence-detection/SKILL.md)。

若 `p74_solidification.warn_count > 0`，禁止投机启动 workflow。读 contract §3 决策树并 **添加 `diff_checks` 规则**覆盖该 workflow 的 surfaces（治本 per ADR-0214 §D1）。

## 1.3 Swarm coordination (G-CONV.7 / ADR-0220)

M1 hard pre-gate（并发 main conflict = 0）：

| Gate | Command | 状态 |
|------|---------|------|
| D1 ADR claim | `python3 bin/adr/next-adr-id.py --session <s> --claim` | ✅ 活跃 |
| D2 branch lock | ~~`gac-worktree.sh claim`~~ | 🏁 退役 (独立 clone) |
| D3 shared claim | ~~pre-commit `claim-check`~~ | 🏁 退役 → 跨仓审计 |
| D4 escape | `SWARM_ESCAPE_ID=...` · `bin/gac/swarm-git` for `--no-verify` | ✅ 活跃 |
| D5 submodule | pre-commit `submodule-guard` (fast-forward) | ⚠️ 部分退役 |

72h window: `python3 bin/gac/swarm-discipline-cli.py window-status` · M1 rejudge: `python3 bin/gac/m1-closeout-report.py --ssot-root <live-workspace>`（`m1_verdict=window_open` while elapsed<72h；`phase2_recommend` 仅当 elapsed≥72h AND conflict=0 AND all hard green）。Registry: `.omo/_truth/registry/swarm-coordination.yaml`。

**D0 铁律**：交付物必须 `git add` → `commit` → **`tag`**（或推独立远端分支）。仅 commit 不算持久化。

**逃生口唯一入口**：`SWARM_ESCAPE_ID=<id> bin/gac/swarm-git ...`。人类急救发卡：`python3 bin/gac/swarm-discipline-cli.py escape-token-issue`。T1-07 PATH shim（`bin/gac/git-shim` + `AGENT_ID`）强制 agent `git` → `swarm-git`，拦 `--no-verify` + 高危操作；人类终端（`AGENT_ID` 空）透传不受影响。

**独立 clone 拓扑（T1-05，2026-08-19 完成）**：每个 delivery attempt 使用独立 clone，主仓降级为集成点。稳定身份为 `actor_id`，一次性交付身份为 `delivery_attempt_id`；新 writer 使用 `~/agents/<actor>/attempts/<attempt>/ws` 与 `agent/<actor>--<attempt>`。写入型 agent 必须设 `AGENT_ID` 并使用独立 clone；v1 clone 只保留读取、验证和退役兼容。
```bash
python3 bin/gac/agent-clone-onboard.py            # dry-run 检测+创建缺失 clone
python3 bin/gac/agent-clone-onboard.py --apply
python3 bin/gac/clone-lifecycle.py onboard/snapshot/changeset/integrate/retire  # 全生命周期
```
详见 [`docs/reports/2026-08-06-multi-agent-git-topology.md`](docs/reports/2026-08-06-multi-agent-git-topology.md) · `BET-Y1Q1-T1-05`。

**蜂群感知**：软/动/硬三层 — 在线节点大盘 · 总线广播 `broadcast-bus.jsonl` + `SWARM_COLLISION_ALERT` · PASW 物理锁 + 门禁 Exit 1 阻断。

> **共享 checkout 并发吸收 (2026-08-16)**：并发 agent 会把共享树上 staged 改动直接 `add -A && commit` 成混合 commit。处理：① 不贸然 reset — 先 `git reflog -8` + `git show <sha> --stat`；② 验证是否已合入 main；③ 已合入则 `agent-workflow close --status blocked` 记录；④ 本地 main 分叉时 **勿 reset --hard**。详见 memory `feedback_shared_checkout_concurrent_absorb_20260816.md`。

## 1.4 我该做什么 — 三年规划执行台账

不要自行拟定任务。读台账：
```bash
uv run --with pyyaml python bin/plan/bet-ledger.py status
uv run --with pyyaml python bin/plan/bet-ledger.py claim-check <BET-ID>
```
SSOT [`docs/plans/3y-bet-ledger.yaml`](docs/plans/3y-bet-ledger.yaml) · 视图 [`docs/plans/3Y-BET-LEDGER.md`](docs/plans/3Y-BET-LEDGER.md) · 指令 [`docs/plans/AGENT-BRIEF.md`](docs/plans/AGENT-BRIEF.md) · skill `bet-execution`。

## 1.5 8D 全景元架构与全仓四大入口契约

系统由 **LifeOS 意图 ➔ C2G 策略 ➔ Goals 目标 ➔ Agora 蜂群 ➔ AetherForge 算力 ➔ AGE-v2 落地 ➔ MOS/KOS 记忆 ➔ X-Plane 熵减** 8 维空间组成。

1. **7D 终极可观测**：`cockpit panorama` / `make panorama`
2. **8D 全景追溯**：`cockpit compass trace <GOAL-ID>` / `make compass-trace` / `bos://governance/omo/compass-trace`
3. **17 项目 4D 体检**：`cockpit project inspect <PROJ>` / `make project-inspect`
4. **场景卡与 Journey 校验**：`cockpit journey` / `make journey-validate` / `make scene-card-check`
5. **常态化守护**：必须维持 `make gac-local-gate` ALL GREEN PASS 绿线（check 数以 `bin/gac/gac-local-gate.py` 为准）

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
| [`.omo/_truth/registry/ci-surfaces.yaml`](.omo/_truth/registry/ci-surfaces.yaml) | CI 平面检查接线登记 (ADR-0379) | `check-ci-surfaces.py` (CR-CI-SURFACE-SSOT) |
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

For `.omo` or `spaces` mutations, use the registered broker/CLI path. If a task truly needs direct manual edits, call that out and keep the patch minimal.

## 5. Essential Commands

按场景分类，快速找到需要的命令：

### 治理门禁 (Gate & lint)

```bash
make gac-local-gate                          # 全量治理-as-Code 门禁
make ci-local                                # 本地一键全部门
make check-layers                            # 分层依赖检查 (docs/layer-contract.yaml)
make gac-local-gate --scope files --file <path> --json
make doc-ssot-lint
make ssot-guardian
make gac-validate
make gac-drift
```

### 能力防腐 & 投影强制 (差距治理 S1, 2026-08-24)

```bash
python3 bin/gac/check-capability-ownership.py          # CAP-OWN: 能力所有权 + 删除防腐
python3 bin/gac/check-capability-ownership.py --json   # JSON 输出
```

- **CAP-OWN**: 注册能力实现缺失 (IMPL-EXISTS) → gate 阻断; owner 缺失 / 孤儿能力 → info。
  删除能力前必须同步注册表 + 证明消费引用归零 (类比 submodule-guard 保护 gitlink)。
- **PROJ-FORCE**: post-commit 检测 SSOT 源变更 (agent-workflows/profiles, mof-capabilities)
  → 自动投影生成。改 SSOT 后派生文档随 commit 同步, 残缺生成物自动 revert。
- **GEN-FORCE**: `docs/generated/` 5 个已跟踪生成物不再被 gitignore (契约保护), git add 直接可见。
- 工程铁律 (TP-RELATIVE 时序相对断言 / PATH-ANCHOR 路径代码锚定): [`docs/operations/engineering-golden-rules.md`](docs/operations/engineering-golden-rules.md)

`make gac-local-gate` runs the default (non-strict) GaC gate — GaC validate/drift, agent-workflow lint/integrations/adapters/bootstrap/observe, MOF schema/state-bridge/drift, documentation SSOT, doc link/snapshot, and staged change-lane checks. Two skip rules apply in default mode, both isolating concurrent-agent dirty in a shared worktree: `verify-plan`/`compliance`/`doctor` run only when staged touches agent-workflow (`896e60ba`); `project-layer-index` (generated layer digest) is CI-only — pre-commit/`make` skip it, `--strict`/CI runs it (`d33af25c`). For run/file-scoped AGCP verification use `bin/gac/gac-local-gate.py --scope ...`. Authoritative check list + skip rules live in `bin/gac/gac-local-gate.py` (`CHECKS`, `AGENT_WORKFLOW_GATE_CHECKS`, `CI_ONLY_CHECKS`) — do not duplicate here.

### SSOT 变更追踪

```bash
make ssot-status                             # SSOT 变更状态检查
make ssot-log                                # SSOT 审计日志查看
make ssot-sync                               # SSOT 变更记录到审计日志
make sync-submodules                         # 推送子模块未推送的 commit 到远程
```

### Agent 工作流生命周期

```bash
make agent-workflow-bootstrap
make agent-workflow-status
make agent-workflows
make agent-workflow-agents
make agent-workflow-lint
make agent-workflow-integrations
make agent-workflow-adapters
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> --profile <agent-profile> --bet <BET-ID> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" verify <run-id> --from-diff --execute
make agent-workflow-closeout RUN_ID=<run-id>
make agent-workflow-compliance  # optional: RUN_ID for specific run
make agent-workflow-doctor
```

<!-- doc-ssot-lint: raw form "bin/agent-workflow.py" bootstrap, "bin/agent-workflow.py" closeout, "bin/agent-workflow.py" compliance -->

### 运行态与治理状态

```bash
make state-sync-dry
make state-sync
uv run --with "pyyaml" python "bin/gac/governance-evolution.py" status --json
uv run --with "pyyaml" python "bin/gac/governance-evolution.py" validate --json
```

### 项目测试

```bash
bash "tests/integration/run-all.sh"          # root integration suite
cd "projects/knowledge/kairon" && make test-diff       # kairon (Python)
cd "projects/knowledge/gbrain" && bun test             # gbrain (TypeScript)
```

### 附加诊断工具

```bash
make gac-healthcheck
make evidence-smoke  # BOS declaration vs execution gap audit
uv run --with "pyyaml" python "bin/mof/gen-project-registry.py"  # Registry drift detection (code→registry)
make swarm-activity              # 多 agent 实时活动面板
python3 bin/gac/swarm-activity-dashboard.py --watch 10
python3 bin/gac/check-ci-surfaces.py                    # CI 平面可观测性 (ADR-0379)
python3 bin/gac/ci-check-runner.py --workflow governance-check.yml
```

### 模型驱动治理闭环 (L0↔MOF)

治理闭环工具链（工具目录: [`bin/README.md`](bin/README.md) §5b, 模型: MOF m0-m3 + L0 约束 + ontology）：

```bash
python3 bin/ssot/consumer_index.py           # L0 约束 → 16 抽象族/规则反向索引
python3 bin/ssot/m0_feedback.py              # M0 运行时快照 → 派生面漂移检测
python3 bin/ssot/semantic_diff.py <old> <new> # 约束变更语义 diff
python3 bin/ssot/model_graph_query.py --constraint X1-C04  # 模型图查询 (GraphRAG)
python3 bin/ssot/corrosion_learner.py --drifts <d.json>    # 漂移 → 修正建议
python3 bin/ssot/onto_ekg_bootstrap.py --emit # OntoEKG 自举 (文档→候选概念)
python3 bin/ssot/onto_reconcile.py           # 候选概念 vs ontology 缺口对比
python3 bin/ssot/governance_closed_loop.py   # 闭环端到端验证 (真实数据)
cd projects/ecos && uv run python3 bin/inference_engine.py  # DR-01~08 推理
cd projects/ecos && uv run python3 bin/gen-l0-constraints.py # L0 派生面生成
```

See [`bin/README.md`](bin/README.md) for the full tool catalog.

Prefer targeted checks for narrow edits. Broaden verification when the change touches shared contracts, generated registries, public entry points, or cross-project behavior.

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, destructive checkout, or branch switching unless the user explicitly asked or confirmed.
- Root repository tracks submodule pointers and workspace metadata.
- Most `projects/*` directories are independent repositories. Commit inside the submodule first only when the user requested commits, then update the root pointer.
- **Submodule pointer update**: prefer `bash bin/ssot/submodule-pointer-transaction.sh --message "..."` (pushes submodules + verifies reachability + stages). If using `git update-index --cacheinfo` manually, always get the hash from `git -C <submodule> rev-parse HEAD` and verify with `git ls-tree HEAD <submodule>` before committing. Never copy-paste hashes from `git log` output (abbreviated hashes cause silent mismatches).
- Never revert unrelated dirty files. Treat them as user or concurrent-agent work.

#### 高危 git 操作守门（2026-08-23 复盘固化，详见 `2026-08-23-agent-session-deep-retrospective.md`）

- **`reset --hard` 前三确认**：① 当前分支（并行工作区会被并发 agent 随时 `checkout` 切走——曾因未确认把并发 agent 的 main 误回退，靠 reflog 恢复）② reset 目标 = 该分支的 origin 状态 ③ 工作树干净。高危操作优先在独立 clone（T1-05 拓扑）里执行。
- **改"看起来是子项目"的代码前确认仓库边界**：先 `ls -d <path>/.git` + `git -C <path> remote -v`。`git -C` 在无独立仓库的目录会 fallback 到父仓库，造成"我在子项目里"的假象（P73-D1 曾因此把 root 跟踪的 gbrain 残留副本当成 gbrain 仓库改）。
### 治理活性自检 (自进化框架)

```bash
# 治理机制活性巡检 (M1 心跳 + M2 引用活性 + scheduler-drift)
python3 bin/gac/meta-doctor.py --workspace . --json

# 调度编译器: 登记↔安装一致性校验
python3 bin/scheduler-compile.py --check

# 会话交接协议: 产出机器可读 handoff.json
python3 bin/gac/session-handoff.py --session <id> --agent <name> --summary "..."

# cron job 心跳包装器
bash bin/gac/heartbeat-wrapper.sh <job_name> <command...>
```

### Resident Agent 体系 (2026-08-23, WP-A~I / ADR-0396)

事件驱动常驻 agent 运行时（五类角色 + 规则级路由订阅），规格见 [`docs/architecture/resident-agent-system-v1.md`](docs/architecture/resident-agent-system-v1.md)。

```bash
make resident-status       # 运行状态快照 (daemon/events/sediment/alert/ledger)
make resident-roles        # 五类角色配置
make resident-daemon       # 单次 tick 调试
uv run --directory projects/omo python -m omo.cli resident status --json
```

- 路由表 SSOT: `projects/omo/src/omo/resident/resident-routes.yaml`（schema `resident-routes/v1`）
- 角色 SSOT: `projects/omo/src/omo/resident/roles.py`（sediment/decision/execute/monitor/heartbeat）
- 兼容脚本: `bin/ssot/resident-orchestrator-daemon.py`、`decision-agent.py`、`event-ingest-adapter.py`、`personal-signals-adapter.py`、`alert-forwarder.py`、`system-health-check.py`
- cron: `bash bin/ssot/install-resident-cron.sh`（每 2min 五类 daemon --once --role；M3.1 signals；M4.3 角色化）
- agora MCP: `resident_status` / `resident_roles`（`projects/agora/src/agora/server/tools_resident.py`，委派 `omo resident status/roles`）
- BOS: `bos://resident/*`（resident 常驻体系 URI 命名空间）

### BCOS 业务域系统 (2026-08-23, W1~W4)

业务闭环系统（信号路由 → 进化引擎 → 北极星价值度量），规格见 [`docs/architecture/bcos-system-v1.md`](docs/architecture/bcos-system-v1.md)。

```bash
make bcos-evolve       # 进化引擎四阶段 (observe/propose/evaluate/approve, dry-run 默认)
make bcos-signals      # 统一信号路由 (W1-D2)
make bcos-north-star   # 北极星价值度量 v2
python3 bin/bc-os/evolution_engine.py --json     # 四阶段 JSON 输出
python3 bin/bc-os/signal_router.py --inbox <dir> # 扫描路由信号
python3 bin/bc-os/north_star_meter_v2.py --json  # 价值真值快照
```

- 进化引擎: `bin/bc-os/evolution_engine.py`（EvolutionEngine: observe/propose/evaluate/approve/rollback）
- 信号路由: `bin/bc-os/signal_router.py`（W1-D2: doc/meeting/research/code 路由规则）
- 北极星: `bin/bc-os/north_star_meter_v2.py`（排除 self-data, W3 真实价值闭环）
- MOF: `mof/m2/bcos_system.yaml`（BCOSystem extends System）· BOS: `bos://bcos/*`
- 背景: evolution_engine/signal_router 曾被误归档, 依台账 + T6-13 恢复 (PR #2050)



### 6.1 PR 工作流

主仓 main 变更走 **per-session worktree + PR**。工具:`bin/gac/gac-worktree.sh`。

```bash
bash bin/gac/gac-worktree.sh claim <session>   # 起隔离 worktree (work/<session> 分支)
cd ../ws-<session>                          # 改文件 + commit (改子模块先 git submodule update --init)
bash bin/gac/gac-worktree.sh submit <session>   # push 分支 + 开 PR (base main)
bash bin/gac/gac-worktree.sh merge <session>    # squash 合并 PR + release + 删分支
```

- **当前状态**: ✅ **blocking + branch protection 已启用** — `make install-hooks` 装 blocking pre-push + `bash bin/gac/gac-branch-protection.sh` 启用 main 保护。direct push main 被本地 + 平台双重拒绝。所有 main 变更必须走 worktree+PR。
- **子模块**: 已启用分支保护 (禁止 force push / 删除 / 非线性历史, enforce_admins), 但仍允许 direct push。CI `bulk-deletion-guard` 门禁拦截空树提交。详见 [`docs/SUBMODULE-PR-STRATEGY.md`](docs/SUBMODULE-PR-STRATEGY.md)。
- **L0 萃取不破坏**: `post-commit` 是 commit 级触发(worktree 共享 `.git/hooks`),worktree 内 commit 照样萃取,派生文件进 PR。
- **完整计划**: [`docs/AGENT-ISOLATION-ROLLOUT.md`](docs/AGENT-ISOLATION-ROLLOUT.md) §4 Phase 2-3 (已落地)。

Worktree 常见踩坑诊断与 redundant 分支检测见 [`docs/operations/worktree-hygiene.md`](docs/operations/worktree-hygiene.md)。

## 7. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Root governance docs | `make gac-local-gate` plus `make ssot-guardian` |
| Python code (generic) | Targeted `uv run pytest` or project Makefile `test` target. 根仓 `tests/` 用 `uv run --with pyyaml --with pytest python -m pytest` (裸 `uv run pytest` 会命中 pipx pytest, 缺 pyyaml) |
| kairon package | `make test-diff` from `projects/knowledge/kairon` |
| gbrain | `bun test` or targeted Bun test |
| cockpit-ui (TypeScript) | `npm run build` or `bun run build` from `projects/cockpit-ui` |
| observability (Docker) | `docker compose config -q` from `projects/observability` |
| Cross-project contract | Targeted tests on every touched consumer plus relevant integration smoke |
| Code exploration (callers/impact) | Prefer codebase-memory MCP (`list_projects` → `search_graph` / `trace_path`); see [`docs/operations/codebase-memory.md`](docs/operations/codebase-memory.md) |

If a test cannot run, report why and what risk remains.

## 8. Historical Patterns

Historical closeout details are useful evidence. Each pattern links to its full doc — read there, not here:

- [Agent mutation protocol](.omo/standards/agent-mutation-protocol.md) · [OMO governance surfaces](.omo/standards/omo-governance-surfaces.md) · [GaC North Star](.omo/_knowledge/gac/NORTH-STAR.md)
- [P75 convergence round](.omo/_knowledge/patterns/p75-convergence-round-pattern.md) (ADR-0373) · [P91 pyright sweep](.omo/_knowledge/patterns/p91-pyright-sweep-pattern.md) (ADR-0364) · [Delegation infra diagnosis](.omo/_knowledge/patterns/delegation-infra-diagnosis-pattern.md)
- [P43 closed-loop](.omo/_knowledge/patterns/p43-closed-loop-pattern.md) · [P71 baseline recovery](.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md) · [P72 follow-up completion](.omo/_knowledge/patterns/p72-follow-up-completion-pattern.md)
- [L0/SSOT/M0/MOF 对齐审计](.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md) · [Frontmatter yaml 读法 (safe_load_all)](.omo/standards/agent-workflow-contract.md)
- [Executable agent workflows](.omo/standards/agent-workflow-contract.md) · [AGCP status/scoped gate/claim](.omo/standards/agent-workflow-contract.md) · [Governance evolution roadmap](docs/GOVERNANCE-EVOLUTION-ROADMAP.md)
- [State generation convergence](.omo/_knowledge/decisions/0128-state-generation-concurrency.md) · [3 类声明/执行鸿沟 (P71 §1)](.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md)
- [P78 triple-axis diagnostic](.omo/_knowledge/patterns/p78-triple-axis-diagnostic-pattern.md) · [Phase 45 治理可观测性](projects/agora/src/agora/server/tools_health.py)
- **分支等价性判据（2026-08-23 固化）**：判断"分支内容是否已合入 main"只用 **内容 diff**（`git diff origin/main...<branch>`）。git cherry 的 `+` 会因 squash/重构假阳性；subject grep 会因 grep 到分支自身假阳性。曾因误判把 6 个"内容已被 main 吸收"的分支反复归类。
- [agora P1 深化](docs/reports/2026-08-06-agora-p1p2-deepening-retrospective.md) · [agora P2 深化](docs/reports/2026-08-06-agora-p1p2-deepening-retrospective.md)

## 9. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Prefer `make agent-workflow-closeout RUN_ID=<run-id>` for governed runs.
4. Mention files changed and checks run.
5. Mention any checks skipped or blocked.
6. Do not create commits unless explicitly requested and confirmed.
7. **大任务后复盘+固化** (P74 常态化精神 — 不靠自觉靠机制):
   - **复盘触发**: 系统性分析/方案任务 / 多轮返工 / Stop hook 反馈后 / 判断错误发现时
   - **判断错误复盘**: 识别"基于不完整信息下结论 / grep 假阴性 / 重复造轮 / 跳过冷启动"等模式 (实证: memory `verify-claim-three-layers`)
   - **诊断前置 4 问 (P78)**: 报"系统问题/架构缺口"前过 4 问 — ①反证找了吗 ②查运行时实证了吗 ③读相关 ADR 了吗 ④扫了 `bin/ssot` + `.github/workflows` 确认"缺的"真缺. 详见 [P78](.omo/_knowledge/patterns/p78-triple-axis-diagnostic-pattern.md)
   - **三层固化**: 教训写 memory (feedback 类型) + AGENTS.md/CLAUDE.md (协议层) + hook (harness 层)
   - **目标**: "基于直觉→基于实证", "靠自觉→靠机制守门"

## 10. Round Workflow Playbook (ADR-0148, M4 时代)

每轮 (Round X) 工程是 **commit → ADR → 测 → closeout 的闭环**, 沉淀自 R0..R5b (22+ commits, 17 ADRs, M4 Health 99.17→100/100)。

```
Round X 的 7 步:
0. baseline: make m4-health (留当前分数快照)
1. single-worktree: bash bin/gac/gac-worktree.sh claim round-{X}
2. deliver: 实施 N 个 deliverable (每 PR 1 deliverable)
3. tests: 加 T-X 系列测试, 跑 regression (tests/integration/m4_metamodel/run_all.py)
4. self-reflex: bin/mof/mof-bootstrap.py all (5-check strict)
5. ADR: 写新 ADR (.omo/_knowledge/decisions/{NNN}-title.md)
6. health-check: make m4-health-compare (delta ≥ 0)
7. close: 写 docs/M4-DECISIONS-INDEX.md, 准备 PR

end-of-round quality gates (3 个必过):
  G-Tests:   m4_metamodel/run_all.py  N+1/N+1 PASS
  G-Reflex:  mof-bootstrap.py all  5-check strict 0 err
  G-Health:  m4-health-score.py --compare  delta ≥ 0
```

### 10.1 Round 类型参考

| Round | 触发 | 输出 |
|-------|------|------|
| **R-patch** | 修缺陷 / 守门 | 1-2 ADR + 测试, Health 持平或↑ |
| **R-feature** | 新增能力 | 3+ ADR + 工具, Health ↑ |
| **R-meta** | 治本 (如 ADR-0136) | 4-5 ADR + 元模型扩展, Health ↑ |
| **R-archive** | 决策回顾 (如 ADR-0146) | 0 实改, 1-2 ADR 治理声明 |

### 10.2 P72 / P52 / P74 守门

每 Round 必须显式回答 3 个门槛: **P72** 路径不过载 (不重做历史踩坑路径) · **P52** 不动元模型/引擎 (不直接改 m3.yaml / model-driven 引擎) · **P74** governance 自闭环 (每 ADR 走 governance-agent profile, 留 evidence)。

### 10.3 历史 milestone

R0 (5 ADR): 主决策 + L0↔M2 桥接 + meta_model↔m3 桥接 + 派生面 + 5 改动 · R2 (3 ADR): 派生落点 + MetaElement 提升 + 8 阶段拒回 · R3 (2 ADR): Health Score 量化 + M2BaseSchema + check_5 · R4 (4 ADR): 速查 + 45 m2 datetime + OMO cron hook + MCPTOOL 集合治本 · R5 (3 ADR): 8 阶段稳定性 + MCPTOOL adder guide + Round playbook。每 Round 都新增 ADR + 测试 + history 沉淀。Health Score 必须不回退。

<!-- GaC-RULES-START -->
<!-- AUTO-GENERATED by bin/gac/gac-export-agents.py — do not edit manually -->

### GaC Rules Pointer

> SSOT: `.omo/_truth/registry/governance-checks.yaml::gac.rules`
> Full generated digest: `docs/generated/agent-gac-rules.md`
> Validate: `python3 bin/gac/gac-validate.py --gate` | Drift: `python3 bin/gac/gac-drift.py`
> Regenerate: `python3 bin/gac/gac-export-agents.py`

Do not paste the full rule inventory into `AGENTS.md`; keep this file as an operational pointer.

<!-- GaC-RULES-END -->

## 归档/收敛项目说明 (project-registry-ssot 契约)

- agora-dashboard 独立入口已收敛 (历史快照, 能力并入 cockpit/agora)
- (归档) hermes-console 与 dashboard_server 作为子应用挂载 (历史, L3 入口能力收敛到 cockpit/agora)
