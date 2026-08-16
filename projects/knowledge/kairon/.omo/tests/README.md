---
title: README
type: doc
status: active
---

# 质量门禁结果

> `gate-results/` 目录存储 CI gate 运行历史。

## 目录结构

```
tests/
  └── gate-results/
      └── YYYY-MM-DD-run-N/
          ├── ruff-check.txt       # ruff check 结果
          ├── pytest.txt           # pytest 结果
          ├── version-check.txt    # 版本一致性扫描结果
          └── format-check.txt     # ruff format --check 结果
```

## 门禁项

| 检查项 | 命令 | 阈值 |
|--------|------|------|
| Ruff lint | `ruff check packages/` | 零错误 |
| 格式检查 | `ruff format --check packages/` | 无差异 |
| 测试 | `pytest packages/` | 通过率 100% |
| 版本一致性 | AST 扫描 `__version__` vs `pyproject.toml` | 完全一致 |
