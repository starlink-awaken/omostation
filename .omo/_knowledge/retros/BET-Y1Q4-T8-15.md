---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
bet: BET-Y1Q4-T8-15
title: CLI 亚百毫秒极致冷启动加速与高频 BOS 传输优化
symptom: 基础查询命令冷启动耗时超 360ms，130+ 解析器顶层贪婪加载拖慢终端体验
solution: Fast-path 直通路径 + 全局 Flags 级联 + 全域 Lazy Import
type: ephemeral
status: archived
---

# BET-Y1Q4-T8-15 复盘

## 做对了什么

1. **Fast-path 极速响应**：针对高频轻量参数（如 `--version`, `-V`），在构建 130+ 复杂解析器前建立快速分发通道，响应耗时从 ~360ms 骤降至 ~40ms。
2. **延迟按需导入**：所有具体命令实现与重型依赖均封装在 `dispatch_*` 内部 Lazy Import，顶层解析零模块开销。
3. **全局参数级联**：自动识别 REMAINDER 参数中的 `--json`, `--dry-run`, `-q`, `-v`，保证参数精准穿透。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| `cockpit --version` 原先会触发全部子解析器加载与 banner 渲染 | 在 main() 首部实现极速直通返回 |

## 交付自证

- 性能实测：`time uv run --project projects/cockpit cockpit --version` 约 0.05s。
- 门禁状态：`make gac-local-gate` 56 项全绿通过。
