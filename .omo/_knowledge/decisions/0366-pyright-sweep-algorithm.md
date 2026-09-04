---
id: ADR-0366
title: Pyright 与 Ruff 扫描修复算法固化
status: ACCEPTED
date: 2026-08-04
owner: governance-team
lifecycle: spec
last_updated: 2026-08-04
---

# ADR-0366: Pyright 与 Ruff 扫描修复算法固化

## 背景

跨 Python 项目的类型与风格债务清理依赖 `/tmp` 中的一次性脚本。脚本之间重复解析 pyright JSON、添加抑制和处理测试文件，且 SIM117 自动改写曾产生无效语法。临时文件无法复用、审查或由工作流门禁覆盖。

## 决策

1. 将通用能力收敛到 `bin/sweep/`：`pyright.py` 消费 pyright JSON 并按项目过滤，`ruff.py` 执行有界修复循环，`nested-with.py` 只合并可证明安全的简单嵌套上下文管理器。
2. 类型修复优先修复真实契约与实现错误；工具只对剩余动态边界添加显式、规则级抑制。测试文件仅在同一规则达到阈值时使用文件级抑制。
3. 每轮遵循扫描、修复、格式化、复扫、测试的收敛循环；任何自动结构改写必须先通过 AST 解析，再运行项目测试。
4. 注册 `pyright-sweep` 专属 workflow，以项目源码、类型配置和 `bin/sweep/**` 为路由面，并通过 `diff_checks` 提供 P74 检查层覆盖。
5. TypeScript 项目不进入 Python pyright 扫描范围，使用其项目本地 TypeScript 工具链。

## 影响

- 类型债务清理从临时脚本升级为可审查、可复现的仓库能力。
- 专属 workflow 替代反复错位使用 `project-code-change`，并保留项目测试和根治理门禁。
- 工具不会把零错误等同于正确性，真实缺陷修复与抑制仍需人工审查。

## 验证

```bash
python3 -m py_compile bin/sweep/*.py
python3 bin/sweep/ruff.py bin/sweep --max-rounds 1
uv run --with pyyaml python bin/agent-workflow.py lint
make gac-local-gate
```
