# Contributing to omostation

欢迎贡献。

## 项目范围

当前活跃项目主要在 `projects/kairon/`（Python monorepo）。  
其他项目（gbrain）各自独立演进。

## kairon 开发流程

```bash
cd projects/kairon

# 安装依赖
uv sync

# 运行全部测试
make test

# 单包测试
uv run --package ontoderive python -m pytest tests/ -q

# lint 检查
ruff check packages/
```

## 提交规范

遵循 Conventional Commits：

- `feat(xxx):` 新功能
- `fix(xxx):` 修复
- `refactor(xxx):` 重构
- `docs(xxx):` 文档
- `test(xxx):` 测试
- `chore(xxx):` 运维

xxx 为包名或模块名，如 `fix(ontoderive):`、`feat(agora):`。
