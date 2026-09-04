---
type: derived
source: bin/mof/gen-agent-redlines.py → .omo/_truth/registry/governance-checks.yaml::gac.rules
last_updated: 2026-08-26
---

# Agent 红线/灰线清单 (宪法 Wave 1)

> 自动生成 from `governance-checks.yaml::gac.rules` (188 rules). **不要手编辑**.
> severity 推导: executor ∈ {hook_pre_edit, ci_gate} → 🔴 red (阻塞); 否则 → 🟡 gray (warn).
> 重新生成: `python3 bin/mof/gen-agent-redlines.py`

## 🔴 红线 (174 条 — 阻塞 merge, agent 必须遵守)

### X1 (40)

| ID | Name | check_type | executor |
|----|------|-----------|----------|
| `CR-L0-BOS-RESOLVE` | BOS 声明/执行一致 | bos_resolve | evidence_smoke,ci_gate |
| `CR-L2-DIRECT-IO` | .omo 直写拦截 (走 omo ingress, 禁原生 write_text/mkdir) | direct_io_gate | ci_gate,omo_audit |
| `CR-X1-EVIDENCE-RUNNABLE` | GaC 声明可执行证据 (声明绿必须真跑过) | audit_chain | foundry_cron,ci_gate |
| `CR-META-BIN-ORPHAN` | bin 工具未接 caller drift (工具存在但 0 caller) | drift_audit | ci_gate,radar_cron |
| `CR-P74-RUNTIME-STAMP-POLICY` | Runtime stamp policy guard (P74, ADR-0130) | drift_audit | ci_gate,radar_cron |
| `CR-P74-WORKFLOW-SILENCE` | Workflow silence detection (P74, ADR-0130) | audit_chain | ci_gate,evidence_smoke |
| `CR-X1-GOD-MODULE-LIMIT` | god-module 文件行数上限 (新代码 > 1500L 阻塞) | god_module | ci_gate,radar_cron |
| `CR-X1-FRESHNESS-SEMANTIC` | freshness_seconds producer/consumer 语义一致性 | audit_chain | ci_gate,radar_cron |
| `X1-OMNI-BUS-ROUTING-20260617` | ? | legacy_index | omo_audit,ci_gate |
| `X1-OMO-GOVERNANCE-SURFACES-20260616` | ? | legacy_index | omo_audit,ci_gate |
| `X1-OMO-DIRECT-MUTATION-GATE-20260617` | ? | legacy_index | omo_audit,ci_gate |
| `X1-ARCH-MERGE-LLMGATEWAY-20260616` | ? | legacy_index | omo_audit,ci_gate |
| `X1-DEBT-EVIDENCE-CLOSURE-20260620` | ? | legacy_index | omo_audit,ci_gate |
| `X1-CROSS-PROJECT-LINT-ENFORCE-20260620` | ? | legacy_index | omo_audit,ci_gate |
| `X1-AUD-COMMIT-LOOP` | ? | legacy_index | omo_audit,ci_gate |
| `X1-C01` | ? | legacy_index | omo_audit,ci_gate |
| `X1-C02` | ? | legacy_index | omo_audit,ci_gate |
| `CR-MCP-LAZY-01` | ? | legacy_index | omo_audit,ci_gate |
| `CS-10` | ? | legacy_index | omo_audit,ci_gate |
| `CR-VIBEOPS-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-VIBEOPS-02` | ? | legacy_index | omo_audit,ci_gate |
| `CR-RBAC-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ADMISSION-01` | ? | legacy_index | omo_audit,ci_gate |
| `X1-C03` | ? | legacy_index | omo_audit,ci_gate |
| `CR-OMO-SURFACE-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-OMO-SURFACE-02` | ? | legacy_index | omo_audit,ci_gate |
| `CR-C2G-INGRESS-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-OMO-DIRECT-IO-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-DEBT-CLOSURE-EVIDENCE-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-GOV-CLOSED-LOOP-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-GOV-COMMIT-FREQUENCY-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ENG-MYPY-TRUTH-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ENG-TEST-ISOLATION-01` | ? | legacy_index | omo_audit,ci_gate |
| `M4-BOOTSTRAP-REFLEX` | M4 自反校验门禁 (5-check) | audit_chain | hook_pre_edit,ci_gate,gac_local_gate |
| `CR-SUBMODULE-BUMP-AUTO` | Submodule pointer 落后检测 (主仓-子仓对称修复) | drift_audit | radar_cron,ci_gate,gac_local_gate |
| `CR-PR-CHECKLIST-COMPLETE` | PR body 必含 WHY/WHAT | drift_audit | ci_gate,gac_local_gate |
| `CR-X2-GOD-MODULE-EDIT` | God Module 编辑门禁 (>800L) | god_module | hook_pre_edit,ci_gate |
| `CR-PR-DESCRIPTION-NON-EMPTY` | PR 描述非空 | audit_chain | hook_pre_edit,ci_gate |
| `CR-OMLX-MESH-GATE-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-C2G-INGRESS-PRECHECK-01` | ? | legacy_index | omo_audit,ci_gate |

### X2 (29)

| ID | Name | check_type | executor |
|----|------|-----------|----------|
| `CR-L1-RUNTIME-HEALTH` | 运行时健康监控新鲜 | freshness | omo_audit,ci_gate |
| `CR-X2-GAC-BOOTSTRAP` | GaC 自举递归 (工具活/indexed 完整/exec 有效/schema 自洽) | drift_audit | ci_gate,radar_cron |
| `CR-X2-GAC-EXEC-DRIFT` | GaC executor 注册 drift (声明 vs 实际存在) | drift_audit | ci_gate,foundry_cron |
| `CR-X2-GOVERNANCE-SEMANTIC-GATE` | 治理语义门禁统一契约 | schema_integrity | ci_gate,gac_local_gate |
| `X2-FRESH-OMO-GOVERNANCE-SURFACES` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-EVIDENCE-ALIAS` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-ARCHIVED-LLMGATEWAY` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-MERGE-CHECKLIST` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-DEBT-EVIDENCE-INTEGRITY` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-CROSS-PROJECT-LINT` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-MOF-VERSION-BUMP` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-DOC-LIFECYCLE` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-COMMIT-FATIGUE` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-OMO-LINT-SIZE` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-GOV-DASHBOARD` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-ADR-DRIFT` | ? | legacy_index | omo_audit,ci_gate |
| `X2-C01` | ? | legacy_index | omo_audit,ci_gate |
| `X2-C02` | ? | legacy_index | omo_audit,ci_gate |
| `X2-C03` | ? | legacy_index | omo_audit,ci_gate |
| `X2-C04` | ? | legacy_index | omo_audit,ci_gate |
| `X2-C05` | ? | legacy_index | omo_audit,ci_gate |
| `CR-CROSS-PROJECT-LINT-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-GOV-FRONTMATTER-SCHEMA-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-GOV-DOC-CATEGORY-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ENG-SSOT-POINTER-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-L4-DOMAIN-REGISTRY-FRESHNESS` | L4 域注册表新鲜度 | freshness | omo_audit,ci_gate |
| `X2-FRESH-NAV-DOC-REVIEW` | ? | legacy_index | omo_audit,ci_gate |
| `X2-FRESH-DEBT-DASHBOARD` | ? | legacy_index | omo_audit,ci_gate |
| `CR-BASELINE-REPLAYED` | 阶段尾 governance score 重放 | drift_audit | radar_cron,omo_audit,ci_gate |

### X3 (27)

| ID | Name | check_type | executor |
|----|------|-----------|----------|
| `CR-X3-DEBT-TIER` | 债务 X3 tier 必声明 | value_roi | omo_audit,ci_gate |
| `CR-P74-WORKFLOW-SUGGEST` | Workflow routing advisory suggest (P74, ADR-0130) | registry_integrity | mcp_tool,ci_gate |
| `X3-C01` | ? | legacy_index | omo_audit,ci_gate |
| `X3-C02` | ? | legacy_index | omo_audit,ci_gate |
| `X3-C03` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ENG-SRP-INCREMENTAL-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-X3-L1-HEALTH-COST` | 运行时健康监控成本可见 | value_roi | omo_audit,ci_gate |
| `CR-X3-L1-PORT-CONSOLIDATION` | 端口合并 ROI | value_roi | omo_audit,ci_gate |
| `CR-X3-L3-COCKPIT-LATENCY` | cockpit 响应延迟 SLA | value_roi | omo_audit,ci_gate |
| `CR-X3-L3-COCKPIT-COVERAGE` | cockpit 功能覆盖率 | value_roi | omo_audit,ci_gate |
| `CR-X3-L2-TEST-ROI` | 测试投入产出比 | value_roi | omo_audit,ci_gate |
| `CR-X3-L2-DEBT-VELOCITY` | 债务清偿速率 | value_roi | omo_audit,ci_gate |
| `CR-X3-L2-MYPY-CLEAN` | mypy 零错误 | value_roi | omo_audit,ci_gate |
| `CR-X3-L2-LINT-CLEAN` | ruff lint 零错误 | value_roi | omo_audit,ci_gate |
| `CR-X3-I0-AGORA-UPTIME` | agora 服务可用性 | value_roi | omo_audit,ci_gate |
| `CR-X3-I0-MCP-COVERAGE` | MCP 工具覆盖率 | value_roi | omo_audit,ci_gate |
| `CR-X3-L0-DOC-SSOT` | 文档 SSOT 零冲突 | value_roi | omo_audit,ci_gate |
| `CR-X3-L0-GAC-COVERAGE` | GaC 规则覆盖率 | value_roi | omo_audit,ci_gate |
| `CR-X3-X-DEBT-SCORING` | omo-debt 评分覆盖率 | value_roi | omo_audit,ci_gate |
| `CR-X3-X-OBSERVABILITY` | 可观测性覆盖 | value_roi | omo_audit,ci_gate |
| `CR-X3-X-SUBMODULE-FRESH` | 子模块新鲜度 | value_roi | omo_audit,ci_gate |
| `CR-CROSS-REPO-CONSISTENT` | 跨仓 BOS URI / port-registry 一致性 (hard, P77 Phase 3 治本后) | consistency_drift | radar_cron,omo_audit,ci_gate,gac_local_gate |
| `CR-CROSS-REPO-CHECK` | 跨仓 unregistered 阈值守门 (hard, P77 Phase 3 治本后 threshold=0) | consistency_drift | radar_cron,ci_gate,gac_local_gate |
| `CR-HARDCODED-PORT` | 跨仓端口硬编码扫描 (P77-5 port-registration-mandatory + P77-7 env-var-SSOT) | consistency_drift | radar_cron,ci_gate,gac_local_gate |
| `CR-ENV-VAR-PORT` | 端口 env var 引用守护 (P77-7 env-var-SSOT) | consistency_drift | ci_gate,gac_local_gate |
| `CR-DEPRECATED-PORT` | deprecated 端口使用检测 (P78-1 dead-port-cleanup) | consistency_drift | ci_gate,gac_local_gate |
| `CR-CROSS-REPO-REGISTRY-CONSISTENT` | 跨仓注册表一致性 | registry_integrity | omo_audit,ci_gate |

### X4 (78)

| ID | Name | check_type | executor |
|----|------|-----------|----------|
| `CR-X4-HEALTH-SSOT` | 健康分 SSOT | ssot_pointer | hook_pre_edit,ci_gate,omo_audit |
| `CR-M0-STAGE-GATE` | M0 7 阶段 Stage/Gate 派生一致 | mof_stage_gate | mof_validate,mof_audit,ci_gate |
| `CR-L2-TASK-DELIVERABLE` | 任务 deliverable 文件路径必填 | task_field | omo_audit,ci_gate |
| `CR-L3-COCKPIT-ENTRY` | cockpit 唯一人类 CLI 入口 | ssot_pointer | omo_audit,ci_gate |
| `CR-HYG-01` | 0 字节文件检查 (防空文件污染) | hygiene_zero_byte | ci_gate |
| `CR-HYG-02` | 大小写 inode 一致 (防 APFS plan/Plans 混淆) | hygiene_case | ci_gate |
| `CR-X4-DOC-SSOT` | 文档 SSOT (markdown 禁硬编码项目元数据, 引用 project-registry) | ssot_pointer | ci_gate |
| `CR-L2-SURFACES-INTEGRITY` | governance surfaces 面定义完整 (state/kernel/ingress plane) | ssot_pointer | omo_audit,ci_gate |
| `CR-L0-PROTOCOLS-SSOT` | protocols 注册表 SSOT (端口/vault/x-axis 禁硬编码) | ssot_pointer | ci_gate |
| `CR-L0-BOS-DOMAIN-NORM` | BOS URI 5 域锁定 + kind 标签 | bos_resolve | ci_gate |
| `CR-META-BIN-NAMING` | bin 工具命名空间一致 | registry_integrity | ci_gate,radar_cron |
| `CR-P74-STATE-PROJECTION-GUARD` | Runtime projection path consistency guard (P74, ADR-0130) | registry_integrity | ci_gate |
| `CR-DOC-NO-LAST-UPDATED` | 文档 SSOT 守门: 不许 > 最后更新 时间戳行 | doc_lifecycle | ci_gate,radar_cron |
| `CR-L0-MATRIX-PORT-CONSISTENCY` | matrix.yaml port 与 port-registry.yaml 一致性 | ssot_lint | ci_gate,gac_local_gate |
| `CR-L0-MATRIX-LAUNCHD-COVERAGE` | daemon 类型服务必须有 launchd_label 或 docker_container | ssot_lint | ci_gate,gac_local_gate |
| `CR-L0-SSOT-PATH-NORM` | SSOT 路径与 broker 写入路径一致 | ssot_lint | ci_gate,radar_cron |
| `CR-META-CI-SKIP-MATRIX` | CI_SKIP_CHECKS ∪ CI_ONLY_CHECKS 覆盖所有 CI 不适用项 | registry_integrity | ci_gate,radar_cron |
| `X4-CONS-OMO-GOVERNANCE-SURFACES` | ? | legacy_index | omo_audit,ci_gate |
| `X4-CONS-LLMGATEWAY-ARCHIVED` | ? | legacy_index | omo_audit,ci_gate |
| `X4-CONS-P43-CLOSED-LOOP-SSOT` | ? | legacy_index | omo_audit,ci_gate |
| `X4-CONS-DEBT-GITIGNORE-BOUNDARY` | ? | legacy_index | omo_audit,ci_gate |
| `X4-CONS-DRIFT-VS-GOVERNANCE` | ? | legacy_index | omo_audit,ci_gate |
| `X4-C01` | ? | legacy_index | omo_audit,ci_gate |
| `X4-C02` | ? | legacy_index | omo_audit,ci_gate |
| `CR-TRIGGER-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-TRIGGER-02` | ? | legacy_index | omo_audit,ci_gate |
| `CR-TRIGGER-03` | ? | legacy_index | omo_audit,ci_gate |
| `CR-TRIGGER-04` | ? | legacy_index | omo_audit,ci_gate |
| `CR-TRIGGER-05` | ? | legacy_index | omo_audit,ci_gate |
| `CR-TRIGGER-06` | ? | legacy_index | omo_audit,ci_gate |
| `MCP` | ? | legacy_index | omo_audit,ci_gate |
| `ACP` | ? | legacy_index | omo_audit,ci_gate |
| `A2A` | ? | legacy_index | omo_audit,ci_gate |
| `BOS_URI` | ? | legacy_index | omo_audit,ci_gate |
| `L0_YAML` | ? | legacy_index | omo_audit,ci_gate |
| `CR-CADENCE-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-INDEX-LOCK-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-MODE-ENV-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-TIME-ENV-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-MODE-COPY-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-DRIFT-LOOP-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-AUDIT-5REPOS-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-MOF-VALIDATE-01` | MOF schema 校验 (L0 constraints + M4 schema 集) | legacy_index | omo_audit,ci_gate |
| `CR-MOF-ALIAS-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-MOF-BIDIR-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-MOF-BRIDGE-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-MOF-STATE-BRIDGE-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-C2G-V3-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-C2G-V3-02` | ? | legacy_index | omo_audit,ci_gate |
| `CR-C2G-V3-03` | ? | legacy_index | omo_audit,ci_gate |
| `CR-STRATEGY-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-STRATEGY-02` | ? | legacy_index | omo_audit,ci_gate |
| `CR-STRATEGY-03` | ? | legacy_index | omo_audit,ci_gate |
| `CR-OMNIBUS-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-OMNIBUS-02` | ? | legacy_index | omo_audit,ci_gate |
| `CR-OMNIBUS-03` | ? | legacy_index | omo_audit,ci_gate |
| `CR-DEBT-GATE-ENUM-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-MOF-VERSION-COUPLED-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-GOV-DIMENSION-SATURATION-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ENG-BUG-CHAIN-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ENG-CWD-ABSOLUTE-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ENG-TOOL-GREP-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-ENG-LOOP-HONESTY-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-X4-TEST-COVERAGE` | 测试覆盖检查 | test_coverage | omo_audit,ci_gate |
| `CR-X4-ADR-LINKS` | ADR 链接完整性 | doc_lifecycle | omo_audit,ci_gate |
| `CR-GAC-M1-INSTANCE-DRIFT-01` | ? | drift_audit | ci_gate,radar_cron |
| `CR-X4-MCPTOOL-IMPL-DRIFT` | ? | consistency_drift | ci_gate |
| `M4-MCPTOOL-INTEGRITY` | MCPTOOL 数据完整性守门 | consistency_drift | ci_gate,gac_local_gate |
| `CR-EVIDENCE-DECLARED` | ADR closeout 引用 ≥1 evidence path | drift_audit | omo_audit,ci_gate |
| `CR-COMMIT-ASSIST-E2E` | commit-assist E2E 测试 (19/19, P77-6-1 e2e-test-for-advisory-tool) | consistency_drift | ci_gate,gac_local_gate |
| `CR-SEC-YAML-BYPASS` | yaml safe_load 强制 (禁止 yaml.load) | yaml_bypass | hook_pre_edit,ci_gate |
| `CR-SEC-SENSITIVE-WRITE` | 敏感信息硬编码禁止 | sensitive_write | hook_pre_edit,ci_gate |
| `CR-SEC-EVAL-EXEC` | eval/exec 禁止 (用 ast.literal_eval) | eval_exec | hook_pre_edit,ci_gate |
| `CR-PY-MUTABLE-DEFAULT` | 函数默认参数禁用 mutable | mutable_default | hook_pre_edit,ci_gate |
| `CR-RUFF-SCOPE-STABLE` | Ruff Scope 稳定 | schema_integrity | ci_gate |
| `CR-WORKTREE-CLEAN-BEFORE-PR` | Worktree 清理 | hygiene_case | hook_pre_edit,ci_gate |
| `CR-KOS-CONSENSUS-RAG-01` | ? | legacy_index | omo_audit,ci_gate |
| `CR-KOS-ONTOLOGY-DRIFT-01` | ? | legacy_index | omo_audit,ci_gate |

## 🟡 灰线 (14 条 — warn/审计, 不阻塞 merge)

### X1 (7)

- `CR-X1-AGENT-AUDIT`: agent 操作审计链 (audit_chain)
- `CR-L2-MUTATION-BROKER`: mutation surfaces broker 写权限注册 (非 broker 禁写) (audit_chain)
- `M4-SUBMODULE-HYGIENE`: 子模块卫生守门 (audit_chain)
- `M4-DERIVED-PLANE-AUDIT`: 派生面范式审计 (ssot_pointer)
- `CR-FOUNDRY-MONITOR`: Knowledge Foundry cron 监控 (drift_audit)
- `CR-PRINCIPLE-FOLLOWED`: P76 沉淀原则 catalog 引用 (ssot_pointer)
- `CR-PRINCIPLE-ENFORCEMENT`: 原则执行化 (audit_chain)

### X2 (2)

- `CR-X2-GAC-DRIFT`: GaC drift 自检 (注册表 vs 实际执行) (drift_audit)
- `M4-HEALTH-SCORE`: M4 Health Score 量化 (freshness)

### X3 (5)

- `CR-LAYER-CALL-DIRECTION`: 分层调用方向契约 (consistency_drift)
- `CR-META-METRIC-DEBT-FEATURE`: debt-closed-per-feature 指标 (drift_audit)
- `CR-X-PROMOTION-LIFECYCLE`: X 扩展晋升 4 阶段守门 (drift_audit)
- `CR-COMMIT-LLM-ASSIST`: LLM-assisted commit (advisory 硬门) (drift_audit)
- `CR-CROSS-REPO`: 跨仓一致性规则族 (registry_integrity)
