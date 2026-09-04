---
type: ssot
---

# AGENTS.md — bin

## Scope

`bin/` 聚合治理、运维与治理脚本入口，包括 `agent-workflow`、`gac`、`doc-ssot` 及工具类脚本。变更会影响全仓门禁和治理流水线。

## 前置要求

1. 阅读根仓 [`../AGENTS.md`](../AGENTS.md) 和相应 CLAUDE 说明。
2. 任何功能/治理需求按 ADR-0203 流程走 `agent-workflow`。
3. 提交前确保脚本语法可解析（`python3 -m py_compile` / 对应语言编译）。

## 编辑原则

- 新脚本/工具优先复用既有能力，不重复实现同类命令。
- 任何脚本新增参数应有最小可复现用法说明（`--help`/文档）。
- 不在无效目录扫描里误杀未追踪运行目录；保持扫描可配置与幂等。

## 常用命令

- `make governance-surface-scan`
- `make governance-surface-scan-json`
- `python3 -m py_compile bin/ssot/root-directory-governance-scan.py`

