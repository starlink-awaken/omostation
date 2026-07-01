---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-30
---

# P52 真治本范式 — Guide for Future Phases

> 2026-06-30 治本路线 (Phase 1.1, 1.2, 2) 沉淀的**真治本判定 + 实施方法**。
> 供后续 Phase 1.x / 2.x / 3.x work 引用, 避免重蹈 Tier 1 渐进式伪治本覆辙。

## 1. 治本 vs 治标 判别

| 判别 | 治标 (Tier 1) | 治本 (Tier 2) |
|------|-------------|-------------|
| 默认 fallback | `Path.home()` + env 双兜底 | **无兜底, fail-fast** |
| 错误信号 | 静默用错路径 | `ValueError` / `FileNotFoundError` 带 hint |
| 跨环境 | env 注入 (需文档化) | **TOML 单一源** |
| 测试污染 | `monkeypatch._BUILTIN_DOMAINS[i].path` | **tmp TOML + fixture** |
| 维护成本 | env 解析 + 默认合并 | **单一注入点, 无 merge 逻辑** |
| **关键差异** | **为错误前提加配置层** | **删除错误前提** |

## 2. 真治本 3 步法

### Step 1: 显式 raise 替代 silent fallback
```python
# ❌ Tier 1 伪治本
def __init__(self, *, path_overrides=None):
    if not path_overrides:
        path_overrides = self._load_env_overrides()  # silent fallback
    # ...

# ✅ Tier 2 真治本
def __init__(self, *, path_overrides: dict[str, Path]):
    if not path_overrides:
        raise ValueError("Explicit path_overrides required...")
    # ...
```

### Step 2: 单一注入点
- **生产**: `l4_kernel.cli._get_registry(config_path)` 走 TOML
- **测试**: `l4_kernel.testing.default_overrides(tmp_path)` 走 fixture
- **NO merge logic**: 优先用 path_overrides (显式) > env (兼容),**不混**

### Step 3: 错误信号可定位
```python
# Raise with hint (右用户知道下一步)
raise RuntimeError(
    "DomainRegistry requires explicit path_overrides. "
    "P52-final: removed Path.home() default + env fallback. "
    "Use l4_kernel.testing.default_overrides(tmp_path) for tests."
)
```

## 3. Tier 1 → Tier 2 升级的 4 个条件

在动手"真治本"前,确认以下 4 点:

- [x] **Tier 1 commit 在 origin 跑过 1 个完整周期** (验证不回归)
- [x] **错误前提识别清楚** (不是猜的: 查 git log, 查代码注释, 查 docs)
- [x] **跨包影响审计** (grep `直接调用模式` 全部站点, 例如 `DomainRegistry()` 无参)
- [x] **错误信号设计** (`ValueError` / `FileNotFoundError` 必须带 hint 到正确 API)

## 4. 实施 P52 真治本的 5 步模式

### Step 1: 扫描 + ADR
- 写 meta-ADR (ADR-0116 类型): 承认 Tier 1 是渐进, 文档化 Tier 2 目标
- 跑验证矩阵: 记录 Tier 1 baseline (test pass/fail/error 数量)

### Step 2: 错误前提清单
- 列出所有隐式假设: `Path.home()` / env / 默认值 / `or X()` fallback
- 每个错误前提 = 1 个 Tier 2 任务

### Step 3: 撤错误前提
- 删 `Path.home()` 默认
- 删 `or X()` 模式 (改 `or X.require_explicit()` 或必传参数)
- 删 env 隐式注入

### Step 4: 单一注入点
- 新增生产入口: `_get_registry(config_path)` (TOML)
- 新增测试入口: `default_overrides(tmp_path)`
- 新增 `require_explicit()` 助手 (失败时给 hint)

### Step 5: 跨包传播
- 用 `sed` 批量替换所有 `DomainRegistry()` → `DomainRegistry(path_overrides=...)`
- 测试 fixture 统一改用 `registry` 参数
- conftest.py 加 autouse fixture 写 tmp TOML + patch `cli.DEFAULT_CONFIG_PATH`

## 5. 真治本 4 个常见陷阱

### 陷阱 1: "为错误前提加配置"
```python
# ❌ 错误
DEFAULT_PATH = Path.home() / "Documents"
class Registry:
    def __init__(self, override_path=None):
        self.path = override_path or DEFAULT_PATH  # 错误前提仍在

# ✅ 正确
class Registry:
    def __init__(self, *, path: Path):  # 必须传
        if not path:
            raise ValueError("path required")
        self.path = path
```

### 陷阱 2: 测试用 monkeypatch 污染源数据
```python
# ❌ 错误
@pytest.fixture
def registry():
    reg = DomainRegistry()
    for d in _BUILTIN_DOMAINS:
        d.path = tmp_path / d.id  # 改全局!
    return reg

# ✅ 正确
@pytest.fixture
def registry(tmp_path):
    overrides = {d.id: tmp_path / d.id for d in _BUILTIN_DOMAINS}
    return DomainRegistry(path_overrides=overrides)  # 不改源数据
```

### 陷阱 3: "PEP 562 __getattr__ 是真治本"
```python
# ❌ 部分治本 (过渡)
def __getattr__(name):
    if name in ("_registry", ...):
        return _get_globals()[name[1:]]  # 兼容旧 API
```

`__getattr__` 是**渐进方案**, 真治本应**全面重写**为显式函数调用。

### 陷阱 4: 跨仓 multi-call-sites 改不动
- Tier 2 真治本常需跨仓改 N 个项目 (例如 l4-kernel 改了 9 个 src + 5 个 test + 2 个 conftest)
- 治本 ROI 看: 1 个 commit 改 22 files vs 散落 N 个 Tier 1 commit
- **总是合并 1 commit, 不要分拆** (避免中间态 fail)

## 6. P52 范式的 ADR 模板

每个 Tier 2 真治本 Phase 都应该:
1. 写 meta-ADR (承认 Tier 1 是渐进, 文档化 Tier 2 目标)
2. 列出错误前提清单 (grep + 审计)
3. 实施后写 review doc (在 `.omo/_knowledge/reviews/`)
4. 跑验证矩阵 (确保无回归)
5. 写 Phase-specific ADR (记录决策, 含 Alternatives Considered)

## 7. P52 范式 vs 其他范式

| 范式 | 适用 | 不适用 |
|------|------|--------|
| **P52 真治本** | 错误前提清晰, 单一概念层, 跨包可控 | 多源混乱, 概念层不清 |
| **P45 R2 doc-lifecycle** | 文档散落, 需 frontmatter 化 | 文档已结构化 |
| **P59 闭环纪律** | 5+ 时序未闭环 | 单点改动 |
| **P60 治理内化** | 治理散落 | 治理已集中 |

**P52 范式 = "撤错误前提 + 单一注入点"**, 与其他范式正交, 可叠加使用。

## 8. 真实案例参考

### Case Study 1: l4-kernel DomainRegistry
- Tier 1 (b865ab4): env 注入, 保留 Path.home() 默认 → 伪治本
- Tier 2 (3147e8c): 删 Path.home(), 删 env 注入, TOML 显式 → 真治本
- 关键改动: 22 files, +485/-291, 255/255 tests pass
- 反思: `.omo/_knowledge/reviews/2026-06-30-phase1.1-l4-kernel-final-review.md`

### Case Study 2: model-driven LifecycleStage
- Tier 1 (ADR-0115): 测试改 7→8, 接受 P60 第 8 阶段 → 伪治本
- Tier 2 (ADR-0117): 撤销第 8 阶段, 治理归 X 轴 → 真治本
- 关键改动: 1 enum value + 1 dict entry + 4 test assertions
- 反思: X 错塞 L2 是根本错误, 接受而非撤销是治标

## 9. P52 范式 Failure Mode

**Phase 2 失败案例**: 根仓 dev-deps 统一
- 尝试: 根仓 `[tool.uv].dev-dependencies` 集中, 13 个项目统一
- 失败: aetherforge/kairon 是 nested workspace, agora/cockpit 跨 path source
- 处理: ADR-0118 记录部分真治本 (10/13 = 76%), P3 work 跟进
- 教训: 跨仓治本前先审计 nested workspace + path source chain

## References

- ADR-0116: Tier 1 vs Tier 2 meta-reflection
- ADR-0117: 撤销 P60 第 8 阶段 (Tier 2 范式应用)
- ADR-0118: 根仓 dev-deps 部分真治本 (Tier 2 范式局限性)
- `.omo/_knowledge/reviews/2026-06-30-phase1.1-l4-kernel-final-review.md`
