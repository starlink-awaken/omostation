---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: plan-phase32-governance.md
deprecated-since: 2026-06-23

---

# Phase 32 — 项目治理与版本策略 (Project Governance & Versioning)

> **状态**: 🟡 部分完成
> 已实现: kairon-governance 6 模块 (P29-W2, P30-W1-GOV-MERGE 迁 omo)
> 待做: 多仓库统一版本发布 (P32)

> 目标: 建立版本发布策略 + 代码冻结管理机制 + 多仓库协调规范
> 优先级: P2 | 预估: 1-2 周
> 依赖: Phase 29-31 可选择并行

---

## 一、需求分析

### 1.1 问题陈述

当前项目治理处于"全人工判断"状态：

| 治理缺口 | 现状 | 风险 |
|---------|------|------|
| 代码冻结无例外管理 | code_freeze=true 但修复/迭代无法区分 | 冻结形同虚设 |
| 无版本发布策略 | 各包版本号各自为政 | 无法做依赖管理和回滚 |
| 单点故障 | 所有架构决策依赖一人 | 效率瓶颈 + 知识孤岛 |
| 无变更日志 | 各项目无统一 CHANGELOG | 无法追踪演进历史 |
| scripts/ 子模块未标准化 | 独立 git 但未注册 submodule | CI 中可能无脚本 |

### 1.2 用户故事

- **作为项目维护者**，我想知道某个包当前是否是稳定版本，能否用于生产
- **作为治理系统**，我想让 code_freeze=true 时有明确的"修复例外"标记
- **作为新加入者**，我想在 CHANGELOG 中看到近期变更
- **作为 CI 系统**，我想可靠地检出所有子仓库

### 1.3 验收标准

- [ ] 建立版本命名规范: `vYYYY.MM.PATCH`（所有项目统一）
- [ ] 根仓库 `.gitmodules` 注册 scripts/ 为正式子模块
- [ ] code_freeze 状态机: 冻结 → 修复例外审批 → 解除冻结
- [ ] CHANGELOG 模板创建

---

## 二、实施计划

### Wave 1: 子模块标准化 (1h)
- [ ] 正式注册 scripts/ 为 git submodule
  ```bash
  git submodule add git@github.com:.../scripts.git scripts
  ```
- [ ] 验证 CI 中可正确检出子模块
- [ ] 输出: `.gitmodules` 文件

### Wave 2: 版本规范 (2h)
- [ ] 统一版本号格式: `vYYYY.MM.PATCH` (如 v2026.06.1)
- [ ] 更新各项目 `pyproject.toml` / `package.json` 为主版本号
- [ ] 自动生成 CHANGELOG: git log 按 Conventional Commits 分类
- [ ] 输出: CHANGELOG.md (各项目根目录)

### Wave 3: 冻结管理机制 (1h)
- [ ] 在 `.omo/state/system.yaml` 增加 `freeze_exceptions` 字段
- [ ] 冻结例外格式:
  ```yaml
  code_freeze: true
  freeze_exceptions:
    - id: "P0-AGENTRT_CRITICAL"
      type: "bugfix"
      approved_at: "2026-06-06"
      expires_at: "2026-06-13"
  ```
- [ ] omo-cli 支持 `omo freeze exception add/remove/list`

---

## 三、参考

- 当前冻结: `.omo/state/system.yaml`
- 版本: kairon `pyproject.toml`, gbrain `package.json`, runtime `pyproject.toml`
- 提交规范: `CONTRIBUTING.md` (Conventional Commits)
