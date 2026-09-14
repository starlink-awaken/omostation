---
id: ADR-0242
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last-reviewed: 2026-07-26
related:
  - 0238-mof-m4-phase0-registry-self-governance.md
  - .omo/plans/metaos-governance-batch-workorder.md
supersedes: []
amends: []
type: ssot
---

# ADR-0242: metaos registry drift 门扩展 (§J1, 承接 ADR-0238)

## Context

metaos 治理批工单 (`.omo/plans/metaos-governance-batch-workorder.md`) §J 判断:
MOF (ADR-0238) 与 metaos 两份方案独立诊断出同一病 — 声明/执行鸿沟 (P73
decl-exec-gap). 逐项目修是打地鼠, 真正高杠杆是**一扇门覆盖所有子项目**.

§J1 要求: 扩展 ADR-0238 已建的 `check-mof-capabilities-drift.py` 覆盖 metaos
registry (projects-capabilities 死条目 / phase-scope 死路径 / submodule_policy
分支名 / entrypoint 可达性). **严禁新建第二套门禁框架**.

独立核实漂移活样本:
- `projects-capabilities.yaml` `kairon.metaos` entrypoint 指向
  `projects/kairon/packages/metaos` (已删, metaos 2026-06-06 拆到 projects/metaos)
- 全量扫出 **44 个死条目** (kairon.*/agentmesh.*/gbrain.*/sharedbrain.*/cli.*),
  projects-capabilities.yaml 整体 stale

## Decision

**§J1: 扩展 `check-mof-capabilities-drift.py` 加 metaos 面** (不新建门):

新增 metaos 面 (`CR-X4-METAOS-REGISTRY-DRIFT`) 三类检查:
1. `check_projects_capabilities_entrypoints` — projects-capabilities.yaml 每个
   capability entrypoint 存在性 (死条目检出, 通用扫所有 capability 非仅 metaos)
2. `check_metaos_cli_entrypoint` — metaos INTERFACE.yaml cli module
   (metaos.cli:main) → src 文件可达性
3. `check_metaos_submodule_present` — metaos submodule 目录存在性
   (.gitmodules 无 branch 声明, 改查目录可达)

API 设计:
- `detect_drift()` (MOF, ADR-0238) **保持向后兼容** — 现有测试断言此函数 0 drift 不受影响
- 新增 `detect_metaos_registry_drift()` + `detect_all_drift()` (聚合两面)
- main() 加 `--scope {mof,metaos,all}` (默认 all 聚合)
- 纯函数 `check_*` 接受参数, 便于注入测试 (与 ADR-0238 一致)

暂不纳入 (避免误报):
- **phase-scope 路径**: phase3 预留阶段 (unlocked=false) 路径未建是预期,
  报为漂移会误报. 待 phase verdict 语义成熟后扩展.
- **submodule 分支名**: .gitmodules 无 branch 声明, 无可比基准, 改查目录存在性.

注册 SSOT: agent-workflows.yaml diff_checks 加 `metaos-registry-drift`
(required:false, CI-only) + `metaos-registry-drift-tests`.

## Confirmation

- `check-mof-capabilities-drift.py --scope mof`: 0 drift (向后兼容) ✅
- `--scope metaos`: 44 drift, 含 kairon.metaos 死条目 (活体验收) ✅
- `tests/test_mof_capabilities_drift.py`: **16 passed** (ADR-0238 原 7 + §J1 新 9:
  注入检出 6 + 结构 1 + 现实 kairon.metaos 活体 1 + 聚合 1) ✅
- `agent-workflow lint`: PASS (diff_checks 注册合法) ✅
- ruff: 干净 ✅

## 红线遵守

- **严禁新建第二套门禁框架**: 扩展 check-mof-capabilities-drift.py 同一脚本,
  非新建门 ✅
- 未碰 .omo AST 禁写红线 (只编辑 registry yaml + 新建 ADR) ✅
- 未加回 metaos 独立 MCP 入口 (ADR-0181) ✅
- claim-before-write (G-CONV.7/ADR-0220): bin/mof 脚本 + tests + agent-workflows.yaml
  + 本 ADR 均 claim 到 a408c2f1 run 后再写. 首次 Edit 未 claim 被还原 (PostToolUse
  hook restore 到 git HEAD), claim 后解决 ✅

## 已知债务 (待 §F / D 决策, 不在 Phase 0 建门范围)

`projects-capabilities.yaml` **44 个死条目** (projects/agentmesh, projects/SharedBrain
等已删项目 + kairon/packages/* 拆迁遗留). 消费者: `projects/omo/src/omo_governance_surfaces*`.
修复需 D 决策:
- D-cap-a: 重生 projects-capabilities.yaml (找/建 generator 重扫 projects/)
- D-cap-b: 退役无消费者的死条目 (按消费实证删)
门已能检出 (required:false 报红告警), 不阻塞. 修复后 `test_detect_metaos_known_kairon_drift`
应删除 (维护契约见测试注释).

## Status

**ACCEPTED** for metaos registry drift 门扩展 (§J1, 2026-07-26). Phase 0 §J1 完成.
D1-D4 决策卡另送 BRIEF Inbox, 不在本 ADR 范围.
