# 归档测试说明

## 归档原因

以下测试文件于 2026-06-03 归档，因为它们引用的 Phase 1–14 计划文档已迁移至 `plans/archive/`。

## 归档文件列表

| 文件 | 原引用 | 归档原因 |
|------|--------|----------|
| test_phase4_kickoff_docs.py | `plans/phase4-execution-roadmap.md` | 计划已归档 |
| test_phase5_completion_docs.py | `plans/phase5-wave{1,2,3}-execution-plan.md` | 计划已归档 |
| test_phase5_wave0_docs.py | `plans/phase5-wave0-{execution,task}-specs.md` | 计划已归档 |
| test_phase6_completion_docs.py | `plans/phase6-{program,wave*}.md` | 计划已归档 |
| test_phase6_ratification_docs.py | `plans/phase6-{program,wave*}.md` | 计划已归档 |
| test_phase7_completion_docs.py | `plans/phase7-{program,wave*}.md` | 计划已归档 |
| test_phase7_planning_gate_docs.py | `plans/phase7-{planning-gate,program,starter}.md` | 计划已归档 |
| test_phase8_completion_docs.py | `plans/phase8-wave3-execution-plan.md` | 计划已归档 |
| test_phase8_planning_gate_docs.py | `plans/phase8-{planning-gate,program,starter}.md` | 计划已归档 |
| test_phase8_wave2_closeout_docs.py | `plans/phase8-wave2-execution-plan.md` | 计划已归档 |
| test_phase9_completion_docs.py | `plans/phase9-{program,wave4}.md` | 计划已归档 |
| test_phase9_workspace_plane_refactor_docs.py | `plans/phase9-{program,workspace-plane}.md` | 计划已归档 |
| test_phase10_completion_docs.py | `plans/phase10-{program,wave4}.md` | 计划已归档 |
| test_phase10_kickoff_docs.py | `plans/phase10-{program,wave1}.md` | 计划已归档 |
| test_phase10_wave2_docs.py | `plans/phase10-wave2-execution-plan.md` | 计划已归档 |
| test_phase10_wave3_docs.py | `plans/phase10-wave3-execution-plan.md` | 计划已归档 |
| test_phase11_kickoff_docs.py | `plans/phase11-{program,wave1}.md` | 计划已归档 |
| test_phase11_wave1_ssot.py | `plans/phase11-wave1-execution-plan.md` | 计划已归档 |
| test_phase11_wave2_docs.py | `plans/phase11-{program,wave2}.md` | 计划已归档 |
| test_phase11_wave3_docs.py | `plans/phase11-wave3-execution-plan.md` | 计划已归档 |
| test_phase11_wave4_docs.py | `plans/phase11-{program,wave4}.md` | 计划已归档 |
| test_phase12_13_planning_docs.py | `plans/phase11-wave4, phase12-{planning-gate,program,wave3-5}, phase13-metacognition, phase14-backlog.md` | 计划已归档 |
| test_phase12_execution.py | `plans/phase12-p0-pilot-adr.md` | 计划已归档 |
| test_phase13_execution.py | `plans/phase13-metacognition-preplanning.md` | 计划已归档 |
| test_phase14_execution.py | `plans/phase14-{program,deferred-ecosystem-backlog}.md` | 计划已归档 |

## 当前活跃测试

Phase 15+ 的测试文件仍保留在 `tests/` 根目录：

- `test_phase15_execution.py`
- `test_phase16_execution.py`
- `test_architecture_baseline_phase15_phase16.py`
- 以及其他不依赖已归档计划文件的通用治理测试

## 恢复方法

如需恢复这些测试，请将对应的计划文档从 `plans/archive/` 移回 `plans/` 根目录，再将测试文件从 `tests/archive/` 移回 `tests/` 根目录。
