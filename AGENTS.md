# AGENTS.md — Workspace Development Guide

> 最后更新: 2026-07-15
> Root operating guide for AI coding agents and developers working in this workspace.
> Keep this file operational. Put runtime facts in SSOT files, not here.

## 1. Read This First

Before editing:

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check the current working tree with `git status --short`.
4. **需求迭代强制 Workflow（ADR-0203）** — see §1.6. Run `bootstrap` → `status` → `start` → `claim` **before** any requirement delivery edit. Prompt-only execution is non-compliant.
5. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
6. For multi-file or high-risk changes, explain the edit surface before applying patches.

Project-specific instructions override this guide only within that project and only when they do not violate workspace governance.

## 1.6 RED LINE — Requirement iterations MUST use Agent Workflow (ADR-0203)

> **适用全部 agent 运行时**（Claude Code / Cursor / OMC / 自建 / 脚本化 agent）。  
> SSOT: `.omo/_truth/registry/agent-workflows.yaml::requirement_iteration_policy`  
> 契约: `.omo/standards/agent-workflow-contract.md` §3.1  
> ADR: `.omo/_knowledge/decisions/0203-requirement-iteration-workflow-mandatory.md`

| 必须 | 禁止 |
|------|------|
| 任何功能/缺陷/运维落地、治理/SSOT/ADR、交付 closeout | 无 `start` 的 run-id 就改需求相关文件并宣称完成 |
| `bootstrap → start --profile → claim → verify → closeout` | 「先改完再补 workflow」 |
| 用 `list` 选对 workflow（勿默认错位 `project-code-change`） | 把 `observer-audit` / 只读探索当成可写豁免 |

**窄豁免**：纯只读问答；`observer-audit`；用户书面明确 waiver（须写入 closeout 证据，模板见 [`docs/operations/workflow-waiver-template.md`](docs/operations/workflow-waiver-template.md)）。

**可执行闸门（ADR-0204）**：`compliance` / `status` 对 **已 stage** 的需求面路径检查是否存在 active run；无 run → **halt**（exit 1）。仅 unstaged dirty → warn。旁路：`AGCP_REQUIREMENT_ITERATION_GATE=0`（须用户授权并写入 waiver 证据）。

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
# 有 diff 时先 suggest，避免错位 workflow（P74）
uv run --with "pyyaml" python "bin/agent-workflow.py" suggest --from-diff --profile <agent-profile>
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> \
  --profile <agent-profile> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
# ... edit / test ...
uv run --with "pyyaml" python "bin/agent-workflow.py" verify <run-id> --from-diff --execute
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
# ADR 占号（防撞车）:
python3 bin/adr/next-adr-id.py --session <session> --claim
# 栈落地后清 worktree:
bash bin/gac/gac-worktree-prune.sh          # dry-run
# bash bin/gac/gac-worktree-prune.sh --apply
# ACL ops 窗口（默认 dry-run，ADR-0206）:
bash bin/gac/omo-acl-ops-window.sh
# 钩子重装（.githooks 变更后）:
# make install-hooks && grep bin/ssot/sync-submodules-push .git/hooks/pre-push
```

Worktree 卫生说明：[`docs/operations/worktree-hygiene.md`](docs/operations/worktree-hygiene.md)。  
ACL ops 窗口：[`docs/operations/omo-path-acl-runbook.md`](docs/operations/omo-path-acl-runbook.md) §2 / ADR-0206。

## 1.5 P74 Solidification Quick Reference (ADR-0130)

P74 is the常态化 mechanism (常态化机制) for detecting and preventing agent-workflow
silence. See `.omo/_knowledge/decisions/0130-p74-workflow-solidification.md` for the
architecture decision, `.omo/_knowledge/patterns/p74-workflow-solidification-pattern.md`
for the pattern, and `.omo/standards/p74-solidification-contract.md` for the
operator-facing decision tree.

SSOT:

- `agent-workflows.yaml::silent_workflow_policy` (A1/A2 classification + per-workflow `run_frequency` per ADR-0211; `excluded_workflows` field removed in ADR-0211 §D1)
- `governance-checks.yaml` (4 CR-P74-* rules: STATE-PROJECTION-GUARD, RUNTIME-STAMP-POLICY, WORKFLOW-SILENCE, WORKFLOW-SUGGEST)

Tools (`bin/` + `projects/omo`):

- `omo lint projection-guard` — CR-P74-STATE-PROJECTION-GUARD (from `bin/gac/omo-state-projection-guard.py`)
- `omo lint stamp-policy` — CR-P74-RUNTIME-STAMP-POLICY (from `bin/gac/omo-runtime-stamp-policy.py`)
- `agent-workflow.py suggest --from-diff --profile <agent>` — CR-P74-WORKFLOW-SUGGEST
- `agent-workflow.py compliance --json` → `.p74_solidification` — CR-P74-WORKFLOW-SILENCE

Skill: `.agents/skills/workflow-silence-detection/SKILL.md` (triggers on P74, silent workflow, compliance warn).

If `p74_solidification.warn_count > 0` (any silent workflow counts; `handoff-resume` and
`observer-audit` no longer excluded per ADR-0211 §D1), do NOT start the workflow
speculatively. Read the contract standard §3 decision tree and **add a `diff_checks`
rule covering the workflow's surfaces** (治本 per ADR-0214 §D1). Extending
`silent_workflow_policy.excluded_workflows` is no longer supported (field removed in
ADR-0211 §D1).

## 2. Documentation SSOT Contract

| Document | Owns | Must Reference |
|----------|------|----------------|
| [`README.md`](README.md) | Front door and quick orientation | Architecture, registry, governance docs |
| [`CLAUDE.md`](CLAUDE.md) | AI session startup protocol | This file and target project docs |
| [`AGENTS.md`](AGENTS.md) | Workspace operating rules | SSOT registries for facts |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Stable architecture contracts | Registry files for counts and runtime values |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | Human-readable layer placement | `docs/project-registry.yaml` |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | Project metadata facts | Actual project metadata |
| [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) | Agent workflow facts | Executable workflow runner |
| [`.omo/_truth/registry/omo-governance-surfaces.yaml`](.omo/_truth/registry/omo-governance-surfaces.yaml) | OMO governance surfaces | Governance surface registry SSOT |
| [`.omo/_truth/registry/runtime-projections.yaml`](.omo/_truth/registry/runtime-projections.yaml) | Runtime projection registry | `omo-state-projection-guard.py` (P74) |
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
| `scripts/` | Ops scripts (independent submodule). See [`scripts/AGENTS.md`](scripts/AGENTS.md). |
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
make ci-local                                # 本地一键全部门 (Makefile:105)
make check-layers                            # 分层依赖检查 (docs/layer-contract.yaml)
uv run --with "pyyaml" python "bin/gac/gac-local-gate.py" --scope files --file <path> --json
uv run --with "pyyaml" python "bin/ssot/doc-ssot-lint.py" --json
uv run --with "pyyaml" python "bin/ssot/ssot-guardian.py"
uv run --with "pyyaml" python "bin/gac/gac-validate.py" --gate
uv run --with "pyyaml" python "bin/gac/gac-drift.py"
```

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
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
uv run --with "pyyaml" python "bin/agent-workflow.py" list
uv run --with "pyyaml" python "bin/agent-workflow.py" agents
uv run --with "pyyaml" python "bin/agent-workflow.py" lint
uv run --with "pyyaml" python "bin/agent-workflow.py" integrations
uv run --with "pyyaml" python "bin/agent-workflow.py" adapters
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> --profile <agent-profile> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" verify <run-id> --from-diff --execute
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" doctor
```

### 运行态与治理状态

```bash
uv run --project "projects/omo" omo state sync --dry-run --json
uv run --project "projects/omo" omo state sync --json
uv run --with "pyyaml" python "bin/gac/governance-evolution.py" status --json
uv run --with "pyyaml" python "bin/gac/governance-evolution.py" validate --json
```

### 项目测试

```bash
bash "tests/integration/run-all.sh"          # root integration suite
cd "projects/kairon" && make test-diff       # kairon (Python)
cd "projects/gbrain" && bun test             # gbrain (TypeScript)
```

### 附加诊断工具

```bash
uv run --with "pyyaml" python "bin/gac/gac-healthcheck.py"   # GaC 13-point health check
uv run --with "pyyaml" python "bin/gac/evidence-smoke.py"     # BOS declaration vs execution gap audit
uv run --with "pyyaml" python "bin/mof/gen-project-registry.py"  # Registry drift detection (code→registry)
```

See [`bin/README.md`](bin/README.md) for the full tool catalog.

Prefer targeted checks for narrow edits. Broaden verification when the change touches shared contracts, generated registries, public entry points, or cross-project behavior.

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, destructive checkout, or branch switching unless the user explicitly asked or confirmed.
- Root repository tracks submodule pointers and workspace metadata.
- Most `projects/*` directories are independent repositories. Commit inside the submodule first only when the user requested commits, then update the root pointer.
- Never revert unrelated dirty files. Treat them as user or concurrent-agent work.

### 6.1 PR 工作流(Phase 2,渐进推进)

主仓 main 变更走 **per-session worktree + PR**,消灭 direct push to main(多 agent 撞车根因)。工具:`bin/gac/gac-worktree.sh`。

```bash
bash bin/gac/gac-worktree.sh claim <session>   # 起隔离 worktree (work/<session> 分支)
cd ../ws-<session>                          # 改文件 + commit (改子模块先 git submodule update --init)
bash bin/gac/gac-worktree.sh submit <session>   # push 分支 + 开 PR (base main)
bash bin/gac/gac-worktree.sh merge <session>    # squash 合并 PR + release + 删分支
```

- **当前状态(2026-07-05)**: ✅ **blocking + branch protection 已启用** — `make install-hooks` 装 blocking pre-push + `bash bin/gac/gac-branch-protection.sh` 启用 main 保护。direct push main 被本地 + 平台双重拒绝(ISC-3b/4/5 达成)。所有 main 变更必须走 worktree+PR。
- **子模块**: 保持 direct push(子模块 main 不保护,复用 `sync-submodules-push.sh`);仅主仓 main 走 PR。详见 [`docs/SUBMODULE-PR-STRATEGY.md`](docs/SUBMODULE-PR-STRATEGY.md)。
- **L0 萃取不破坏**: `post-commit` 是 commit 级触发(worktree 共享 `.git/hooks`),worktree 内 commit 照样萃取,派生文件进 PR。
- **完整计划**: [`docs/AGENT-ISOLATION-ROLLOUT.md`](docs/AGENT-ISOLATION-ROLLOUT.md) §4 Phase 2-3 (已落地)。

#### 6.1.1 Worktree 常见踩坑诊断(2026-07-05 多 PR 实战)

| 症状 | 根因 | 解法 |
|------|------|------|
| `submodule-reachability FAIL (N failures)` | worktree partial init | claim 默认已 init ecos+scripts+omo+cockpit+agora (ADR-0204); 仍缺则 `INIT_ALL_SUBMODULES=1` 或 push `--no-verify` (P72) |
| `sync-submodules-push.sh: No such file` | pre-push 未 `make install-hooks` 或旧 hook 路径 | SSOT=`bin/ssot/…` + `bin/` wrapper; 重装 `make install-hooks` |
| compliance `requirement_iteration_no_active_run` | staged 需求面文件但无 active run | `agent-workflow start` + `claim` 后再 stage（ADR-0203/0204） |
| `change-lane-check FAIL mixed lanes` | bin/ governance_code + tests/ code 跨 lane 一 commit | P72 原则4 拆 commit (每 commit 单 lane) |
| `ssot-guardian: direct_omo_io_violation` | direct-io-baseline `entries:` 空 + write_if_changed 是前人实现但未入 baseline | `--no-verify` (P72 原则3, baseline gap pre-existing, CI 兜底) |
| `gac-bootstrap: 非法 executor` (agcp_drift) | claim 未 init cockpit/agora 子模块 | `git submodule update --init projects/cockpit projects/agora` |
| `gh pr create: No commits between main and work/X` | 改动文件大小写不符 (如 PULL_REQUEST_TEMPLATE.md) 或 commit fail | 核 git status + 大小写 + 用 `git add <正确大小写>` |

- **redundant 分支检测**: `python3 bin/ssot/check-branch-redundant.py` (git cherry patch-level, 比 grep 准)

## 7. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Root governance docs | `make gac-local-gate` plus `uv run --with "pyyaml" python "bin/ssot/ssot-guardian.py"` |
| Python code (generic) | Targeted `uv run pytest` or project Makefile `test` target |
| kairon package | `make test-diff` from `projects/kairon` |
| gbrain | `bun test` or targeted Bun test |
| cockpit-ui (TypeScript) | `npm run build` or `bun run build` from `projects/cockpit-ui` |
| observability (Docker) | `docker compose config -q` from `projects/observability` |
| Cross-project contract | Targeted tests on every touched consumer plus relevant integration smoke |

If a test cannot run, report why and what risk remains.

## 8. Historical Patterns

Historical closeout details are useful evidence but should not be pasted into this file. Use pointers:

| Pattern | Read |
|---------|------|
| Agent mutation protocol | [`.omo/standards/agent-mutation-protocol.md`](.omo/standards/agent-mutation-protocol.md) |
| OMO governance surfaces | [`.omo/standards/omo-governance-surfaces.md`](.omo/standards/omo-governance-surfaces.md) |
| GaC North Star | [`.omo/_knowledge/gac/NORTH-STAR.md`](.omo/_knowledge/gac/NORTH-STAR.md) |
| P43 closed-loop pattern | [`.omo/_knowledge/patterns/p43-closed-loop-pattern.md`](.omo/_knowledge/patterns/p43-closed-loop-pattern.md) |
| **P71 baseline recovery pattern** (2026-07-02, 5 阶段声明/执行鸿沟修复) | [`.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md`](.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md) + [closeout](.omo/_knowledge/audits/2026-07-02-p0-baseline-recovery-closeout.md) + [PR #6/#7/#8](https://github.com/starlink-awaken/omostation/pulls?q=is%3Apr+author%3Astarlink-awaken+merged%3A2026-07-02) |
| **P72 follow-up completion pattern** (2026-07-02, 阶段路线图执行守门) | [`.omo/_knowledge/patterns/p72-follow-up-completion-pattern.md`](.omo/_knowledge/patterns/p72-follow-up-completion-pattern.md) + [S1 复盘 ADR-0124](.omo/_knowledge/decisions/0124-s1-followup-retrospective.md) + [PR #17/#18/#19](https://github.com/starlink-awaken/omostation/pulls?q=is%3Apr+author%3Astarlink-awaken+merged%3A2026-07-02) |
| L0/SSOT/M0/MOF 对齐审计 (2026-06-29) | [audit](.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md) + [remediation](.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment-remediation.md) + [ADR-0114 L4 豁免](.omo/_knowledge/decisions/0114-l4-gac-exemption.md) |
| Frontmatter'd yaml 读法 (safe_load_all) | 读 `_truth/` 多文档 yaml 必 `safe_load_all` 取正文 (agent 私有 memory, 不入仓) |
| Executable agent workflows | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |
| AGCP status/scoped gate/claim policy | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |
| Governance evolution roadmap | [`docs/GOVERNANCE-EVOLUTION-ROADMAP.md`](docs/GOVERNANCE-EVOLUTION-ROADMAP.md) |
| State generation convergence | [`.omo/_knowledge/decisions/0128-state-generation-concurrency.md`](.omo/_knowledge/decisions/0128-state-generation-concurrency.md) |
| **3 类声明/执行鸿沟 (P71 §1)** | 路径错位 (类 A, PR#4 baseline 漂移) / 工具未接 (类 B, 9 check-* 0 caller) / CI 永红 (类 C, doctor + project-layer-index). 修复见 P71 5 阶段流程. 防复发见 4 GaC 规则 (CR-X1-EVIDENCE-RUNNABLE / CR-L0-BOS-DOMAIN-NORM / CR-META-BIN-NAMING / CR-META-BIN-ORPHAN) |

## 9. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Prefer `uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>` for governed runs.
4. Mention files changed and checks run.
5. Mention any checks skipped or blocked.
6. Do not create commits unless explicitly requested and confirmed.
7. **大任务后复盘+固化** (P74 常态化精神 — 不靠自觉靠机制):
   - **复盘触发**: 系统性分析/方案任务 / 多轮返工 / Stop hook 反馈后 / 判断错误发现时
   - **判断错误复盘**: 识别"基于不完整信息下结论 / grep 假阴性 / 重复造轮 / 跳过冷启动"等模式 (实证: memory `verify-claim-three-layers`)
   - **三层固化**: 教训写 memory (feedback 类型) + AGENTS.md/CLAUDE.md (协议层, 通用 agent) + hook (harness 层, Claude Code 专属)
   - **目标**: "基于直觉→基于实证", "靠自觉→靠机制守门"

## 10. Round Workflow Playbook (ADR-0148, M4 时代)

每轮 (Round X) 工程是 **commit → ADR → 测 → closeout 的闭环**, 沉淀自 R0..R5b
(22+ commits, 17 ADRs, M4 Health 99.17→100/100)。Round 6+ 直接 follow:

```
Round X 的 7 步:

0. baseline: 跑 m4-health-score, 留当前分数快照
   uv run --with "pyyaml" python bin/mof/m4-health-score.py --emit
1. single-worktree: bash bin/gac/gac-worktree.sh claim round-{X}
2. deliver: 实施 N 个 deliverable (每 PR 1 deliverable)
   - 每次 commit: git log --oneline e2f8f4d7..HEAD
3. tests: 加 T-X 系列测试, 跑 regression
   uv run --with "pyyaml" python tests/integration/m4_metamodel/run_all.py
4. self-reflex: 5-check strict all PASS
   uv run --with "pyyaml" python bin/mof/mof-bootstrap.py all
5. ADR: 写新 ADR (.omo/_knowledge/decisions/{NNN}-title.md), INDEX append
6. health-check: 跑 m4-health-score.py, delta 对比 baseline (不回退)
   uv run --with "pyyaml" python bin/mof/m4-health-score.py --compare
7. close: 写 docs/M4-DECISIONS-INDEX.md (新 ADR 加入),
   准备 PR, 显式 commit PR | round-X-final

end-of-round quality gates (3 个必过):
  G-Tests:   tests/integration/m4_metamodel/run_all.py  N+1/N+1 PASS
  G-Reflex:  bin/mof/mof-bootstrap.py all  5-check strict 0 err
  G-Health:  bin/mof/m4-health-score.py --compare  delta ≥ 0
```

### 10.1 Round 类型参考

| Round | 触发 | 输出 |
|-------|------|------|
| **R-patch** | 修缺陷 / 守门 | 1-2 ADR + 测试, Health 持平或↑ |
| **R-feature** | 新增能力 | 3+ ADR + 工具, Health ↑ |
| **R-meta** | 治本 (如 ADR-0136) | 4-5 ADR + 元模型扩展, Health ↑ |
| **R-archive** | 决策回顾 (如 ADR-0146) | 0 实改, 1-2 ADR 治理声明 |

实际 R0..R5b 覆盖 R-meta (主) / R-patch (R2a, R4c) / R-archive (R2c, R5a)。

### 10.2 P72 / P52 / P74 守门

每 Round 必须显式回答 3 个门槛:

- **P72 路径不过载**: 不重做历史踩坑路径 (e.g. ADR-0139 拒回 8 阶段复活)
- **P52 不动元模型/引擎**: 不直接改 m3.yaml 字段, 不直接改 model-driven 引擎
- **P74 governance 自闭环**: 每 ADR 走 governance-agent profile, 留 evidence

### 10.3 历史 milestone 与覆盖

```
R0 (5 ADR): 主决策 + L0 ↔ M2 桥接 + meta_model ↔ m3 桥接 + 派生面 + 5 改动
R2 (3 ADR): 派生落点 + MetaElement 提升 + 8 阶段拒回
R3 (2 ADR): Health Score 量化 + M2BaseSchema + check_5
R4 (4 ADR): 速查 + 45 m2 datetime + OMO cron hook + MCPTOOL 集合治本
R5 (3 ADR): 8 阶段稳定性 + MCPTOOL adder guide + Round playbook (本 ADR)
```

每 Round 都新增 ADR + 测试 + history 沉淀。Health Score 必须不回退。

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
