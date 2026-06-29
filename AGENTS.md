# AGENTS.md — Workspace Development Guide

> Root operating guide for AI coding agents and developers working in this workspace.
> Keep this file operational. Put runtime facts in SSOT files, not here.

## 1. Read This First

Before editing:

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check the current working tree with `git status --short`.
4. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
5. For multi-file or high-risk changes, explain the edit surface before applying patches.

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
| [`.omo/state/system.yaml`](.omo/state/system.yaml) | Runtime state | Runtime probes and OMO state sync |

Do not hard-code current phase, health score, test counts, tool counts, service counts, source-file counts, port values, or generated rule inventories in Markdown. Use pointers.

The full documentation contract is [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md).

## 3. Architecture Summary

```
L4  Self       -> l4-kernel
L3  Entry      -> cockpit / cockpit-ui
I0  Weave      -> agora
L2  Engine     -> kairon / gbrain / omo / metaos
L1  Runtime    -> runtime
L0  Protocol   -> ecos
M0  Lifecycle  -> model-driven
X   Frameworks -> aetherforge / c2g / bus-foundation / omo-debt / observability / family-hub / spaces
```

Stable architecture details live in [`ARCHITECTURE.md`](ARCHITECTURE.md). Project metadata and counts live in [`docs/project-registry.yaml`](docs/project-registry.yaml).

## 4. Governance Boundaries

| Surface | Rule |
|---------|------|
| `.omo/` | State/evidence plane. Do not add long-lived execution logic here. |
| `projects/omo/` | Governance kernel: schema, audit, sync, broker, lint, task/debt lifecycle. |
| `projects/c2g/` | Strategy ingress: pitch/bet materialization into governed tasks. |
| `projects/ecos/` | Protocol and MOF layer. |
| `spaces/` | User/tenant-space manifests. Treat as governed configuration. |

For `.omo` or `spaces` mutations, use the registered broker/CLI path. If a task truly needs direct manual edits, call that out and keep the patch minimal.

## 5. Essential Commands

```bash
make gac-local-gate
uv run --with "pyyaml" python "bin/doc-ssot-lint.py" --json
uv run --with "pyyaml" python "bin/ssot-guardian.py"
uv run --with "pyyaml" python "bin/gac-validate.py" --gate
uv run --with "pyyaml" python "bin/gac-drift.py"
bash "tests/integration/run-all.sh"
cd "projects/kairon" && make test-diff
cd "projects/gbrain" && bun test
```

Prefer targeted checks for narrow edits. Broaden verification when the change touches shared contracts, generated registries, public entry points, or cross-project behavior.

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, destructive checkout, or branch switching unless the user explicitly asked or confirmed.
- Root repository tracks submodule pointers and workspace metadata.
- Most `projects/*` directories are independent repositories. Commit inside the submodule first only when the user requested commits, then update the root pointer.
- Never revert unrelated dirty files. Treat them as user or concurrent-agent work.

## 7. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Root governance docs | `make gac-local-gate` plus `uv run --with "pyyaml" python "bin/ssot-guardian.py"` |
| Python code | Targeted `uv run pytest` or project Makefile target |
| kairon package | `make test-diff` from `projects/kairon` |
| gbrain | `bun test` or targeted Bun test |
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

## 9. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Mention files changed and checks run.
4. Mention any checks skipped or blocked.
5. Do not create commits unless explicitly requested and confirmed.

<!-- GaC-RULES-START -->
<!-- AUTO-GENERATED by bin/gac-export-agents.py — do not edit manually -->
<!-- Run: python3 bin/gac-export-agents.py to regenerate. Source: governance-checks.yaml (132 rules) -->

### GaC 规则速览 (132 条)

> SSOT: `.omo/_truth/registry/governance-checks.yaml::gac.rules`
> 校验: `python3 bin/gac-validate.py --gate` | 漂移: `python3 bin/gac-drift.py`

#### X1 审计 (29 条)

| 规则 ID | 层 | 检查类型 | 描述 |
|---------|:--:|---------|------|
| `CR-ADMISSION-01` | L0 | legacy_index |  |
| `CR-C2G-INGRESS-01` | L0 | legacy_index |  |
| `CR-DEBT-CLOSURE-EVIDENCE-01` | L0 | legacy_index |  |
| `CR-ENG-MYPY-TRUTH-01` | L0 | legacy_index |  |
| `CR-ENG-TEST-ISOLATION-01` | L0 | legacy_index |  |
| `CR-GOV-CLOSED-LOOP-01` | L0 | legacy_index |  |
| `CR-GOV-COMMIT-FREQUENCY-01` | L0 | legacy_index |  |
| `CR-L0-BOS-RESOLVE` | L0 | bos_resolve | BOS URI 声明必须 resolve (evidence-smoke 防 alive 标志假阳) |
| `CR-L2-DIRECT-IO` | L2 | direct_io_gate | 禁止绕过 omo ingress 直写 .omo (防状态竞态死锁, 报告债务① Critical) |
| `CR-L2-MUTATION-BROKER` | L2 | audit_chain | mutation-surfaces.yaml broker 注册权威 (entrypoint+target+mode), |
| `CR-MCP-LAZY-01` | L0 | legacy_index |  |
| `CR-OMO-DIRECT-IO-01` | L0 | legacy_index |  |
| `CR-OMO-SURFACE-01` | L0 | legacy_index |  |
| `CR-OMO-SURFACE-02` | L0 | legacy_index |  |
| `CR-RBAC-01` | L0 | legacy_index |  |
| `CR-VIBEOPS-01` | L0 | legacy_index |  |
| `CR-VIBEOPS-02` | L0 | legacy_index |  |
| `CR-X1-AGENT-AUDIT` | meta | audit_chain | agent 编辑经 MCP/omo CLI, 自动记 AppendOnlyLog (可追溯) |
| `CS-10` | L0 | legacy_index |  |
| `X1-ARCH-MERGE-LLMGATEWAY-20260616` | meta | legacy_index |  |
| `X1-AUD-COMMIT-LOOP` | meta | legacy_index |  |
| `X1-C01` | L0 | legacy_index |  |
| `X1-C02` | L0 | legacy_index |  |
| `X1-C03` | L0 | legacy_index |  |
| `X1-CROSS-PROJECT-LINT-ENFORCE-20260620` | meta | legacy_index |  |
| `X1-DEBT-EVIDENCE-CLOSURE-20260620` | meta | legacy_index |  |
| `X1-OMNI-BUS-ROUTING-20260617` | meta | legacy_index |  |
| `X1-OMO-DIRECT-MUTATION-GATE-20260617` | meta | legacy_index |  |
| `X1-OMO-GOVERNANCE-SURFACES-20260616` | meta | legacy_index |  |

#### X2 抗熵 (25 条)

| 规则 ID | 层 | 检查类型 | 描述 |
|---------|:--:|---------|------|
| `CR-CROSS-PROJECT-LINT-01` | L0 | legacy_index |  |
| `CR-ENG-SSOT-POINTER-01` | L0 | legacy_index |  |
| `CR-GOV-DOC-CATEGORY-01` | L0 | legacy_index |  |
| `CR-GOV-FRONTMATTER-SCHEMA-01` | L0 | legacy_index |  |
| `CR-L1-RUNTIME-HEALTH` | L1 | freshness | runtime 健康监控数据新鲜 (不超 24h, X2 抗熵) |
| `CR-X2-GAC-BOOTSTRAP` | meta | drift_audit | GaC 治一切, GaC 自己也要被治 (NORTH-STAR 元治理递归); bin/gac-bootstrap.py |
| `CR-X2-GAC-DRIFT` | meta | drift_audit | 防 GaC 自己走偏: 注册表规则 vs hook/mcp/gate 实际注册, drift 告警 + 自愈 |
| `CR-X2-GAC-EXEC-DRIFT` | meta | drift_audit | GaC 规则声明 executor (ci_gate/omo_audit/evidence_smoke 等), 验证实际 |
| `X2-C01` | L0 | legacy_index |  |
| `X2-C02` | L0 | legacy_index |  |
| `X2-C03` | L0 | legacy_index |  |
| `X2-C04` | L0 | legacy_index |  |
| `X2-C05` | L0 | legacy_index |  |
| `X2-FRESH-ADR-DRIFT` | meta | legacy_index |  |
| `X2-FRESH-ARCHIVED-LLMGATEWAY` | meta | legacy_index |  |
| `X2-FRESH-COMMIT-FATIGUE` | meta | legacy_index |  |
| `X2-FRESH-CROSS-PROJECT-LINT` | meta | legacy_index |  |
| `X2-FRESH-DEBT-EVIDENCE-INTEGRITY` | meta | legacy_index |  |
| `X2-FRESH-DOC-LIFECYCLE` | meta | legacy_index |  |
| `X2-FRESH-EVIDENCE-ALIAS` | meta | legacy_index |  |
| `X2-FRESH-GOV-DASHBOARD` | meta | legacy_index |  |
| `X2-FRESH-MERGE-CHECKLIST` | meta | legacy_index |  |
| `X2-FRESH-MOF-VERSION-BUMP` | meta | legacy_index |  |
| `X2-FRESH-OMO-GOVERNANCE-SURFACES` | meta | legacy_index |  |
| `X2-FRESH-OMO-LINT-SIZE` | meta | legacy_index |  |

#### X3 价值 (20 条)

| 规则 ID | 层 | 检查类型 | 描述 |
|---------|:--:|---------|------|
| `CR-ENG-SRP-INCREMENTAL-01` | L0 | legacy_index |  |
| `CR-X3-DEBT-TIER` | L2 | value_roi | debt items 必声明 x3_tier (价值分级, 投入产出可量化) |
| `CR-X3-I0-AGORA-UPTIME` | I0 | value_roi | agora BOS 服务可用性 ≥ 99% (路由层 = 价值命脉, X3 产出) |
| `CR-X3-I0-MCP-COVERAGE` | I0 | value_roi | agora MCP 工具覆盖 ≥ 90% BOS 服务 (工具缺失 = 价值缺口, X3) |
| `CR-X3-L0-DOC-SSOT` | L0 | value_roi | doc-ssot-lint 0 冲突 (文档一致性 = 减少误导成本, X3 投入产出) |
| `CR-X3-L0-GAC-COVERAGE` | L0 | value_roi | GaC 规则覆盖 4 dimension × 5+ layer (规则缺口 = 治理盲区, X3 价值) |
| `CR-X3-L1-HEALTH-COST` | L1 | value_roi | runtime 健康监控必须有成本标记 (探针开销 ≤ 总资源 5%, X3 投入产出) |
| `CR-X3-L1-PORT-CONSOLIDATION` | L1 | value_roi | runtime 暴露端口数 ≤ 注册表上限 (每多一个端口 = +1 运维成本, X3 投入) |
| `CR-X3-L2-DEBT-VELOCITY` | L2 | value_roi | debt items 关闭速率 ≥ 新增速率 (债务不增长, X3 价值流) |
| `CR-X3-L2-LINT-CLEAN` | L2 | value_roi | 全项目 ruff check 0 错误 (代码质量 = 产出质量, X3 价值) |
| `CR-X3-L2-MYPY-CLEAN` | L2 | value_roi | kairon mypy 类型检查 0 错误 (类型安全 = 产出质量, X3 价值) |
| `CR-X3-L2-TEST-ROI` | L2 | value_roi | 每个 L2 项目测试/代码比 ≥ 0.5 (测试投入 ≤ 代码量 2x, X3 产出) |
| `CR-X3-L3-COCKPIT-COVERAGE` | L3 | value_roi | cockpit 命令覆盖 ≥ 80% L2 功能 (用户入口完整性, X3 价值) |
| `CR-X3-L3-COCKPIT-LATENCY` | L3 | value_roi | cockpit CLI 命令 P95 延迟 ≤ 2s (用户价值 = 响应速度, X3 产出) |
| `CR-X3-X-DEBT-SCORING` | X | value_roi | omo-debt 评分覆盖所有 L2 项目 (债务可量化 = 投入可决策, X3 价值) |
| `CR-X3-X-OBSERVABILITY` | X | value_roi | observability 部署覆盖所有 L2 项目 (追踪覆盖 = 价值可见, X3 产出) |
| `CR-X3-X-SUBMODULE-FRESH` | X | value_roi | submodule 滞后 ≤ 3 天 (滞后 = 价值流失, X3 投入产出) |
| `X3-C01` | L0 | legacy_index |  |
| `X3-C02` | L0 | legacy_index |  |
| `X3-C03` | L0 | legacy_index |  |

#### X4 一致性 (58 条)

| 规则 ID | 层 | 检查类型 | 描述 |
|---------|:--:|---------|------|
| `A2A` | L0 | legacy_index |  |
| `ACP` | L0 | legacy_index |  |
| `BOS_URI` | L0 | legacy_index |  |
| `CR-AUDIT-5REPOS-01` | L0 | legacy_index |  |
| `CR-C2G-V3-01` | L0 | legacy_index |  |
| `CR-C2G-V3-02` | L0 | legacy_index |  |
| `CR-C2G-V3-03` | L0 | legacy_index |  |
| `CR-CADENCE-01` | L0 | legacy_index |  |
| `CR-DEBT-GATE-ENUM-01` | L0 | legacy_index |  |
| `CR-DRIFT-LOOP-01` | L0 | legacy_index |  |
| `CR-ENG-BUG-CHAIN-01` | L0 | legacy_index |  |
| `CR-ENG-CWD-ABSOLUTE-01` | L0 | legacy_index |  |
| `CR-ENG-LOOP-HONESTY-01` | L0 | legacy_index |  |
| `CR-ENG-TOOL-GREP-01` | L0 | legacy_index |  |
| `CR-GAC-M1-INSTANCE-DRIFT-01` | meta | drift_audit |  |
| `CR-GOV-DIMENSION-SATURATION-01` | L0 | legacy_index |  |
| `CR-HYG-01` | meta | hygiene_zero_byte | pre-commit 扫描 0 字节文件 (报告建议3 CR-HYG-01) |
| `CR-HYG-02` | meta | hygiene_case | pre-commit 大小写拼写一致性 (报告建议3 CR-HYG-02, APFS case-insensitive) |
| `CR-INDEX-LOCK-01` | L0 | legacy_index |  |
| `CR-L0-PROTOCOLS-SSOT` | L0 | ssot_pointer | protocols/{port,vault-paths,x-axis}-registry.yaml 协议层 SSOT,  |
| `CR-L2-SURFACES-INTEGRITY` | L2 | ssot_pointer | omo-governance-surfaces.yaml 面定义权威 (plane 资产归属), GaC 引用不复制;  |
| `CR-L2-TASK-DELIVERABLE` | L2 | task_field | OMO 任务必声明 deliverables (task-yaml-rules 规则 1) |
| `CR-L3-COCKPIT-ENTRY` | L3 | ssot_pointer | cockpit 是唯一人类 CLI/Web 入口 (其他 CLI 程序接口, X4 一致) |
| `CR-M0-STAGE-GATE` | M0 | mof_stage_gate | M1→M2→M3 派生必走 mof Stage/Gate (零风险派生) |
| `CR-MODE-COPY-01` | L0 | legacy_index |  |
| `CR-MODE-ENV-01` | L0 | legacy_index |  |
| `CR-MOF-ALIAS-01` | L0 | legacy_index |  |
| `CR-MOF-BIDIR-01` | L0 | legacy_index |  |
| `CR-MOF-BRIDGE-01` | L0 | legacy_index |  |
| `CR-MOF-STATE-BRIDGE-01` | L0 | legacy_index |  |
| `CR-MOF-VALIDATE-01` | L0 | legacy_index |  |
| `CR-MOF-VERSION-COUPLED-01` | L0 | legacy_index |  |
| `CR-OMNIBUS-01` | L0 | legacy_index |  |
| `CR-OMNIBUS-02` | L0 | legacy_index |  |
| `CR-OMNIBUS-03` | L0 | legacy_index |  |
| `CR-STRATEGY-01` | L0 | legacy_index |  |
| `CR-STRATEGY-02` | L0 | legacy_index |  |
| `CR-STRATEGY-03` | L0 | legacy_index |  |
| `CR-TIME-ENV-01` | L0 | legacy_index |  |
| `CR-TRIGGER-01` | L0 | legacy_index |  |
| `CR-TRIGGER-02` | L0 | legacy_index |  |
| `CR-TRIGGER-03` | L0 | legacy_index |  |
| `CR-TRIGGER-04` | L0 | legacy_index |  |
| `CR-TRIGGER-05` | L0 | legacy_index |  |
| `CR-TRIGGER-06` | L0 | legacy_index |  |
| `CR-X4-ADR-LINKS` | L2 | doc_lifecycle | ADR INDEX.md 引用的所有 ADR 文件必须存在 (omo_audit 检查 #4) |
| `CR-X4-DOC-SSOT` | meta | ssot_pointer | 101 markdown 禁硬编码 (包数/版本/Phase/健康分), 引用 docs/project-registr |
| `CR-X4-HEALTH-SSOT` | L2 | ssot_pointer | health_score 唯一源 system.yaml, 文档用指针不复制 |
| `CR-X4-TEST-COVERAGE` | L2 | test_coverage | 每个非归档 kairon 包至少 1 个 test_*.py (omo_audit 检查 #2) |
| `L0_YAML` | L0 | legacy_index |  |
| `MCP` | L0 | legacy_index |  |
| `X4-C01` | L0 | legacy_index |  |
| `X4-C02` | L0 | legacy_index |  |
| `X4-CONS-DEBT-GITIGNORE-BOUNDARY` | meta | legacy_index |  |
| `X4-CONS-DRIFT-VS-GOVERNANCE` | meta | legacy_index |  |
| `X4-CONS-LLMGATEWAY-ARCHIVED` | meta | legacy_index |  |
| `X4-CONS-OMO-GOVERNANCE-SURFACES` | meta | legacy_index |  |
| `X4-CONS-P43-CLOSED-LOOP-SSOT` | meta | legacy_index |  |

<!-- GaC-RULES-END -->
