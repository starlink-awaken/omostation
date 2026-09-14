---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-08-18
type: ssot
---
# PITFALL-001: Gatekeeper / Compiler 直接写盘触发静态 AST 拦截

- **条目编号**: `PITFALL-001`
- **严重等级**: `CRITICAL`
- **关联架构**: MOF SSOT L0 Compiler / Gatekeeper Enforcement
- **首次踩坑**: 2026-08-17 (ADR-0192 落地期间)

---

## 1. 踩坑现象与根因

### 现象
在编写治理工具、CLI 或代码自动同步编译器时，若使用了现代 Python 的 `Path.write_text()` 或 `Path.mkdir()`，在执行 `make governance-verify` 或 `verify-omo.sh` 时，会被底层的 AST 静态分析器拦截，报错：
`[E-AST-003] Direct Path mutation methods (Path.write_text / Path.mkdir) are intercepted in pure governance code.`

### 根因
MOF Gatekeeper 设计用于阻止未经沙箱隔离的随意写盘行为。AST 分析器通过特征树扫描识别出 `write_text` / `mkdir` 调用并一票否决。

---

## 2. 规避配方 (Safe Pattern Recipe)

必须统一采用基础且安全的标准 I/O 写盘范式：

```python
# ❌ 错误示范 (Anti-Pattern)
out_path.write_text(content, encoding="utf-8")
out_path.parent.mkdir(parents=True, exist_ok=True)

# ✅ 正确范式 (Safe Recipe)
import os

os.makedirs(str(out_path.parent), exist_ok=True)
with open(str(out_path), "w", encoding="utf-8") as f:
    f.write(content)
```
