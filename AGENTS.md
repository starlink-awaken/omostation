# AGENTS.md — Workspace Development Guide

> 最后更新: 2026-07-02
> Root operating guide for AI coding agents and developers working in this workspace.
> Keep this file operational. Put runtime facts in SSOT files, not here.

## 1. Read This First

Before editing:

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check the current working tree with `git status --short`.
4. For multi-step work, run `uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap`, check `status`, create a run with `start`, then claim the edit surface with `claim <run-id> --path <path>`.
5. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
6. For multi-file or high-risk changes, explain the edit surface before applying patches.

Project-specific instructions override this guide only within that project and only when they do not violate workspace governance.

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
| [`.omo/_truth/x1-governance-policies.yaml`](.omo/_truth/x1-governance-policies.yaml) | X1 governance policies | Governance policy SSOT |
| [`.omo/_truth/x2-freshness-rules.yaml`](.omo/_truth/x2-freshness-rules.yaml) | X2 freshness rules | Doc freshness SSOT |
| [`.omo/_truth/x3-value-stack.yaml`](.omo/_truth/x3-value-stack.yaml) | X3 value stack | Value chain SSOT |
| [`.omo/_truth/x4-consistency-rules.yaml`](.omo/_truth/x4-consistency-rules.yaml) | X4 consistency rules | Consistency SSOT |
| [`projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`](projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml) | L0 protocol constraints | Constraint SSOT |
| [`.omo/state/system.yaml`](.omo/state/system.yaml) | Runtime state | Runtime probes and OMO state sync |

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

```bash
make gac-local-gate
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" list
uv run --with "pyyaml" python "bin/agent-workflow.py" agents
uv run --with "pyyaml" python "bin/agent-workflow.py" integrations
uv run --with "pyyaml" python "bin/agent-workflow.py" adapters
uv run --with "pyyaml" python "bin/agent-workflow.py" lint
uv run --with "pyyaml" python "bin/agent-workflow.py" status --json
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" verify <run-id> --from-diff --execute
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance <run-id>
uv run --with "pyyaml" python "bin/agent-workflow.py" doctor
uv run --with "pyyaml" python "bin/governance-evolution.py" status --json
uv run --with "pyyaml" python "bin/governance-evolution.py" validate --json
uv run --with "pyyaml" python "bin/gac-local-gate.py" --scope files --file <path> --json
uv run --with "pyyaml" python "bin/doc-ssot-lint.py" --json
uv run --with "pyyaml" python "bin/ssot-guardian.py"
uv run --with "pyyaml" python "bin/gac-validate.py" --gate
uv run --with "pyyaml" python "bin/gac-drift.py"
bash "tests/integration/run-all.sh"
cd "projects/kairon" && make test-diff
cd "projects/gbrain" && bun test
```

`make gac-local-gate` runs the default (non-strict) GaC gate — GaC validate/drift, agent-workflow lint/integrations/adapters/bootstrap/observe, MOF schema/state-bridge/drift, documentation SSOT, doc link/snapshot, and staged change-lane checks. Two skip rules apply in default mode, both isolating concurrent-agent dirty in a shared worktree: `verify-plan`/`compliance`/`doctor` run only when staged touches agent-workflow (`896e60ba`); `project-layer-index` (generated layer digest) is CI-only — pre-commit/`make` skip it, `--strict`/CI runs it (`d33af25c`). For run/file-scoped AGCP verification use `bin/gac-local-gate.py --scope ...`. Authoritative check list + skip rules live in `bin/gac-local-gate.py` (`CHECKS`, `AGENT_WORKFLOW_GATE_CHECKS`, `CI_ONLY_CHECKS`) — do not duplicate here.

Additional tools (not in gac-local-gate):

```bash
uv run --with "pyyaml" python "bin/gac-healthcheck.py"   # GaC 13-point health check
uv run --with "pyyaml" python "bin/evidence-smoke.py"     # BOS declaration vs execution gap audit
uv run --with "pyyaml" python "bin/gen-project-registry.py"  # Registry drift detection (code→registry)
```

See [`bin/README.md`](bin/README.md) for the full tool catalog.

Prefer targeted checks for narrow edits. Broaden verification when the change touches shared contracts, generated registries, public entry points, or cross-project behavior.

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, destructive checkout, or branch switching unless the user explicitly asked or confirmed.
- Root repository tracks submodule pointers and workspace metadata.
- Most `projects/*` directories are independent repositories. Commit inside the submodule first only when the user requested commits, then update the root pointer.
- Never revert unrelated dirty files. Treat them as user or concurrent-agent work.

### 6.1 PR 工作流(Phase 2,渐进推进)

主仓 main 变更走 **per-session worktree + PR**,消灭 direct push to main(多 agent 撞车根因)。工具:`bin/gac-worktree.sh`。

```bash
bash bin/gac-worktree.sh claim <session>   # 起隔离 worktree (work/<session> 分支)
cd ../ws-<session>                          # 改文件 + commit (改子模块先 git submodule update --init)
bash bin/gac-worktree.sh submit <session>   # push 分支 + 开 PR (base main)
bash bin/gac-worktree.sh merge <session>    # squash 合并 PR + release + 删分支
```

- **当前状态(2026-06-30)**: advisory 阶段——pre-push 对 direct push to main 发警告但不阻断(Phase 2a-2)。Phase 2c 升级为 blocking(本地拒绝)。
- **子模块**: 保持 direct push(子模块 main 不保护,复用 `sync-submodules-push.sh`);仅主仓 main 走 PR。详见 [`docs/SUBMODULE-PR-STRATEGY.md`](docs/SUBMODULE-PR-STRATEGY.md)。
- **L0 萃取不破坏**: `post-commit` 是 commit 级触发(worktree 共享 `.git/hooks`),worktree 内 commit 照样萃取,派生文件进 PR。
- **完整计划**: [`docs/AGENT-ISOLATION-ROLLOUT.md`](docs/AGENT-ISOLATION-ROLLOUT.md) §4 Phase 2。

## 7. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Root governance docs | `make gac-local-gate` plus `uv run --with "pyyaml" python "bin/ssot-guardian.py"` |
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
| L0/SSOT/M0/MOF 对齐审计 (2026-06-29) | [audit](.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md) + [remediation](.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment-remediation.md) + [ADR-0114 L4 豁免](.omo/_knowledge/decisions/0114-l4-gac-exemption.md) |
| Frontmatter'd yaml 读法 (safe_load_all) | 读 `_truth/` 多文档 yaml 必 `safe_load_all` 取正文 (agent 私有 memory, 不入仓) |
| Executable agent workflows | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |
| AGCP status/scoped gate/claim policy | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |
| Governance evolution roadmap | [`docs/GOVERNANCE-EVOLUTION-ROADMAP.md`](docs/GOVERNANCE-EVOLUTION-ROADMAP.md) |
| **3 类声明/执行鸿沟 (P71 §1)** | 路径错位 (类 A, PR#4 baseline 漂移) / 工具未接 (类 B, 9 check-* 0 caller) / CI 永红 (类 C, doctor + project-layer-index). 修复见 P71 5 阶段流程. 防复发见 4 GaC 规则 (CR-X1-EVIDENCE-RUNNABLE / CR-L0-BOS-DOMAIN-NORM / CR-META-BIN-NAMING / CR-META-BIN-ORPHAN) |

## 9. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Prefer `uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>` for governed runs.
4. Mention files changed and checks run.
5. Mention any checks skipped or blocked.
6. Do not create commits unless explicitly requested and confirmed.

<!-- GaC-RULES-START -->
<!-- AUTO-GENERATED by bin/gac-export-agents.py — do not edit manually -->

### GaC Rules Pointer

> SSOT: `.omo/_truth/registry/governance-checks.yaml::gac.rules`
> Full generated digest: `docs/generated/agent-gac-rules.md`
> Validate: `python3 bin/gac-validate.py --gate` | Drift: `python3 bin/gac-drift.py`
> Regenerate: `python3 bin/gac-export-agents.py`

Do not paste the full rule inventory into `AGENTS.md`; keep this file as an operational pointer.

<!-- GaC-RULES-END -->
