---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 4.A — 文档体系补齐

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Phase 3 gate) | 预估: 1h

## 一、目标

将 README.md 从项目目录索引改造为使用指南，新用户读完知道输入 `workspace demo`。

## 二、范围

| 文件 | 当前状态 | 目标 |
|------|---------|------|
| `README.md` | 项目列表索引 | 使用指南：demo → research → status |
| `workspace help` | 不存在 | 列出所有活跃项目 + 用途 + 入口命令 |
| `agora/docs/API_REFERENCE.md` | 可能过时 | 反映 v1.5 实际 API |

## 三、验收标准

```
☐ README.md 第一段 = "Workspace 是一套本地优先的知识工程系统。从研究到保存，帮你完成知识工作的完整闭环。"
☐ README.md 包含 "快速开始：workspace demo"
☐ README.md 包含 3 条用户路径：研究 / 系统状态 / 了解更多
☐ workspace help 输出所有项目 + 一句话用途
```

## 四、输出

| 文件 | 操作 |
|------|------|
| `README.md` | 重写 |
| `workspace/cli.py` | 添加 help 子命令 |
| `agora/docs/API_REFERENCE.md` | 更新 |
| `.omo/TASK_POOL.md` | T054-T056 → done |
