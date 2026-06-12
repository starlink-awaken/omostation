# 贡献指南

感谢您对本项目的关注！以下是贡献流程。

---

## 开发环境

```bash
# 克隆项目
git clone <repo-url>
cd <project>

# 安装依赖
uv sync

# 运行测试
uv run pytest tests/ -q
```

## 开发流程

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: 添加新功能'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 代码规范

- 使用 ruff 格式化代码
- 遵循 PEP 8 规范
- 添加必要的测试
- 更新相关文档

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `style:` 代码格式（不影响功能）
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具相关

---

感谢您的贡献！
