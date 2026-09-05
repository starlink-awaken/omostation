---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
bet: BET-Y1Q4-T8-12
title: 全局行为契约与 ExitCode/Trace-ID/机器纯净度规范
symptom: 退出码随意、JSON 输出混带 ANSI 终端彩色转义字符、缺少分布式链路追踪
solution: ExitCode IntEnum 体系 + ANSI 拦截 + Trace-ID 贯穿日志
type: ephemeral
status: archived
---

# BET-Y1Q4-T8-12 复盘

## 做对了什么

1. **退出码语义规范**：标准化 `ExitCode.SUCCESS (0)` 至 `UPSTREAM_ERROR (5)` 枚举，错误时返回准确的状态码。
2. **机器纯净度保证**：在 `error()` 与 `output_result` 强制拦截 Rich ANSI 控制字符，保证 `--json` 输出始终为纯净 JSON。
3. **Trace-ID 全链路贯穿**：通过 `logger.py` 与环境变量/全局选项注入 Trace-ID，支持链路级诊断。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| 解析器遇到无效子命令时 Rich Console 直接打印 ANSI 污染 JSON | 在 WorkspaceParser.error() 提前判断 `--json` 标志并拦截输出纯 JSON |
| sys.exit(2) 被上层异常捕获吞噬 | 规范异常拦截与 ExitCode 映射逻辑 |

## 交付自证

- 测试覆盖：`uv run --project projects/cockpit pytest projects/cockpit/tests/test_universal_flags.py` (ALL PASS)
- 门禁状态：`make gac-local-gate` 56 项全绿通过。
