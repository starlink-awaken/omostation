# eCOS v6 物理拓扑与架构依赖图谱

> **自动刷新时间**: 2026-07-06 15:44:53
> **数据源**: KOS SQLite 本体引擎 · `EicosParser` 自动提取

```mermaid
graph TD
    %% Style definitions
    classDef project fill:#2b303c,stroke:#4f5b66,stroke-width:1px,color:#fff;
    classDef node fill:#1f3c3d,stroke:#3e787a,stroke-width:2px,color:#fff;
    classDef axiom fill:#4a3c31,stroke:#8f7b6e,stroke-width:1px,color:#fff;
    classDef concept fill:#3c2b3d,stroke:#77567a,stroke-width:1px,color:#fff;
    classDef evidence fill:#5c2b2b,stroke:#b85c5c,stroke-width:2px,color:#fff;
    A_A2A["A:A2A"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_ACP["A:ACP"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_BOS_URI["A:BOS_URI"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ADMISSION_01["A:CR-ADMISSION-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_AUDIT_5REPOS_01["A:CR-AUDIT-5REPOS-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_C2G_INGRESS_01["A:CR-C2G-INGRESS-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_C2G_V3_01["A:CR-C2G-V3-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_C2G_V3_02["A:CR-C2G-V3-02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_C2G_V3_03["A:CR-C2G-V3-03"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_CADENCE_01["A:CR-CADENCE-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_CROSS_PROJECT_LINT_01["A:CR-CROSS-PROJECT-LINT-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_DEBT_CLOSURE_EVIDENCE_01["A:CR-DEBT-CLOSURE-EVIDENCE-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_DEBT_GATE_ENUM_01["A:CR-DEBT-GATE-ENUM-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_DOC_NO_LAST_UPDATED["A:文档 SSOT 守门: 不许 > 最后更新 时间戳行"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_DRIFT_LOOP_01["A:CR-DRIFT-LOOP-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ENG_BUG_CHAIN_01["A:CR-ENG-BUG-CHAIN-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ENG_CWD_ABSOLUTE_01["A:CR-ENG-CWD-ABSOLUTE-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ENG_LOOP_HONESTY_01["A:CR-ENG-LOOP-HONESTY-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ENG_MYPY_TRUTH_01["A:CR-ENG-MYPY-TRUTH-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ENG_SRP_INCREMENTAL_01["A:CR-ENG-SRP-INCREMENTAL-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ENG_SSOT_POINTER_01["A:CR-ENG-SSOT-POINTER-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ENG_TEST_ISOLATION_01["A:CR-ENG-TEST-ISOLATION-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_ENG_TOOL_GREP_01["A:CR-ENG-TOOL-GREP-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_GAC_M1_INSTANCE_DRIFT_01["A:CR-GAC-M1-INSTANCE-DRIFT-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_GOV_CLOSED_LOOP_01["A:CR-GOV-CLOSED-LOOP-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_GOV_COMMIT_FREQUENCY_01["A:CR-GOV-COMMIT-FREQUENCY-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_GOV_DIMENSION_SATURATION_01["A:CR-GOV-DIMENSION-SATURATION-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_GOV_DOC_CATEGORY_01["A:CR-GOV-DOC-CATEGORY-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_GOV_FRONTMATTER_SCHEMA_01["A:CR-GOV-FRONTMATTER-SCHEMA-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_HYG_01["A:0 字节文件检查 (防空文件污染)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_HYG_02["A:大小写 inode 一致 (防 APFS plan/Plans 混淆)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_INDEX_LOCK_01["A:CR-INDEX-LOCK-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L0_BOS_DOMAIN_NORM["A:BOS URI 5 域锁定 + kind 标签"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L0_BOS_RESOLVE["A:BOS 声明/执行一致"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L0_MATRIX_LAUNCHD_COVERAGE["A:daemon 类型服务必须有 launchd_label 或 docker_container"]:::axiom -->|related_to| D_ADR_0120["ADR-0120"]
    A_CR_L0_MATRIX_PORT_CONSISTENCY["A:matrix.yaml port 与 port-registry.yaml 一致性"]:::axiom -->|related_to| D_ADR_0120["ADR-0120"]
    A_CR_L0_PROTOCOLS_SSOT["A:protocols 注册表 SSOT (端口/vault/x-axis 禁硬编码)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L0_SSOT_PATH_NORM["A:SSOT 路径与 broker 写入路径一致"]:::axiom -->|related_to| D_ADR_0121["ADR-0121"]
    A_CR_L1_RUNTIME_HEALTH["A:运行时健康监控新鲜"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L2_DIRECT_IO["A:.omo 直写拦截 (走 omo ingress, 禁原生 write_text/mkdir)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L2_MUTATION_BROKER["A:mutation surfaces broker 写权限注册 (非 broker 禁写)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L2_SURFACES_INTEGRITY["A:governance surfaces 面定义完整 (state/kernel/ingress plane)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L2_TASK_DELIVERABLE["A:任务 deliverable 文件路径必填"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L3_COCKPIT_ENTRY["A:cockpit 唯一人类 CLI 入口"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_L4_DOMAIN_REGISTRY_FRESHNESS["A:L4 域注册表新鲜度"]:::axiom -->|related_to| D_ADR_0114["ADR-0114"]
    A_CR_M0_STAGE_GATE["A:M0 7 阶段 Stage/Gate 派生一致"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_MCP_LAZY_01["A:CR-MCP-LAZY-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_META_BIN_NAMING["A:bin 工具命名空间一致"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_META_BIN_ORPHAN["A:bin 工具未接 caller drift (工具存在但 0 caller)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_META_CI_SKIP_MATRIX["A:CI_SKIP_CHECKS ∪ CI_ONLY_CHECKS 覆盖所有 CI 不适用项"]:::axiom -->|related_to| D_ADR_0121["ADR-0121"]
    A_CR_MODE_COPY_01["A:CR-MODE-COPY-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_MODE_ENV_01["A:CR-MODE-ENV-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_MOF_ALIAS_01["A:CR-MOF-ALIAS-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_MOF_BIDIR_01["A:CR-MOF-BIDIR-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_MOF_BRIDGE_01["A:CR-MOF-BRIDGE-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_MOF_STATE_BRIDGE_01["A:CR-MOF-STATE-BRIDGE-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_MOF_VALIDATE_01["A:CR-MOF-VALIDATE-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_MOF_VERSION_COUPLED_01["A:CR-MOF-VERSION-COUPLED-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_OMNIBUS_01["A:CR-OMNIBUS-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_OMNIBUS_02["A:CR-OMNIBUS-02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_OMNIBUS_03["A:CR-OMNIBUS-03"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_OMO_DIRECT_IO_01["A:CR-OMO-DIRECT-IO-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_OMO_SURFACE_01["A:CR-OMO-SURFACE-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_OMO_SURFACE_02["A:CR-OMO-SURFACE-02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_P74_RUNTIME_STAMP_POLICY["A:Runtime stamp policy guard (P74, ADR-0130)"]:::axiom -->|related_to| D_ADR_0130["ADR-0130"]
    A_CR_P74_STATE_PROJECTION_GUARD["A:Runtime projection path consistency guard (P74, ADR-0130)"]:::axiom -->|related_to| D_ADR_0130["ADR-0130"]
    A_CR_P74_WORKFLOW_SILENCE["A:Workflow silence detection (P74, ADR-0130)"]:::axiom -->|related_to| D_ADR_0130["ADR-0130"]
    A_CR_P74_WORKFLOW_SUGGEST["A:Workflow routing advisory suggest (P74, ADR-0130)"]:::axiom -->|related_to| D_ADR_0130["ADR-0130"]
    A_CR_RBAC_01["A:CR-RBAC-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_STRATEGY_01["A:CR-STRATEGY-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_STRATEGY_02["A:CR-STRATEGY-02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_STRATEGY_03["A:CR-STRATEGY-03"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_TIME_ENV_01["A:CR-TIME-ENV-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_TRIGGER_01["A:CR-TRIGGER-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_TRIGGER_02["A:CR-TRIGGER-02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_TRIGGER_03["A:CR-TRIGGER-03"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_TRIGGER_04["A:CR-TRIGGER-04"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_TRIGGER_05["A:CR-TRIGGER-05"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_TRIGGER_06["A:CR-TRIGGER-06"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_VIBEOPS_01["A:CR-VIBEOPS-01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_VIBEOPS_02["A:CR-VIBEOPS-02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X1_AGENT_AUDIT["A:agent 操作审计链"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X1_EVIDENCE_RUNNABLE["A:GaC 声明可执行证据 (声明绿必须真跑过)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X1_FRESHNESS_SEMANTIC["A:freshness_seconds producer/consumer 语义一致性"]:::axiom -->|related_to| D_ADR_0120["ADR-0120"]
    A_CR_X1_GOD_MODULE_LIMIT["A:god-module 文件行数上限 (新代码 > 1500L 阻塞)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X2_GAC_BOOTSTRAP["A:GaC 自举递归 (工具活/indexed 完整/exec 有效/schema 自洽)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X2_GAC_DRIFT["A:GaC drift 自检 (注册表 vs 实际执行)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X2_GAC_EXEC_DRIFT["A:GaC executor 注册 drift (声明 vs 实际存在)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X2_GOVERNANCE_SEMANTIC_GATE["A:治理语义门禁统一契约"]:::axiom -->|related_to| D_ADR_0121["ADR-0121"]
    A_CR_X3_DEBT_TIER["A:债务 X3 tier 必声明"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_I0_AGORA_UPTIME["A:agora 服务可用性"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_I0_MCP_COVERAGE["A:MCP 工具覆盖率"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L0_DOC_SSOT["A:文档 SSOT 零冲突"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L0_GAC_COVERAGE["A:GaC 规则覆盖率"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L1_HEALTH_COST["A:运行时健康监控成本可见"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L1_PORT_CONSOLIDATION["A:端口合并 ROI"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L2_DEBT_VELOCITY["A:债务清偿速率"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L2_LINT_CLEAN["A:ruff lint 零错误"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L2_MYPY_CLEAN["A:mypy 零错误"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L2_TEST_ROI["A:测试投入产出比"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L3_COCKPIT_COVERAGE["A:cockpit 功能覆盖率"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_L3_COCKPIT_LATENCY["A:cockpit 响应延迟 SLA"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_X_DEBT_SCORING["A:omo-debt 评分覆盖率"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_X_OBSERVABILITY["A:可观测性覆盖"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X3_X_SUBMODULE_FRESH["A:子模块新鲜度"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X4_ADR_LINKS["A:ADR 链接完整性"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X4_DOC_SSOT["A:文档 SSOT (markdown 禁硬编码项目元数据, 引用 project-registry)"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X4_HEALTH_SSOT["A:健康分 SSOT"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X4_MCPTOOL_IMPL_DRIFT["A:CR-X4-MCPTOOL-IMPL-DRIFT"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CR_X4_TEST_COVERAGE["A:测试覆盖检查"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_CS_10["A:CS-10"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_L0_YAML["A:L0_YAML"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_MCP["A:MCP"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_ARCH_MERGE_LLMGATEWAY_20260616["A:X1-ARCH-MERGE-LLMGATEWAY-20260616"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_AUD_COMMIT_LOOP["A:X1-AUD-COMMIT-LOOP"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_C01["A:X1-C01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_C02["A:X1-C02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_C03["A:X1-C03"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_CROSS_PROJECT_LINT_ENFORCE_20260620["A:X1-CROSS-PROJECT-LINT-ENFORCE-20260620"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_DEBT_EVIDENCE_CLOSURE_20260620["A:X1-DEBT-EVIDENCE-CLOSURE-20260620"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_OMNI_BUS_ROUTING_20260617["A:X1-OMNI-BUS-ROUTING-20260617"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_OMO_DIRECT_MUTATION_GATE_20260617["A:X1-OMO-DIRECT-MUTATION-GATE-20260617"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X1_OMO_GOVERNANCE_SURFACES_20260616["A:X1-OMO-GOVERNANCE-SURFACES-20260616"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_C01["A:X2-C01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_C02["A:X2-C02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_C03["A:X2-C03"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_C04["A:X2-C04"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_C05["A:X2-C05"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_ADR_DRIFT["A:X2-FRESH-ADR-DRIFT"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_ARCHIVED_LLMGATEWAY["A:X2-FRESH-ARCHIVED-LLMGATEWAY"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_COMMIT_FATIGUE["A:X2-FRESH-COMMIT-FATIGUE"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_CROSS_PROJECT_LINT["A:X2-FRESH-CROSS-PROJECT-LINT"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_DEBT_DASHBOARD["A:X2-FRESH-DEBT-DASHBOARD"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_DEBT_EVIDENCE_INTEGRITY["A:X2-FRESH-DEBT-EVIDENCE-INTEGRITY"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_DOC_LIFECYCLE["A:X2-FRESH-DOC-LIFECYCLE"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_EVIDENCE_ALIAS["A:X2-FRESH-EVIDENCE-ALIAS"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_GOV_DASHBOARD["A:X2-FRESH-GOV-DASHBOARD"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_MERGE_CHECKLIST["A:X2-FRESH-MERGE-CHECKLIST"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_MOF_VERSION_BUMP["A:X2-FRESH-MOF-VERSION-BUMP"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_NAV_DOC_REVIEW["A:X2-FRESH-NAV-DOC-REVIEW"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_OMO_GOVERNANCE_SURFACES["A:X2-FRESH-OMO-GOVERNANCE-SURFACES"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X2_FRESH_OMO_LINT_SIZE["A:X2-FRESH-OMO-LINT-SIZE"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X3_C01["A:X3-C01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X3_C02["A:X3-C02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X3_C03["A:X3-C03"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X4_C01["A:X4-C01"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X4_C02["A:X4-C02"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X4_CONS_DEBT_GITIGNORE_BOUNDARY["A:X4-CONS-DEBT-GITIGNORE-BOUNDARY"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X4_CONS_DRIFT_VS_GOVERNANCE["A:X4-CONS-DRIFT-VS-GOVERNANCE"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X4_CONS_LLMGATEWAY_ARCHIVED["A:X4-CONS-LLMGATEWAY-ARCHIVED"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X4_CONS_OMO_GOVERNANCE_SURFACES["A:X4-CONS-OMO-GOVERNANCE-SURFACES"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    A_X4_CONS_P43_CLOSED_LOOP_SSOT["A:X4-CONS-P43-CLOSED-LOOP-SSOT"]:::axiom -->|related_to| D_ADR_0106["ADR-0106"]
    J_aetherforge["J:Aetherforge"]:::project -->|member_of| C_Layer_X["C:Layer X"]:::concept
    J_agora["J:Agora"]:::project -->|member_of| C_Layer_I0["C:Layer I0"]:::concept
    J_bus_foundation["J:Bus Foundation"]:::project -->|member_of| C_Layer_X["C:Layer X"]:::concept
    J_c2g["J:C2G"]:::project -->|member_of| C_Layer_X["C:Layer X"]:::concept
    J_cockpit["J:Cockpit"]:::project -->|member_of| C_Layer_L3["C:Layer L3"]:::concept
    J_cockpit_ui["J:Cockpit Ui"]:::project -->|member_of| C_Layer_L3["C:Layer L3"]:::concept
    J_ecos["J:Ecos"]:::project -->|member_of| C_Layer_L0["C:Layer L0"]:::concept
    J_family_hub["J:Family Hub"]:::project -->|member_of| C_Layer_L2["C:Layer L2"]:::concept
    J_gbrain["J:Gbrain"]:::project -->|member_of| C_Layer_L2["C:Layer L2"]:::concept
    J_kairon["J:Kairon"]:::project -->|member_of| C_Layer_L2["C:Layer L2"]:::concept
    J_l4_kernel["J:L4 Kernel"]:::project -->|member_of| C_Layer_L4["C:Layer L4"]:::concept
    J_mesh_router["J:Mesh Router"]:::project -->|member_of| C_Layer_L0["C:Layer L0"]:::concept
    J_metaos["J:Metaos"]:::project -->|member_of| C_Layer_L2["C:Layer L2"]:::concept
    J_model_driven["J:Model Driven"]:::project -->|member_of| C_Layer_M0["C:Layer M0"]:::concept
    J_observability["J:Observability"]:::project -->|member_of| C_Layer_X["C:Layer X"]:::concept
    J_omo["J:Omo"]:::project -->|member_of| C_Layer_L2["C:Layer L2"]:::concept
    J_omo_debt["J:Omo Debt"]:::project -->|member_of| C_Layer_L2["C:Layer L2"]:::concept
    J_runtime["J:Runtime"]:::project -->|member_of| C_Layer_L1["C:Layer L1"]:::concept
    J_toolbox["J:Toolbox"]:::project -->|member_of| C_Layer_L1_L3["C:Layer L1-L3"]:::concept
    N_MBP_M5_Max["N:MBP M5 Max"]:::node -->|runs_model| C_Model_coder["C:Model coder"]:::concept
    N_MBP_M5_Max["N:MBP M5 Max"]:::node -->|runs_model| C_Model_embed_bge["C:Model embed-bge"]:::concept
    N_MBP_M5_Max["N:MBP M5 Max"]:::node -->|runs_model| C_Model_reasoner["C:Model reasoner"]:::concept
    N_MBP_M5_Max["N:MBP M5 Max"]:::node -->|runs_model| C_Model_vision["C:Model vision"]:::concept
    N_MBP_M5_Max["N:MBP M5 Max"]:::node -->|runs_model| C_Model_vision_lite["C:Model vision-lite"]:::concept
    N_Y7000P_4070["N:Y7000P 4070"]:::node -->|runs_model| C_Model_mid["C:Model mid"]:::concept
    N_Y7000P_4070["N:Y7000P 4070"]:::node -->|runs_model| C_Model_ocr["C:Model ocr"]:::concept
    N_Y7000P_4070["N:Y7000P 4070"]:::node -->|runs_model| C_Model_vision_lite["C:Model vision-lite"]:::concept
    N_mac_mini_M4["N:mac mini M4"]:::node -->|runs_model| C_Model_embed["C:Model embed"]:::concept
    N_mac_mini_M4["N:mac mini M4"]:::node -->|runs_model| C_Model_fast["C:Model fast"]:::concept
    N_mac_mini_M4["N:mac mini M4"]:::node -->|runs_model| C_Model_mini_9b["C:Model mini-9b"]:::concept
    N_mac_mini_M4["N:mac mini M4"]:::node -->|runs_model| C_Model_mini_chat["C:Model mini-chat"]:::concept
    N_mac_mini_M4["N:mac mini M4"]:::node -->|runs_model| C_Model_rerank["C:Model rerank"]:::concept
```

---
## 📊 实体指标统计
* **总实体数**: 216
* **总关系数**: 184