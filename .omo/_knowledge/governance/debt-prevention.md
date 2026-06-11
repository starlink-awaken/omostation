# 债务预防规范

> 通过 pre-commit hook 和流程规范，防止新债务产生

---

## Pre-commit 检查项

### 1. 非原子写入检查

**检测规则**:
- 检测 `write_text()` 和 `open("w")` 调用
- 跳过已使用 `atomic_write` 的文件
- 跳过测试文件和脚手架代码

**修复方式**:
```python
# 错误
path.write_text(json.dumps(data))

# 正确
from kairon_utils import atomic_write_json
atomic_write_json(path, data)
```

### 2. 新包测试覆盖检查

**检测规则**:
- 检测新增的 `packages/*/pyproject.toml`
- 检查对应目录是否有 `tests/`

**修复方式**:
```bash
# 创建测试目录
mkdir -p packages/my-package/tests
touch packages/my-package/tests/__init__.py
touch packages/my-package/tests/test_basic.py
```

---

## 债务预防清单

### 代码审查时

- [ ] 是否使用了原子写入？
- [ ] 是否有对应的单元测试？
- [ ] 是否更新了相关文档？
- [ ] 是否遵守了 SSOT 原则？

### 合并前

- [ ] pre-commit 检查通过
- [ ] 测试覆盖率达标
- [ ] 文档已更新
- [ ] CHANGELOG 已更新

---

## 债务响应流程

```
发现债务 → 登记 (omo-debt register) → 分类 → 优先级 → 修复 → 验证 → 关闭
```

### 响应时间

| 严重程度 | 响应时间 | 修复时间 |
|----------|----------|----------|
| critical | 立即 | 24小时 |
| high | 24小时 | 1周 |
| medium | 1周 | 1月 |
| low | 1月 | 1季度 |

---

*最后更新: 2026-06-11*
