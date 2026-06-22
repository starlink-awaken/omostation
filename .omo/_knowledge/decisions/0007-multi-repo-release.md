---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# ADR-0007: 多仓库统一版本发布策略

- **Status**: ACCEPTED
- **Date**: 2026-06-07
- **Authors**: P34-W3-MULTI-REPO-RELEASE
- **Supersedes**: 各项目独立发版的临时状态

## Context and Problem Statement

omostation 6 项目 (agora / kairon / gbrain / omo / metaos / cockpit / runtime) 各自独立发版, 无统一机制. 出现:
- 版本号漂移 (kairon 0.1.0, omo 1.5.0, 难以协调)
- 变更追踪散落各项目 CHANGELOG
- 发布流程手工, 易错
- 跨项目升级无法原子化

## Decision Drivers

- 6 项目协调发版
- 版本号可追溯
- 发布流程自动化
- 减少手工错误
- 不打破 P30 决策的"逻辑单仓, 物理多仓"布局

## Considered Options

### A. 各项目独立发版 (现状)

- 优点: 项目自治, 各自可独立节奏
- 缺点: 协调难, 版本漂移, 跨项目无原子性

### B. monorepo 单版本

- 优点: 简单
- 缺点: 违反 P30 已建 6 项目布局, 物理合仓成本高

### C. (推荐) 6 项目共享 omostation-X.Y.Z 命名

- 工作区根 `VERSION` 文件权威
- 各项目 `__version__.py` 镜像 (运行时读 VERSION 文件)
- `scripts/release.sh` 一键 bump + 同步
- `CHANGELOG.md` 聚合 6 项目变更
- git push / tag 仍手工 (POC 阶段)

## Decision Outcome

**Chosen option: C**, because omostation 6 项目是"逻辑单仓, 物理多仓" (P30 决策), 共享语义版本符合"协调发版"目标, 同时不打破 P30 的物理布局.

### Consequences

- Good: 6 项目版本号统一 (`omostation-0.1.0` 等)
- Good: CHANGELOG 聚合, 变更一目了然
- Good: `release.sh` 自动化 bump, 减少手工
- Good: 各项目 `__version__.py` 运行时自动同步, 不需要硬编码
- Bad: 仍需手动 git push / tag (POC 阶段)
- Bad: 各项目 `__version__.py` 仍要维护镜像逻辑 (虽仅 8 行)

### Confirmation

- [x] `release.sh dry-run` 成功
- [x] `release.sh patch` 真跑成功 (0.1.0 → 0.1.1)
- [x] VERSION 文件权威
- [x] CHANGELOG.md 聚合 6 项目
- [x] 各项目 `__version__.py` 同步镜像
- [x] ruff 0 errors
- [x] audit 100 (A+)
- [x] 单元测试 ≥ 3 通过

## Notes

- POC 阶段: release.sh 不打 tag / 不 push, 由人工 git 操作
- 后续 Phase 可考虑: 集成 gh CLI 自动发版
- 6 项目布局 = agora (L0) + kairon (L2) + gbrain (L2) + omo (L2) + metaos (L2) + cockpit (L3) + runtime (L1)
