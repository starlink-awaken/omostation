---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T8-16
risk_level: L2
human_gate: false
value_indicator_policy: false
type: ssot
---

# T8-16 顶级开源 DX：Shell 补全、Did-you-mean 纠错与单源 CLI 手册设计

## 1. 目标

补齐 cockpit 开发者体验三件套的剩余缺口：bash/zsh/fish 原生补全生成器
（已有基础）、基于 Levenshtein 距离的 typo 智能纠错（缺失）、全自动单源
生成的全量 CLI-REFERENCE.md（现有 303 行 → 1400+ 行）。

## 2. In scope

1. `projects/cockpit/src/cockpit/commands/completion.py`：
   - 新增 typo 纠错：未知命令时按 Levenshtein 距离（≤2）从注册命令表
     给出 "Did you mean …?" 建议（含子命令层级）。
2. `bin/ssot/gen-help-docs.py`：扩展为全量单源生成——遍历 cli.py 注册的
   全部一级命令与子命令（170+），生成含用法、参数、示例的
   `docs/CLI-REFERENCE.md`（≥1400 行），保持既有生成结构。
3. `docs/CLI-REFERENCE.md`：由生成器重新生成（生成物入库）。
4. `projects/cockpit/tests/test_completion_and_typo.py`（新文件）：
   - 三壳补全脚本合法性（bash -n / zsh 语法结构 / fish 函数定义）。
   - typo 建议准确性（已知错拼 → 期望命令）。
   - CLI-REFERENCE 生成器行数下限与结构断言。

## 3. Out of scope

- 不引入 shell 补全第三方依赖；不改命令行为语义。
- 不做交互式 TUI 向导（属 T8-18）。

## 4. 验收（对齐 ledger done_when）

1. `cockpit completion` 产生合法 shell 补全脚本（三壳）。
2. 输错命令时提供准确 Did you mean 提示。
3. 自动生成 1400+ 行全量 CLI-REFERENCE.md。
4. 单测全部通过。
