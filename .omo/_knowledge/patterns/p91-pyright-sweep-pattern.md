---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-08-04
related:
  - ../decisions/0364-pyright-sweep-algorithm.md
  - p74-workflow-solidification-pattern.md
type: ssot
---

# P91 — Pyright Sweep Pattern

## 1. 触发条件

适用于 Python 项目出现批量 pyright 错误、跨包类型债务清理，或 ruff 修复与类型检查反复互相影响的场景。TypeScript 项目使用本地 TypeScript 工具链，不套用本模式。

## 2. 收敛循环

1. 在目标项目运行 pyright JSON 输出并按错误规则、文件和生产代码/测试代码分类。
2. 优先修复真实缺陷：错误签名、错误参数名、错误返回类型、重复路由、缺失依赖和无效上下文管理器注解。
3. 对不可静态表达的动态边界运行 `bin/sweep/pyright.py`，使用规则级、行级抑制；测试文件的重复规则可按阈值提升为文件级抑制。
4. 运行 `bin/sweep/ruff.py` 做有界安全修复。SIM117 需要结构改写时，仅使用 `bin/sweep/nested-with.py`，并要求 AST 解析通过。
5. 重复 pyright、ruff、格式化和项目测试，直到连续一轮无新增诊断。
6. 最后运行 workspace 治理门禁，并通过 `pyright-sweep` workflow 留存 claim、verify 和 closeout 证据。

## 3. 安全边界

- 零诊断不是正确性证明，禁止用全局关闭规则掩盖真实契约错误。
- 抑制必须包含具体 pyright rule，不使用无类别的 `type: ignore`。
- 自动工具不修改反斜杠续行，不跨越复杂多行 `with` 头，不处理无法通过 AST 的结果。
- `ruff --unsafe-fixes` 默认关闭，只有人工审查后显式启用。
- 每个项目使用自身依赖和测试命令，不从根目录推断所有包共享同一环境。

## 4. 防复发

`agent-workflows.yaml` 的 `pyright-sweep` workflow 负责专属路由；对应 `diff_checks` 覆盖项目 Python 源码、类型配置和 `bin/sweep/**`，避免 P74 沉默。工具自身由 ruff、py_compile、workflow lint 和 `gac-local-gate` 校验。
