---
type: ssot
name: harness-compliance
description: Harness 全生命周期合规检查 — 12 章节完整性 + MOF 约束联动 + OMO 状态同步
triggers:
  - 用户询问 Harness 合规状态
  - 修改 harness-policy.yaml 时
  - 新增 bin/gac/harness*.py 脚本时
  - 编辑 MOF 相关文件时
  - PR 提交前
  - CI 失败排查时
owner: governance-team
last_updated: 2026-09-04
---

# Skill: harness-compliance

Harness 作为唯一 S 槽位收束点，全生命周期合规检查。

## 触发条件

- 用户询问 Harness 合规状态
- 修改 `.omo/_truth/registry/harness-policy.yaml` 时
- 新增/修改 `bin/gac/harness*.py` 脚本时
- 编辑 MOF 相关文件 (`projects/ecos/src/ecos/ssot/mof/`) 时
- PR 提交前（自动触发）
- CI 失败排查时

## 执行步骤

### 1. 运行 Harness 合规检查

```bash
# 全量检查 (12 章节 + SFOP + 维度 + 探针 + 价值循环 + 已知债 + 实现率 + 防腐)
python3 bin/gac/harness-compliance-check.py --report

# 严格模式 (warning 也 fail)
python3 bin/gac/harness-compliance-check.py --strict
```

### 2. 运行 MOF 约束联动检查

```bash
# 全量 MOF 检查 (8 条 Agent-MOF 规则)
python3 bin/gac/harness-mof-bridge.py

# 仅影响分析 + 状态转换
python3 bin/gac/harness-mof-bridge.py --impact

# 仅 schema 校验 + 命名规范
python3 bin/gac/harness-mof-bridge.py --schema
```

### 3. 运行 OMO 状态同步检查

```bash
# 全量同步检查 (Harness + GaC + 漂移 + 已知债)
python3 bin/gac/harness-omo-bridge.py

# 仅 Harness 状态同步
python3 bin/gac/harness-omo-bridge.py --status

# 仅 GaC 规则同步
python3 bin/gac/harness-omo-bridge.py --gac
```

### 4. 运行统一约束与驱动

```bash
# CI 模式 (全量 4 引擎)
python3 bin/gac/harness-constraint-enforcer.py --ci

# 编辑前模式
python3 bin/gac/harness-constraint-enforcer.py --pre-edit

# 提交前模式
python3 bin/gac/harness-constraint-enforcer.py --pre-commit

# Push 前模式
python3 bin/gac/harness-constraint-enforcer.py --pre-push
```

## 检查项清单

### 12 章节完整性
- [ ] admission — 起跑前准入
- [ ] spec — 带指标的契约
- [ ] execution — Step 级护栏
- [ ] verify — DAG 编排 + 缓存
- [ ] audit — 设计期推演 + 静态校验
- [ ] accept — 分级验收
- [ ] probes — 7 类 Event 标准化
- [ ] dimensions — 12 维度全量挂载
- [ ] value_loop — 5 阶段价值循环
- [ ] known_debt — 已知债与逃生收口
- [ ] observability — 可观测
- [ ] rollout — 分阶段落地

### SFOP S 槽位
- [ ] harness.sfop_slot == "S"
- [ ] harness.controller == "COMP-WS-omo"

### 12 维度挂载
- [ ] X1_audit, X2_freshness, X3_value, X4_consistency
- [ ] scene, function, journey, experience, vision, operation, ops
- [ ] anticorrosion, constraint, evolution, trust

### 7 类 Probe
- [ ] arch_upgrade, feature_add, bug_fix, experience
- [ ] doc_governance, toolchain, business_process

## 修复指南

| 问题 | 修复方案 |
|------|----------|
| 缺少章节 | 在 harness-policy.yaml 中添加对应章节 |
| SFOP 槽位错误 | 修正 sfop_slot 为 S，controller 为 COMP-WS-omo |
| 维度缺失 | 在 dimensions 节点下添加对应维度 |
| MOF 约束失败 | 运行 `harness-mof-bridge.py --impact` 定位问题 |
| OMO 同步失败 | 检查 system.yaml 和 governance-data.json 可写 |
| 实现率不足 | 确保 harness entry 指向的脚本存在且调用 agent-workflow |

## MCP 工具映射

| MCP Tool | 功能 | 调用方式 |
|----------|------|----------|
| harness_compliance_check | 12 章节合规检查 | `{"mode": "full"}` |
| harness_status | 合规状态总览 | `{}` |
| harness_run | 8 阶段 DAG 运行 | `{"bet_id": "...", "profile": "..."}` |
| harness_verify | 并行校验 | `{}` |
| harness_probe | 7 探针 + Event Bus | `{}` |

## BOS URI 路由

| BOS URI | 功能 |
|---------|------|
| bos://harness/compliance/check | 12 章节合规检查 |
| bos://harness/mof/bridge | MOF 约束联动 |
| bos://harness/omo/bridge | OMO 状态同步 |
| bos://harness/constraint/enforce | 统一约束驱动 |
| bos://harness/architecture/perceive | 架构感知预编辑 |
| bos://harness/compliance/full | 全量合规检查 |
| bos://harness/run | 8 阶段 DAG 运行 |
| bos://harness/verify | 并行校验 |
| bos://harness/probe | 7 探针 + Event Bus |

## 相关文件

- 策略 SSOT: `.omo/_truth/registry/harness-policy.yaml`
- 感知注册中心: `.omo/_truth/registry/architecture-perception-registry.yaml`
- 架构标准: `.omo/standards/` (6 份)
- GaC 规则: `.omo/_truth/registry/governance-checks.yaml`
- MOF 约束: `.omo/standards/mof-agent-constraints.yaml`
