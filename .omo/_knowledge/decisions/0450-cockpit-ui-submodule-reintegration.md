---
id: ADR-0450
status: accepted
lifecycle: contract
owner: xiamingxing
last-reviewed: 2026-09-04
type: ssot
---

# ADR-0450: cockpit-ui 以 submodule 形态回归主仓

## 背景

- BET-Y1Q4-T8-02 期间 PWA 前端曾直接跟踪于主仓 `projects/cockpit-ui`（dist 强制入库）。
- 后被 untrack 迁往独立仓 `starlink-awaken/omostation-cockpit-ui`（commit 654a8bb38，**未留 ADR——治理缺口**）。
- 迁移后主仓对其失去版本锚定与治理感知：前端（T8-04 work-case 高频迭代）与 cockpit 子仓 API 的兼容组合无 gitlink 依据；omo-status / 台账 / doc-index 对前端全盲。
- untrack 残留（空壳目录、.gitmodules 死注册）曾致 CI 11 项全红（见 PR #3048 修复链）。

## 决策

cockpit-ui 以 **git submodule** 挂载回归 `projects/cockpit-ui`，成为主仓第 15 个子模块。独立仓保持独立开发与发布节奏，主仓 gitlink 仅做版本锚定。

## 理由

1. **版本锚定**：前端 × cockpit 后端（mobile_api / work-case API）组合演进有 gitlink 依据。
2. **CI 组合覆盖**：主仓 20 项检查矩阵可测"后端 + 前端某 commit"组合。
3. **治理感知**：PASW 可达性、sync-submodule-pointers、doc-index 等既有机制自动覆盖。
4. **架构一致**：对齐 14 子模块舰队模式，基建零新增。
5. node_modules/dist 顾虑不成立：submodule 内部 ignore 由子仓自治；独立仓 dist 入库策略使 `check-cockpit-ui-dist` 零改动通过。

## 影响

- `submodule-reachability-gate`: 14 → **15 gitlinks**。
- `.github/workflows/cockpit-ui-ci.yml` 复活（presence guard + gitlink 路径精确触发）。
- `.gitignore` 移除 untrack 期残留的 `projects/cockpit-ui` 忽略行。

## 非目标

- 不回收独立仓的开发节奏与自主 CI。
- 不在主仓重复跟踪前端构建产物（dist 由子仓管理）。
