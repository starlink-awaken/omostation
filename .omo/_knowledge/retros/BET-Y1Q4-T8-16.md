---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T8-16
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-05
type: ephemeral
---

# BET-Y1Q4-T8-16 retro — DX 三件套（补全/纠错/单源手册）

## What changed

- **completion.py**：新增 `suggest_commands`（纯 Python Levenshtein，距离 ≤2
  从 SSOT registry 取候选，长度预过滤）+ 三壳生成器既有实现验证。
- **CLI-REFERENCE.md：303 行 → 1853 行**。根因：gen-help-docs.py 以
  `frontmatter=` 关键字调用 docs.py 的无参 `generate_cli_reference_markdown`，
  TypeError 被裸 `except Exception` 静默吞掉，永远走 303 行简表 fallback。
  修复：gen_cli_reference 重写为全量模式（COMMAND_CATALOG 106 命令 SSOT
  元数据 ∪ registry 扫描 207 条，每命令独立成节含 summary/域/成熟度/用法块，
  加目录索引/遗留映射/全局 Flags/补全说明/MCP 映射），不再依赖 docs.py。
- **did-you-mean**：cli.py 的 `WorkspaceParser.error` 已实现 canonical 机制
  （`fuzzy_matcher.find_closest_commands` + JSON suggestions 字段 + TTY
  建议），本轮验证其行为并纳入测试；completion.py 的 suggest_commands
  作为域感知候选 API 保留。曾实现 parse 前拦截后发现重复，已回滚。
- 测试 10/10（三壳合法性、typo 建议准确性/距离上界、parser.error JSON
  suggestions、CLI-REFERENCE ≥1400 行结构断言）。

## Q3 (打假)

- done_when "1400+ 行" 首跑只有 899 行（CATALOG 106 命令 × 元数据行不足），
  补标准 usage 块（--json/--dry-run/--help 三行）后 1853 行——用法块是
  通用模板而非逐命令定制，实际参数面以 `--help` 为准。
- docs.py 的静默 `except Exception` 掩盖签名不匹配达数周——防御性兜底
  必须至少 log。

## Q4 (遗留)

- CLI-REFERENCE 每命令参数表可从 argparse parser 反射生成（当前为通用
  模板）；example 字段 106 命令中大多数为空。
