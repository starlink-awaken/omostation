---
name: architecture-perception
description: Agent 感知当前架构状态，检查架构合规性
triggers:
  - 用户询问架构相关问题
  - 创建/修改场景卡时
  - 新增 bin/ 脚本时
  - 架构变更时
type: ssot
owner: agent-skills-team
last_updated: 2026-09-03
---

# Skill: architecture-perception

让 Agent 感知当前架构状态，确保架构合规。

## 触发条件

- 用户询问架构相关问题
- 创建/修改场景卡时
- 新增 bin/ 脚本时
- 架构变更时
- PR 提交前

## 执行步骤

### 1. 读取架构标准

```bash
cat .omo/standards/scene-card-lifecycle.yaml
cat .omo/standards/business-domains.yaml
cat .omo/standards/dimension-system.yaml
cat .omo/standards/value-loop-standard.yaml
cat .omo/standards/architecture-ssot-index.yaml
```

### 2. 检查当前变更合规性

```bash
# 快速架构检查
python3 bin/gac/architecture-check.py --quick

# 场景卡生命周期检查
uv run --with pyyaml python "bin/ssot/scene-card-lifecycle.py" validate --all

# 维度健康度报告
python3 bin/gac/dimension-health.py --report
```

### 3. 如不符合，给出修正建议

- 场景卡缺少 domain 字段 → 添加 domain: work|health|research|knowledge|governance
- 场景卡生命周期跳级 → 补充中间级别的 promotion_evidence
- 新增脚本未归档 → 归档一个旧脚本平衡配额

### 4. 运行全量检查

```bash
make architecture-check
```

## 架构标准摘要

### 场景卡生命周期 (5 级)
```
draft → shadow → assisted → supervised → routine
```

### 业务域 (5 域)
- work: 公文、文档、会议、项目
- health: 个人与家庭健康
- research: 调研与学术
- knowledge: 知识沉淀与学习
- governance: 系统治理与合规

### 维度系统 (12 维度)
- 治理维 (4): X1审计 / X2保鲜 / X3价值 / X4一致性
- 业务维 (7): 场景 / 功能 / 旅程 / 体验 / 愿景 / 运营 / 运维
- 新增维 (2): 防腐 / 约束 / 进化 / 信任

### 价值循环 (5 阶段)
信号感知 → 信号分类 → 旅程执行 → 价值记录 → 进化反馈

## 相关文件

- 标准目录: `.omo/standards/`
- 场景卡: `docs/scene-cards/`
- Journey: `docs/journey-specs/`
- 注册表: `.omo/_truth/registry/`
