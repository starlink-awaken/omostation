---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
bet: BET-Y1Q4-T8-11
title: 8大正交一级领域树与双轨无感知兼容路由器
symptom: 存量 130+ 命令扁平无序，认知负荷过高；缺乏体系化分层
solution: ORTHOGONAL_DOMAINS 8 域模型 + 双轨透明预处理分发
---

# BET-Y1Q4-T8-11 复盘

## 做对了什么

1. **双轨无感知分发**：`cockpit system dashboard` 与 `cockpit dashboard` 双向等价分发，全仓自动化与 Agent 脚本 100% 零破坏兼容。
2. **挂载原生子解析树**：通过 `_subcommands.py` 为 8 大正交一级领域挂载完整子解析器，支持 `cockpit <domain>` 打印富文本领域功能地图与子命令表格。
3. **自动化测试守底**：`test_command_hierarchy.py` 完整覆盖 8 大领域定义、别名分发与帮助提示。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| REMAINDER 参数将子命令参数全量截留导致 flags 丢失 | 预处理识别全局通用 flags 并进行层级同步 |
| 存量命令调用示例缺少正交域前缀提示 | 在领域 help 表格中补充双轨调用映射提示 |

## 交付自证

- 映射与分发测试：`uv run --project projects/cockpit pytest projects/cockpit/tests/test_command_hierarchy.py` (ALL PASS)
- 门禁状态：`make gac-local-gate` 56 项全绿通过。
