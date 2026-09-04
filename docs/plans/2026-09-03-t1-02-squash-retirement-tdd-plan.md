---
schema_version: specification/v1
spec_version: 1.0.0
title: T1-02 Squash-Successor Clone Retirement — TDD Implementation Plan
bet_id: BET-Y1Q4-T1-02
status: accepted
lifecycle: plan
owner: governance-team
created: 2026-09-03
last_updated: 2026-09-03
type: ssot
last_updated: 2026-09-03
---

# T1-02 TDD Implementation Plan

Spec: `docs/superpowers/specs/2026-09-01-squash-successor-clone-retirement-provenance-design.md`

## Phase 2 → Phase 3 交接

- Phase 0 (draft Spec) ✅
- Phase 1 (accepted binding) ✅ — BET-Y1Q4-T1-02 bound, status=candidate
- **Phase 2 (this plan) ✅ — TDD 实现计划**
- Phase 3 (implementation) ← 当前
- Phase 4 (operary canary) — 需单独 principal 授权

## 1. 变更面 (KISS — 最小扩展)

| 文件 | 变更 |
|------|------|
| `bin/gac/clone-lifecycle.py` | +~250 行：CLI 4 参数、P1-P11 proof、receipt 链、幂等路径 |
| `tests/test_clone_lifecycle.py` | +~600 行：RED fixture + 23 negative/race |
| `bin/gac/agent-clone.py` | **不改** — 复用现有 retirement-provenance |
| 运行时/注册表/调度器 | **不改** — spec non_goal |

## 2. CLI 扩展

```python
# build_parser() retire subparser 新增：
sp.add_argument("--squash-merged-pr", type=int, help="...")
sp.add_argument("--source-tag", help="...")
sp.add_argument("--delivery-base", help="...")
sp.add_argument("--evidence", help="...")
```

契约：
- 四参数必须同时存在（否则 policy failure）
- 与 `--platform-rebased-pr` 互斥
- `--delivery-base` 必须 40-hex commit
- `--evidence` 必须在 clone 外、不能是 symlink

## 3. Proof Predicates P1-P11 实现映射

| Predicate | 现有代码位置 | 新代码 |
|-----------|------------|--------|
| P1 clone identity/clean | `cmd_retire` L1536-1575 | 复用 |
| P2 repository/origin | `bound_repository_slug` | 复用 |
| P3 exact merged PR | `query_platform_rebased_pr` | 复用（改 schema 字段名校验） |
| P4 annotated source tag | **新** `_verify_source_tag()` | tag object + peeled + remote 一致性 |
| P5 explicit delivery base | **新** `_verify_delivery_base()` | merge-base == delivery_base + ancestry |
| P6 delivery-only author | `run_provenance_guard` | 复用（platform_base=delivery_base, platform_head=source_head） |
| P7 one-parent squash | **新** `_verify_squash_topology()` | merge commit 单 parent == PR base |
| P8 patch-to-tree equivalence | **新** `_verify_patch_tree_equiv()` | binary patch → temp index → tree == merge tree |
| P9 current remote main | **新** `_verify_current_main()` | origin/main 双读 + squash ancestor |
| P10 surviving source branch | `ls-remote` 逻辑 | 复用（absent 或 == HEAD） |
| P11 external receipt chain | **新** `_persist_proof_receipt()` | O_CREAT\|O_EXCL\|O_NOFOLLOW + fsync |

## 4. 外部 Receipt 链

### 文件布局
```
<evidence>                          — proof (authorization)
<evidence>.delete-intent            — delete-intent (quarantine ownership)
<evidence>.settled                  — settlement (completion)
```

### Schema
- `clone-squash-successor-retirement-proof/v1`
- `clone-squash-successor-retirement-delete-intent/v1`
- `clone-squash-successor-retirement-settlement/v1`

### 写入规则
- parent-chain `O_NOFOLLOW` 校验
- leaf `O_CREAT | O_EXCL | O_NOFOLLOW`
- file + parent-directory `fsync`
- exact-match 幂等

## 5. 幂等已缺席处理

`cmd_retire` 当前 `already_absent` 直接返回 ok。新路径增加：

1. **Settled replay**: proof + delete-intent + settlement 全链有效 → 返回 ok
2. **Crash after delete, before settlement**: proof + delete-intent 链有效 → 写 settlement → ok
3. **Crash after quarantine, before delete**: proof + delete-intent + quarantine 匹配 → 恢复 FD-bound 删除 → ok
4. **Proof only / unrecorded quarantine / mismatched** → policy failure

## 6. TDD 执行顺序

### Step 1: RED (falsy fixture)

`tests/test_clone_lifecycle.py` 新增 `test_retire_squash_successor_motivating_topology`：

- 构建 v2 identity clone fixture（frozen root + 2 main successors + 1 delivery commit + annotated tag）
- 调用 `retire --squash-merged-pr ... --source-tag ... --delivery-base ... --evidence ...`
- **断言失败**：parser 报 unknown argument 或 ordinary retirement 返回 `clone_provenance_mismatch`

### Step 2: GREEN (minimal implementation)

按 P1-P11 顺序逐个实现 proof predicate，每通过一个跑一次测试：

1. CLI 解析 + 参数校验
2. P1-P2 identity/origin（复用现有）
3. P3 exact PR
4. P4 annotated tag
5. P5 delivery base
6. P6 author identity（复用 run_provenance_guard）
7. P7 squash topology
8. P8 patch-tree equivalence
9. P9 current main
10. P10 source branch
11. P11 receipt 链
12. 退场 + settlement

### Step 3: Negative/race coverage

23 个 negative test（spec §11.3 列表），分批实现。

### Step 4: Idempotent replay

3 个幂等 replay test。

## 7. Verify 契约

```bash
# 单文件 AST 校验
python3 -c 'import ast, pathlib; ast.parse(pathlib.Path("bin/gac/clone-lifecycle.py").read_text())'

# 聚焦测试
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml \
  python -m pytest -q -p no:cacheprovider tests/test_clone_lifecycle.py -k squash

# Lint
uv run ruff check bin/gac/clone-lifecycle.py tests/test_clone_lifecycle.py

# CLI help
python3 bin/gac/clone-lifecycle.py retire --help

# 全量回归
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml \
  python -m pytest -q -p no:cacheprovider tests/test_clone_lifecycle.py

# GaC gate
python3 bin/gac/gac-validate.py --gate
```

## 8. 风险与缓解

| 风险 | 缓解 |
|------|------|
| GitHub API 限流 | gh api rate_limit 检查 + 重试退避 |
| fixture 构建复杂 | 用 git commit-tree 直接构建精确 topology，不走完整 clone 生命周期 |
| receipt fsync 跨平台 | macOS/Linux fsync 语义一致，CI 双平台覆盖 |
| 现有 retirement 回归 | 全量 test_clone_lifecycle.py 必须绿 |

## 9. 不做的事（YAGNI）

- 不退场激励 clone（Phase 4 单独授权）
- 不改 agent-clone.py
- 不加新运行时/注册表/调度器
- 不声称个人价值（value_indicator_policy=false）
