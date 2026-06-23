---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# Product UX Redesign — Workspace CLI + Dashboard

> 从产品视角重新设计 workspace CLI 的终端用户体验。
> 目标：不是修修补补，而是把用户操作体验做到产品级。

## TL;DR

- **核心改动**：用 `rich` 库重写 workspace CLI 输出（颜色/表格/面板/进度条）
- **交付物**：新的 `workspace/cli.py` + `workspace/storage.py`（已有）
- **验收标准**：每条命令的输出可截图、可分享、一眼能看懂
- **影响范围**：workspace CLI 5 条子命令

---

## 当前问题

| 问题 | 用户感受 |
|------|---------|
| 纯黑白文本 | 无法区分信息层级 |
| 表格用空格排列 | 列不对齐，宽终端溢出 |
| 无进度反馈 | 研究任务在 30 秒黑屏后突然完成 |
| 错误信息枯燥 | 看不出是警告还是致命 |
| 无视觉分区 | 所有输出混在一起 |

## 设计标准

- **颜色语义**：green=成功, yellow=警告, red=错误, cyan=可操作, dim=辅助信息
- **表格**：rich.Table + rounded box
- **面板**：rich.Panel 包装关键输出
- **进度**：rich.Progress (Spinner + Bar + TimeElapsed)
- **错误**：rich.Console(stderr=True) + red 高亮

## 具体改动

### 1. `cmd_research` — 研究执行
**当前**：print + `▶` 步骤
**目标**：Progress spinner → Panel 包装结果 → Markdown 渲染输出
**结果**：用户看到动态进度条，完成后一个绿框面板展示摘要

### 2. `cmd_research_list` — 研究列表
**当前**：纯文本对齐
**目标**：rich.Table 渲染，列对齐，追问计数标记
**结果**：整表 screenshot-ready

### 3. `cmd_research_open` — 研究详情
**当前**：`===` 分隔线 + 纯文本
**目标**：Panel + Markdown 渲染 + 追问子表
**结果**：研究全文可读性大幅提升

### 4. `cmd_status` — 系统状态
**当前**：print 对齐
**目标**：rich.Table 服务状态表 + 研究列表
**结果**：一眼看出系统健康度

### 5. `cmd_demo` — 快速开始
**当前**：print 文本
**目标**：Progress 分步 + Panel 包装结果
**结果**：新用户演示有节奏感

## 依赖

- `rich` — 终端 UI 框架（pip install rich）
- `storage.py` — 不变，已有 SQLite 持久化

## 执行

委托 Sisyphus-Junior 执行 `/Users/xiamingxing/Workspace/.omo/plans/product-ux-redesign.md`
