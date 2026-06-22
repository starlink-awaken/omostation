---
status: deprecated
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
deprecated-since: 2026-06-22
superseded-by: ".omo/DOC-LIFECYCLE.md  (P45)"
note: "P45 审计: 0 引用, 标记 deprecated, 等人工 review"
---

# Workspace Dependency Baseline

> 外部依赖版本基线标准
> SSOT: `.omo/_truth/registry/dependency-baseline.yaml`
> 最后更新: 2026-06-20

## 目的

本标准定义工作区所有 Python 项目对外部依赖的统一最低版本约束，用于：

1. 减少 `uv.lock` 解析冲突
2. 避免同一依赖在不同项目中被锁定到差异过大的版本
3. 降低安全漏洞和历史版本兼容风险
4. 为新项目/新包添加依赖时提供参考

## 范围

覆盖 `projects/*` 及 `projects/*/packages/*` 中所有 `pyproject.toml` 声明的：

- 生产依赖 (`[project] dependencies`)
- 非 dev/test optional-dependencies（如 `web`、`llm`、`mcp`、`legacy`）
- dev/test 依赖单独列在 `dev_test` 段，不强制与生产基线一致

Workspace 内部项目之间的依赖（如 `agora`、`metaos`、`bus-foundation`、各 kairon packages）不列入本基线，由各自项目自行维护。

## 核心生产依赖基线

| 依赖 | 统一最低约束 | 说明 |
|------|-------------|------|
| `fastmcp` | `>=3.4.2` | 工作区统一 MCP 运行时 |
| `httpx` | `>=0.28.1` | HTTP client |
| `pydantic` | `>=2.13.4` | 数据模型 |
| `pyyaml` | `>=6.0.3` | YAML 解析 |
| `requests` | `>=2.34.2` | HTTP client（遗留场景） |
| `rich` | `>=13.0` | 受 `deepeval==4.0.6` 的 `<15.0.0` 上限约束 |
| `structlog` | `>=24.0` | 结构化日志 |
| `openai` | `>=2.41.1` | OpenAI SDK |
| `fastapi` | `>=0.128.8` | Web framework |
| `uvicorn` | `>=0.49.0` | ASGI server |

完整列表见 SSOT：`.omo/_truth/registry/dependency-baseline.yaml`

## 使用规则

1. **新增依赖时**：先查基线，优先使用基线中的最低约束；若业务需要更高版本，在代码评审中说明原因。
2. **升级依赖时**：如果提高了某个依赖的最低版本，同步更新 `.omo/_truth/registry/dependency-baseline.yaml`。
3. **禁止行为**：不要将明显过低的约束（如 `fastmcp>=0.1`）引入生产依赖；这类约束会扩大解析空间，引入不兼容旧版本的风险。

## 历史收敛

2026-06-20 完成三轮大规模收敛：

1. 打破 `agora ↔ metaos` 循环依赖：将 `metaos` 改为 `agora` 的 optional `admission` extra。
2. 统一 workspace 根级项目的外部依赖约束。
3. 统一 kairon/aetherforge workspace packages 的内部约束。

收敛后工作区内：

- 无循环依赖
- 无 editable mismatch
- 生产依赖外部版本约束差异显著降低

## 更新流程

1. 修改相关 `pyproject.toml`
2. 运行 `uv lock` 并验证 `uv sync`
3. 更新 `.omo/_truth/registry/dependency-baseline.yaml`
4. 提交并 push 对应子模块 + 根仓库指针
