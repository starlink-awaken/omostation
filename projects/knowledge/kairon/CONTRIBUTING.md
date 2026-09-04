---
title: CONTRIBUTING
type: doc
---

# Contributing to kairon

欢迎贡献！kairon 是一个 30 包的 Python monorepo。

## 开发环境

```bash
git clone https://github.com/starlink-awaken/kairon.git
cd kairon
uv sync
make test
make lint
```

## 代码规范

- Python 3.13+, 行宽 120
- `ruff format` 格式化，`ruff check` 检查
- `make lint` 确保零错误

## 提交流程

1. Fork 仓库
2. 创建特性分支: `git checkout -b feat/my-feature`
3. 提交变更: `git commit -m "feat(pkg): description"`
4. 推送到你的 Fork: `git push origin feat/my-feature`
5. 创建 Pull Request

## 提交信息格式

遵循 Conventional Commits:
- `feat(pkg):` 新功能
- `fix(pkg):` Bug 修复
- `test(pkg):` 测试
- `docs(pkg):` 文档
- `refactor(pkg):` 重构
- `chore(pkg):` 杂项

## 测试

```bash
make test        # 全量测试
make test-fast   # 仅单元测试
make lint        # Ruff 检查
```
