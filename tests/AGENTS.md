---
type: ephemeral
---

# AGENTS.md — tests

## Scope

`tests/` 存放根仓级测试与治理验证脚本。该目录属于交付质量基线，不做业务逻辑开发。

## 编辑规则

1. 先读根仓 [`../AGENTS.md`](../AGENTS.md) 与本目录相关流程。
2. 新增测试文件时保持命名清晰、可重放，避免与子项目测试重叠。
3. 对失败风险高的测试变更同步更新说明与执行命令。

## 常用命令

- `bash tests/integration/run-all.sh`
- `make gac-local-gate`
- `make ci-local`

## 发布检查

- 文档类变更：优先跑文档 SSOT 校验；
- 涉及交付门禁：按 `make gac-local-gate --scope files --file tests` 进行文件级检查。

