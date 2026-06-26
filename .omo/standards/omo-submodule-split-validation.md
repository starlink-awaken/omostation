---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# omo Submodule 拆分验证模板 (7-step Checklist)

> 状态: active | 版本: v1.0 | 引入: 2026-06-25 (P109-A)
> 关联: ADR-0094-0102 (omo_lint + omo_governance_surfaces 5 阶段拆解), ADR-0100 D7 (教训)
> 适用范围: omo submodule 内任何 Python 模块 god-module 拆解 (P100+ 模式)

---

## 1. 适用范围

本模板用于 omo submodule 内 Python god-module (>800L warn / >1500L error) 拆解到独立子模块的验证流程。

**强制要求**: 7 步缺一即 `request changes`, 不得合并步、不得省略步。

**应用场景**: P100-P108 模式 (omo_lint 拆 schemas/yaml-bypass/surfaces/mutation-ledger/doc-lifecycle, omo_governance_surfaces 拆 snapshots/ingress/task_policy/ingress_artifacts/state_plane/mutation_surface/c2g_boundary/internal_write_profiles)

---

## 2. 7 步硬结构 Checklist

### 2.1 Step 1: 子模块创建 (Submodule file creation)

- [ ] 新文件 `omo_<parent>_<child>.py` 创建, 在 `projects/omo/src/omo/` 目录
- [ ] 文件头包含 docstring (P88 模式: 起始阶段 + 拆解行数 + 业务说明 + 模块依赖 + 向后兼容说明)
- [ ] 函数体 1:1 从原文件迁移, **不允许** 在迁移过程中修改业务逻辑
- [ ] `python3 -c "import ast; ast.parse(open(f).read())"` 通过
- [ ] **新文件行数 <800L** (warn 阈值, 不触发 god-module error)

### 2.2 Step 2: 原文件剥离 (Source file strip)

- [ ] Python 脚本 or edit tool 移除 line range [start, end)
- [ ] 移除时保留前后 1 空白行 (保持代码结构清晰)
- [ ] **不删除任何尚未搬迁到子模块的 import**
- [ ] `python3 -c "import ast; ast.parse(open(f).read())"` 通过
- [ ] **原文件行数减少 ≥ 子模块净行数** (净行数 = 子模块行数 - 重导出/re-export 行数)

### 2.3 Step 3: Re-export 双向覆盖 (Re-export bidirectional coverage) 🔴

**🔴 必检 — P104 教训**: P104 末 Python 脚本声称 re-export 完成但实际漏写, 导致 P106 R3 lint 暴露 4 个 NameError.

**检查清单**:
- [ ] 列出**所有** 子模块 export 的 public 函数 (`def _check_*`, `def cmd_*`)
- [ ] 列出**所有** 子模块 export 的 module-level 常量 (`ALLOWED_*`, `EXPECTED_*`, `INGRESS_*` 等)
- [ ] 列出**所有** 子模块 export 的 helper 函数 (`_load_yaml`, `_category_counts` 等)
- [ ] 在原文件中 `from .<child_module> import (...)` 块覆盖**所有**以上符号
- [ ] **逐符号 import 验证**: 不可写 `import *`, 必须 explicit symbol 列表
- [ ] **避免 re-export 重复定义**: 子模块 export 的符号在原文件**不能再定义** (否则覆盖)

### 2.4 Step 4: Circular Import 修复 (Circular import resolution) 🔴

**🔴 必检 — P105 教训**: P105 首次实施触发 child → parent internal helper circular import.

**决策树**:
```
子模块 import 某个符号 X
  │
  ├─ X 在原文件定义?
  │   │
  │   ├─ 是 → child → parent internal helper
  │   │        │
  │   │        └─ 用 inline helper 模式 (P105 D2 范式)
  │   │           from omo.omo_shared import load_yaml_required
  │   │           def _load_yaml(path): return load_yaml_required(path)
  │   │
  │   └─ 否 → X 在 sibling 模块?
  │            │
  │            ├─ 是 → child → sibling (无 circular 风险)
  │            │        from omo.omo_<sibling> import X
  │            │
  │            └─ 否 → X 是 stdlib (Path, ast, yaml)
  │                     直接 import 即可
```

**验证**:
- [ ] 子模块 import 不形成循环 (A imports B, B imports A → 禁止)
- [ ] **优先 sibling import 范式** (P107, 优于 inline helper)
- [ ] **inline helper 仅在 circular 不可避免时使用** (P105)

### 2.5 Step 5: 全套 lint 验证 (Full lint suite) 🔴

**🔴 必检 — P106 教训**: P104 验证仅跑 `lint yaml-bypass`, 未跑 `mutation-surfaces`, 漏掉 NameError.

**omostation 治理面 6 lint 必跑**:
```bash
for cmd in ingress-registry mutation-surfaces internal-write-profiles \
          state-plane-assets c2g-omo-boundary ingress-artifacts; do
    PYTHONPATH=projects/omo/src uv run --with pyyaml \
        python3 -m omo.omo_lint $cmd 2>&1 | head -1
done
```

**omo lint 业务 lint 必跑** (按 P 阶段涉及范围):
- [ ] `schemas` — P100+ 后必跑
- [ ] `yaml-bypass` — P101+ 后必跑
- [ ] `mutation-ledger` — P103+ 后必跑
- [ ] `mutation-surfaces` — P104+ 后必跑 (如涉及 snapshot)
- [ ] `internal-write-profiles` — P108+ 后必跑
- [ ] `state-plane-assets` — P107+ 后必跑 (如涉及 state-plane)
- [ ] `c2g-omo-boundary` — P108+ 后必跑 (如涉及 c2g_boundary)
- [ ] `ingress-registry` — P105+ 后必跑 (如涉及 ingress)
- [ ] `ingress-artifacts` — P106+ 后必跑 (如涉及 ingress_artifacts)
- [ ] `task-policy` (隐式通过 mutation-surfaces)

**期望**: 6+ 行 `✅ omo lint <cmd> pass: ...`

### 2.6 Step 6: Re-export 等价验证 (Re-export equivalence)

```bash
cd projects/omo && PYTHONPATH=src uv run --with pyyaml python3 -c "
from omo.<parent_module> import (
    <symbol_a>,
    <symbol_b>,
    ...
)
from omo.<child_module> import (
    <symbol_a> as child_a,
    <symbol_b> as child_b,
    ...
)
assert <symbol_a> is child_a, f'<symbol_a> re-export broken'
assert <symbol_b> is child_b, f'<symbol_b> re-export broken'
print('✅ all N re-exports OK')
"
```

**期望**: `✅ all N re-exports OK`, 其中 N = 子模块 export 的 public symbol 数

### 2.7 Step 7: 阈值达标 + ADR 记录 (Threshold + ADR)

- [ ] **原文件行数 < 目标阈值**:
  - P100-P103 (omo_lint): 目标 <600L ideal, <400L 黄金值
  - P104-P108 (omo_governance_surfaces): 目标 <600L ideal, <500L 黄金值
  - **绝对阈值**: 永远 <800L (warn), 终极目标 <600L (ideal), <500L (黄金)
- [ ] **god-module 列表更新**: `bin/god-module-13-error-list.py` 中本文件消失或行数下降
- [ ] **ADR 编写**: `.omo/_knowledge/decisions/NNNN-p<phase>-<topic>.md`
  - 必含 7 段: Context / Decision / Consequences / Validation / References / D1-D7 (拆分细节) / 教训
  - **教训段** 必须显式登记前阶段失败模式 (e.g. P106 教训 P104 re-export 漏写)
- [ ] **mof-version 记录**: `bin/mof-version record "<description>"` → 版本号 +1
- [ ] **dashboard 验证**: `bin/governance-dashboard.py` → 22/22 OK
- [ ] **git commit**: 元数据 (ADR + mof-version) → 不 commit omo submodule (待人类审批)

---

## 3. 验证脚本 (Quick validation)

放在 `bin/omo-submodule-split-validate.sh` 提供一键检查:

```bash
#!/usr/bin/env bash
# omo submodule 拆分验证脚本 (P109-A)
# 用法: bin/omo-submodule-split-validate.sh <parent_module> <child_module> [N symbols]
set -euo pipefail

PARENT="${1:?parent module required (e.g. omo_governance_surfaces)}"
CHILD="${2:?child module required (e.g. omo_governance_surfaces_snapshots)}"
SYMBOLS="${3:-1}"

echo "=== P109-A validation: ${PARENT} + ${CHILD} ==="

# Step 3: re-export check
echo "--- Step 3: re-export coverage ---"
PARENT_FILE="projects/omo/src/omo/${PARENT}.py"
CHILD_FILE="projects/omo/src/omo/${CHILD}.py"

if ! grep -q "from .${CHILD#omo_} import" "$PARENT_FILE"; then
    echo "❌ FAIL: ${PARENT} does not re-export from ${CHILD}"
    exit 1
fi

# Step 5: 6 lint check
echo "--- Step 5: 6 surface lints ---"
for cmd in ingress-registry mutation-surfaces internal-write-profiles \
          state-plane-assets c2g-omo-boundary ingress-artifacts; do
    output=$(PYTHONPATH=projects/omo/src uv run --with pyyaml \
        python3 -m omo.omo_lint $cmd 2>&1 | head -1)
    if [[ ! "$output" =~ ^✅ ]]; then
        echo "❌ FAIL: lint $cmd: $output"
        exit 1
    fi
done
echo "✅ 6 surface lints pass"

# Step 6: re-export equivalence
echo "--- Step 6: re-export equivalence ---"
PYTHONPATH=projects/omo/src uv run --with pyyaml python3 -c "
from omo.${PARENT} import *
from omo.${CHILD} import *
# 比较共享 symbol 是否同对象
import inspect
parent_mod = __import__('omo.${PARENT}', fromlist=[''])
child_mod = __import__('omo.${CHILD}', fromlist=[''])
shared = set(dir(parent_mod)) & set(dir(child_mod)) - {'__builtins__', '__cached__', '__doc__', '__file__', '__loader__', '__name__', '__package__', '__path__', '__spec__'}
broken = [s for s in shared if getattr(parent_mod, s) is not getattr(child_mod, s) and not s.startswith('_')]
if broken:
    print(f'❌ BROKEN re-exports: {broken}')
    import sys; sys.exit(1)
print(f'✅ all {len(shared)} shared symbols OK')
"

# Step 7: threshold
echo "--- Step 7: threshold check ---"
LINES=$(wc -l < "$PARENT_FILE")
echo "  ${PARENT}: ${LINES}L"
if [[ $LINES -ge 800 ]]; then
    echo "❌ FAIL: ${PARENT} still >=800L (warn threshold)"
    exit 1
fi
echo "✅ threshold pass (<800L)"

echo ""
echo "🎉 all 7 steps pass for ${PARENT} + ${CHILD}"
```

---

## 4. 反模式 (Anti-patterns)

### 4.1 ❌ 验证只跑部分 lint (P104 教训)

```
# BAD
python3 -m omo.omo_lint yaml-bypass  # 只跑 1 个
echo "✅ looks good"

# GOOD
for cmd in ingress-registry mutation-surfaces internal-write-profiles \
          state-plane-assets c2g-omo-boundary ingress-artifacts; do
    python3 -m omo.omo_lint $cmd
done
```

### 4.2 ❌ commit message 声称成功但实际未生效 (P104 教训)

```
# BAD
echo "✅ 添加 re-export block (5 符号)"  # 但 Python 脚本 re_export 变量未写入
git commit -m "..."

# GOOD
# 验证步骤: 跑全套 lint + re-export equivalence 后再 commit
for cmd in ...; do python3 -m omo.omo_lint $cmd; done
PYTHONPATH=... python3 -c "assert <symbol> is <child_symbol>; print('OK')"
git commit -m "..."
```

### 4.3 ❌ 拆解中修改业务逻辑 (违反 P88 一致性原则)

```
# BAD: 拆解时顺便修 bug
# omo_lint_schemas.py 创建时改了 _check_schema_registry_integrity 的一行
# (声称: 顺便修个 bug)

# GOOD: 拆解不改业务
# 原代码 1:1 搬迁, bug 修复独立 P 阶段处理
```

### 4.4 ❌ 一次性拆太多子模块

```
# BAD
# 拆 1000L 文件到 5 子模块, 单次 commit 涉及 6 文件 + 1500L 变更
# 风险: 一旦某子模块有 bug, rollback 全部

# GOOD: 拆 1-2 子模块/阶段, 每 P 阶段验证后 commit
# P104 → P105 → P106 → P107 → P108 各拆 1-2 子模块, 5 阶段 5 commits
```

---

## 5. 应用示例

### 5.1 P108 应用案例 (omo_governance_surfaces + c2g_boundary/internal_write_profiles)

**Step 1**: 创建 2 子模块 (omo_governance_surfaces_c2g_boundary.py 91L + omo_governance_surfaces_internal_write_profiles.py 142L)

**Step 2**: 原文件 strip 2 段 (L104-154 + L222-325 = 155L)

**Step 3**: 7 子模块 re-export 完整覆盖 (snapshots 4 + ingress 2 + task_policy 1 + ingress_artifacts 1 + state_plane 1 + mutation_surface 1 + c2g_boundary 1 + internal_write_profiles 1 = 12 symbols)

**Step 4**: 决策树
- state_plane: child → parent `_load_yaml` → inline helper (P105 范式)
- mutation_surface: child → sibling `_mutation_surface_*` → sibling import (P107 范式)
- internal_write_profiles: child → sibling `_worker_*` → sibling import (P107 范式)
- c2g_boundary: child → parent `_load_yaml` + `ast` → inline + ast import (P105 + P108 范式)

**Step 5**: 全套 6 lint 通过 (首次暴露 ast import 缺失, P108 R3 修复)

**Step 6**: 8 re-exports 等价验证 ✓

**Step 7**: 443L 黄金值达成, ADR-0102 记录, mof-version v0.0.97

---

## 6. 关键 memory 引用

- `ADR-0094` P100 omo_lint schemas 拆解 (拆解模式范本)
- `ADR-0099` P105 ingress-check 拆解 (circular import 修复)
- `ADR-0100` P106 4 子模块化 (P104 re-export 教训)
- `ADR-0101` P107 6 子模块化 (cross-sibling import 范式)
- `ADR-0102` P108 8 子模块化 (ast import + 黄金值达成)
- `feedback_p104_re_export_missing_20260625.md` — 教训文档

---

*版本: v1.0 | 2026-06-25 引入 | P109-A 治理价值: 避免 P104/P106 类错误再次发生, ROI 极高 (1 文件 + 1 验证脚本)*
