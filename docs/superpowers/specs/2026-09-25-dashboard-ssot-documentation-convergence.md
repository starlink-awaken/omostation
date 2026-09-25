---
status: active
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
title: "Spec: Dashboard SSOT Documentation and Architecture Convergence (BET-Y2Q2-T10-166)"
---
# Spec: Dashboard SSOT Documentation and Architecture Convergence (BET-Y2Q2-T10-166)

## 1. 概述与设计意图 (Overview & Intent)
在完成 Cockpit-UI 治理全景控制舱（`/panorama`）的构建、四大核心资产模块化、全局导航与命令面板集成、无障碍测试矩阵以及端口导流守护后，本规范对全体系的 SSOT 协议文档、端口注册表与架构规范进行终极锚定。

彻底收敛历史混乱的“三套入口”表述，正式在 SSOT 文档层面确立：
**Cockpit-UI (`:5173` / `:8090`，`/panorama`) 是 omostation 唯一的人类主控总视窗。**

## 2. 核心文档改动清单 (SSOT Modifications)

### 2.1 `docs/DASHBOARDS.md`
- 入口表格更新：
  - `Cockpit-UI (/panorama)`：**单一人类主控入口**（Single Sovereign Human Console），代码受控于 `projects/cockpit-ui`。
  - `:43191` (知行底座) & `:43910` (Panorama 静态页)：**已完成收敛并下线 (Sunset & Converged)**，通过 Sunset Redirector 302 导流至 Cockpit-UI。
- 历史风险闭环：
  - 声明原“`:43191` 部署目录不受版本控制”的根本风险已通过全量迁入 `projects/cockpit-ui` 彻底根除。

### 2.2 `protocols/port-registry.yaml`
- 端口状态调整：
  - `43191`: 状态更新为 `converged`，标注重定向至 `http://localhost:5173/panorama`。
  - 补充 `43910` 导流记录。

### 2.3 `docs/PANORAMA-DASHBOARD.md`
- 架构图与使用说明更新，指向原生 `/panorama`。

## 3. 验收标准 (Acceptance Criteria)
1. `docs/DASHBOARDS.md` 准确反映单一人类主入口现状；
2. `protocols/port-registry.yaml` 完成端口状态对齐；
3. `make gac-local-gate` 治理门禁全部通过。
