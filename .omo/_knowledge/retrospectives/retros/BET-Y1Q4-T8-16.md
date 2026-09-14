---
schema_version: retro/v1
status: active
lifecycle: history
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
bet: BET-Y1Q4-T8-16
title: 顶级开源 DX：Shell 自动补全、交互纠错与统一使用手册
symptom: 缺乏原生 Shell 自动补全脚本，拼写错误时无法提供建议，缺乏完整的单源 CLI 参考手册
solution: 原生 completion (bash/zsh/fish) + Levenshtein 纠错建议引擎 + docs export (docs/CLI-REFERENCE.md)
type: ephemeral
status: archived
---

# BET-Y1Q4-T8-16 复盘

## 做对了什么

1. **三端 Shell 原生补全**：实现 `cockpit completion [bash|zsh|fish]`，动态补全 8 大正交一级领域、二级子命令与全局 Flags。
2. **Did You Mean 智能纠错**：自研零第三方依赖的 Levenshtein 模糊匹配算法，TTY 模式高亮建议，`--json` 模式返回 `"suggestions": [...]`。
3. **单源参考手册生成器**：实现 `cockpit docs export`，一键生成对标 `gh`/`kubectl` 的 Markdown 命令参考手册 `docs/CLI-REFERENCE.md`。

## 踩了什么坑

| 坑 | 修复 |
|----|------|
| 非法 Shell 参数直接在 argparse 解析时 raise SystemExit | 在测试中捕获 SystemExit 并断言纯净 JSON 报错内容与 ExitCode 2 |
| 文档路径在嵌套目录下 parents 层级计算偏差 | 修正 WORKSPACE_ROOT 为正确的 parents[5] 定位到 Workspace 根目录 |

## 交付自证

- 测试覆盖：`test_fuzzy_matching.py`, `test_completion.py`, `test_docs.py` 全部 100% PASS。
- 生成手册：`docs/CLI-REFERENCE.md` (323 行)。
- 门禁状态：`make gac-local-gate` 56 项全绿通过。
