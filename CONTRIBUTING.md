# Contributing to omostation / 贡献指南

> Welcome! 欢迎贡献。本文档提供参与 omostation 项目的完整指引。
>
> This document provides complete guidance for contributing to omostation.

[English](#english) | [中文](#中文)

---

<a name="english"></a>

## English

### Project Scope

8 active projects across 7 layers. The primary development areas are:

- **kairon**: Python monorepo (19 packages) — knowledge engineering pipeline
- **agora**: Python — I0 MCP service mesh
- **cockpit**: Python — L3 unified entry (CLI + Web)
- **gbrain**: TypeScript — knowledge database (67 MCP tools)
- **omo**: Python — governance & self-healing

### Development Workflow

```bash
# kairon
cd projects/kairon && uv sync && make test

# agora
cd projects/agora && uv sync && uv run pytest tests/ -q

# cockpit
cd projects/cockpit && uv sync && uv run pytest src/cockpit/tests/ -q

# gbrain
cd projects/gbrain && bun install && bun test
```

### Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat(scope):` — New feature
- `fix(scope):` — Bug fix
- `refactor(scope):` — Code refactoring
- `docs(scope):` — Documentation
- `test(scope):` — Tests
- `chore(scope):` — Maintenance

### Code Standards

- **Python**: ruff format + ruff check, line-length=120, Python 3.13+
- **TypeScript**: bun fmt + bun lint
- **Pre-commit**: auto ruff check on staged Python files across all projects

### Pull Request Process

1. Create a feature branch from `main`
2. Make changes following code standards
3. Run tests for affected projects
4. Ensure pre-commit check passes
5. Submit PR with clear description

---

<a name="中文"></a>

## 中文

### 项目范围

8 个活跃项目，7 层架构。主要开发领域：

- **kairon**: Python monorepo (19 包) — 知识工程管线
- **agora**: Python — I0 MCP 服务网格
- **cockpit**: Python — L3 统一入口 (CLI + Web)
- **gbrain**: TypeScript — 知识数据库 (67 MCP 工具)
- **omo**: Python — 治理与自愈引擎

### 开发流程

```bash
# kairon
cd projects/kairon && uv sync && make test

# agora
cd projects/agora && uv sync && uv run pytest tests/ -q

# cockpit
cd projects/cockpit && uv sync && uv run pytest src/cockpit/tests/ -q

# gbrain
cd projects/gbrain && bun install && bun test
```

### 提交规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat(scope):` — 新功能
- `fix(scope):` — 修复
- `refactor(scope):` — 代码重构
- `docs(scope):` — 文档
- `test(scope):` — 测试
- `chore(scope):` — 运维

### 代码规范

- **Python**: ruff format + ruff check, 行长=120, Python 3.13+
- **TypeScript**: bun fmt + bun lint
- **Pre-commit**: 自动 ruff 检查所有项目已暂存的 Python 文件

### PR 流程

1. 从 `main` 创建功能分支
2. 按代码规范进行修改
3. 运行受影响项目的测试
4. 确保 pre-commit 检查通过
5. 提交 PR 并附清晰说明
