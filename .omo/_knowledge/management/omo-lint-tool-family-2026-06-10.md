---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# §13 omo_lint 工具家族 — 静态校验规则集 (Round 29 起步)

> **状态**: 起步 (Round 29 P0)
> **作者**: 老王
> **定位**: §11 AppendOnlyLog 模式 (10 consumer / 8 schema) 配套的 **静态校验工具**
> **目的**: CI 守住 X1 审计契约, 防止"未来代码绕过 Pydantic 写时锁"
> **链接**: §11.13 (Round 21 lint 扩 SCHEMA_REGISTRY 完整性) → §13 (工具家族独立成章)

---

## §13.0 一句话总结

omo_lint 是 §11 X1 审计契约的**自动守门人** — 用 ast 静态扫 7 consumer 模块, 校验 4 规则 (3 个 schema 完整 + 1 个写时 schema= 传参), CI (omo-lint-schemas job) 任何回归立即 fail, 0 漂移.

## §13.1 现有 4 规则 (R15-29 累积)

| # | 规则名 | 引入 | 校验 | 触发时 |
|---|--------|------|------|--------|
| 1 | `schema-kwarg-missing` | Round 15 P0 | `AppendOnlyLog(...).append(...)` 调用都传 `schema=` kwarg | 任何 7 consumer 模块 |
| 2 | `missing-z-timestamp` | Round 21 P0 | `SCHEMA_REGISTRY` 所有 schema 继承 `ZTimestampModel` (Z-suffix 校验) | `omo_lint schemas` |
| 3 | `no-required-fields` | Round 21 P0 | `SCHEMA_REGISTRY` 所有 schema 至少 1 必填字段 (防空架子) | `omo_lint schemas` |
| 4 | `missing-from-all` | Round 29 P0 | `omo_io_schemas.__all__` 包含 `SCHEMA_REGISTRY` 全部 class 名 (防 import 失败) | `omo_lint schemas` |

**当前覆盖** (Round 29 P0):
- 7 consumer 模块 (omo_audit / omo_bos_metrics / omo_history / omo_sync / omo_alert / omo_event / omo_trail) 写时 schema= ✓
- 8 schema 完整性 (audit / bos_metrics / history / sync / alert / event / trail / health) ✓
- `omo_io_schemas.__all__` 8 class 全暴露 ✓

## §13.2 工具 API

```python
# omo_lint.py 公开 API
from omo.omo_lint import (
    _check_module_append_has_schema,    # 规则 1
    _check_schema_registry_integrity,    # 规则 2+3
    _check_all_schemas_exported,         # 规则 4 (R29 新)
    cmd_lint_schemas,                    # CLI main
    CONSUMER_MODULES,                    # 7 模块列表
)
```

CLI:
```bash
uv run --no-sync python -m omo.cli lint schemas
# 输出: 4 段 (每规则一段) + 总 pass/fail
```

CI:
- `omo-lint-schemas` job 在 `.github/workflows/ci-lint.yml` (Round 15 P1)
- 退出码非 0 即 fail (硬约束, 不走 warning)

## §13.3 候选新规则 (R29+ 留)

按 §11.13 + §11.16 提到的 "omo_lint 加更多规则" 候选:

### §13.3.1 规则 5: `consumer-naming-consistency` (候选)

校验 `omo_*.py` 模块名 = SCHEMA_REGISTRY 命名对应 (e.g. `omo_audit.py` 对应 `OmoAuditRecord` schema).

**动机**: 防未来模块重命名时漏同步 schema 命名.

**实现**: 用 ast 扫 `omo_*.py` 文件名, 对比 `from omo.omo_io_schemas import OmoXxxRecord` 是否一致.

### §13.3.2 规则 6: `dead-import` (候选)

校验 `omo_*.py` consumer 模块 `import` 但未用 (dead code).

**动机**: 防止历史 import 残留, 提升可读性.

**风险**: 误报 (e.g. `import OmoTrailRecord` 实际在 `TYPE_CHECKING` block). 需 import-aware (用 ast `Name` 使用追踪).

### §13.3.3 规则 7: `cross-module-srp` (候选)

校验 `omo_X.py` 不应 `import omo_Y` (违反 SRP 单一职责).

**动机**: AppendOnlyLog 是底层 SSOT, 7 consumer 都依赖它 (单向), 但 consumer 之间不应相互依赖.

**实现**: 扫 `from omo.omo_X import` 在 `omo_Y.py` 中, 报违规.

**风险**: 跨模块工具函数 (e.g. `_utc_now` 在 `omo_audit`, 多个 consumer 共享) — 需白名单.

### §13.3.4 规则 8: `sort-keys-default` (候选)

校验 `AppendOnlyLog.append()` 调用未传 `sort_keys=True` 默认值不一致 (防 §12.1.4 sort_keys 默认违反).

**动机**: `sort_keys=True` 是 §12.1.4 跨仓 4 不变量之一, 字节级兼容.

**实现**: 扫 `AppendOnlyLog.append(..., sort_keys=...)` 关键字参数, 报漏 `sort_keys=True` 的调用.

**风险**: 某些场景故意不 sort_keys (e.g. 测试 fixture) — 需白名单.

## §13.4 §11 章节关系

- **§11** = AppendOnlyLog 模式实现 (10 段 + §11.16 omo_lint 工具家族)
- **§12** = 跨仓契约 (13 子节 + §12.5.1 跨仓 baseline 同步)
- **§13** = omo_lint 工具家族 (本节, 起步)

§13 与 §11.13-§11.16 互补:
- §11.13 描述"omo_lint 加 SCHEMA_REGISTRY 完整性" (Round 21)
- §11.16 描述"AppendOnlyLog 抽 _shared" (Round 24)
- §13 独立成章, 把 omo_lint 工具家族作为独立主题

## §13.5 Round 29+ 候选 (本节填充)

- [x] §13.0 起步 (本 commit)
- [x] §13.1 现有 4 规则 (R15-29 累积)
- [x] §13.2 工具 API
- [x] §13.3 候选新规则 4 个 (R29+ 留)
- [x] §13.4 §11 关系
- [x] §13.5 Round 29+ 候选
- [ ] §13.6+ 实施候选规则 1+ (R30+)

---

**§13 章节总览** (Round 29 起步):

| 子节 | 主题 | 状态 |
|------|------|------|
| §13.0 | 一句话总结 | ✅ Round 29 |
| §13.1 | 现有 4 规则 | ✅ Round 29 |
| §13.2 | 工具 API | ✅ Round 29 |
| §13.3 | 候选新规则 4 个 | ✅ Round 29 |
| §13.4 | §11 关系 | ✅ Round 29 |
| §13.5 | Round 29+ 候选 | ✅ Round 29 |
| **总** | **§13 6 子节 + 4 规则** | ✅ 起步 |
