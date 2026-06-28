# omo_audit 7 检查 → GaC 规则映射表

> 最后更新: 2026-06-28 (Phase 4 孤儿规则补全)
> omo_audit.py `run_governance_audit()` 跑 7 项检查, 每项检查覆盖的 GaC 规则 ID 如下。

| # | 检查函数 | 检查内容 | 覆盖的 GaC 规则 ID | GaC check_type |
|---|---------|---------|-------------------|---------------|
| 1 | `governance_check_lint()` | ruff check kairon packages, 统计 error 数 | X1-CROSS-PROJECT-LINT-ENFORCE-20260620 | lint_enforce (待注册) |
| 2 | `governance_check_test_coverage()` | 每个非归档包至少 1 个 test_*.py | CR-X4-TEST-COVERAGE (Phase 4 补全) | test_coverage |
| 3 | `governance_check_debt_integrity()` | .omo/debt/items/ 中 lifecycle_state=resolved 的项是否有 resolution_evidence | X1-DEBT-EVIDENCE-CLOSURE-20260620, CR-X3-DEBT-TIER | audit_chain, value_roi |
| 4 | `governance_check_adr_links()` | ADR INDEX.md 引用的所有 ADR 都存在 | CR-X4-ADR-LINKS (Phase 4 补全) | doc_lifecycle |
| 5 | `governance_check_task_consistency()` | status=completed 的任务, deliverables 路径必须存在 | CR-L2-TASK-DELIVERABLE | task_field |
| 6 | `governance_check_agora_health()` | agora 路由 → 服务真实可达率 (>=80% = 满分) | CR-L0-BOS-RESOLVE, CR-L1-RUNTIME-HEALTH | bos_resolve |
| 7 | `governance_check_doc_lifecycle()` | .omo/ 文档生命周期健康度 (frontmatter + 分类 + 引用) | CR-X4-DOC-SSOT, CR-X4-HEALTH-SSOT | doc_lifecycle, ssot_pointer |

## 孤儿检查补全 (Phase 4)

原 2 个孤儿检查已在 Phase 4 补全 GaC 规则:

| 检查 | 补全规则 | target | executor |
|------|---------|--------|----------|
| `governance_check_test_coverage()` | CR-X4-TEST-COVERAGE | kairon/packages/*/tests/ | omo_audit, ci_gate |
| `governance_check_adr_links()` | CR-X4-ADR-LINKS | .omo/_knowledge/decisions/ | omo_audit, ci_gate |

## 关系

- GaC `executor: [omo_audit]` 声明 → `run_governance_audit()` 是执行入口
- 本映射表是 **声明性文档**, 不替代代码中的实际检查逻辑
- `gac-drift.py` 验证 indexed 规则的 source_ref 文件存在 + ID 匹配 + M1 实例存在 (Phase 4B)
- `gac-m1-sync.py` 维护 registry↔M1 实例同步 (机制 7 完整闭环)
- 未来可通过 `gac-executor.py` 实现逐规则 dispatch (当前 omo_audit 是 monolithic executor)
