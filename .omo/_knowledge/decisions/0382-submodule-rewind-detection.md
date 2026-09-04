---
id: ADR-0382
title: 子模块指针回退检测 (CR-SUBMODULE-REWIND)
status: ACCEPTED
lifecycle: spec
owner: governance-team
last_updated: 2026-08-07
---

# ADR-0380: 子模块指针回退检测

> **Status**: Accepted
> **Date**: 2026-08-06
> **Author**: governance-team
> **Supersedes**: (none)
> **Related**: ADR-0152 (M4 submodule hygiene), ADR-0158 (submodule bump auto), ADR-0379 (CI plane convergence)

## Context

2026-08-06 发生一起子模块指针意外回退事故:

- **事故提交**: `4662b95a5`
- **影响范围**: `projects/agora`
- **回退前指针**: `d4a9d1c` (Phase 4 变更)
- **回退后指针**: `f57d13dd` (Phase 4 变更被撤销)
- **后果**: Phase 4 的 agora 变更被意外撤销, CI 未能在合并前检测到回退

事故根因:
1. 主仓 commit 中 `.gitmodules` / gitlink 记录被意外修改为旧指针
2. 现有检查 (CR-M4-SUBMODULE-HYGIENE / CR-SUBMODULE-BUMP-AUTO) 仅检测指针滞后 (stale) 或脏状态, 无法检测指针被主动回退
3. 回退后的指针 `f57d13dd` 与回退前 `d4a9d1c` 在子模块历史中存在 ancestor 关系 (线性历史), 导致 `git merge-base --is-ancestor` 无法区分"正常前进"与"回退后重前进"

## Decision

新增 **CR-SUBMODULE-REWIND** 检查, 在 pre-commit 和 CI 中运行:

```
CR-SUBMODULE-REWIND
├── dimension: X1 (审计/安全)
├── layer: meta
├── check_type: audit_chain
├── executor: ci_gate + gac_local_gate
├── enforcement: required
└── source_ref: bin/gac/check-submodule-rewind.py::main
```

### 检测逻辑

```python
# 1. 读取 index 当前 gitlink
current_gitlinks = git ls-files --stage  # mode=160000, stage=0

# 2. 获取上一次 commit 的指针
previous_sha = git log -1 --format=%H -- <submodule_path>

# 3. 检测回退: 当前指针 NOT ancestor of 上一次指针
if not git merge-base --is-ancestor <current_sha> <previous_sha>:
    report_rewind(<submodule_path>, current_sha, previous_sha)
```

### 判定语义

| 条件 | 含义 |
|:---|:---|
| `current == previous` | 无变更, 跳过 |
| `current IS ancestor of previous` | 指针前进 (正常) |
| `current NOT ancestor of previous` | 指针回退或历史改写 (REWIND → FAIL) |

### 容忍条件 (Tolerance Layers)

以下场景不报 rewind, 视为合法指针变更:

| # | 场景 | 判定条件 | 原因 |
|:---|:---|:---|
| 1 | 相同提交 | `current == previous` | 无变更 |
| 2 | SHA 缺失 | `git cat-file -t` 返回非 commit | force-push 清理旧提交, 无法判定方向 |
| 3 | 默认分支前向 | `merge-base --is-ancestor` 在 default branch 通过 | 正常前进 |
| 4 | 任意 ref 前向 | `merge-base --is-ancestor` 在任意 ref 通过 | 分支切换 |
| 5 | 旧指针不可达 | `git rev-parse --verify` 失败 | force-push 已清理旧指针 |
| 6 | 特性分支 rebase | HEAD 在非默认分支 | 合法的 feature-branch rebase |
| 7 | detached-HEAD 分支 tip | 新指针是某分支 tip | 分支切换后的合法状态 |

> **实现**: `bin/gac/check-submodule-rewind.py::is_descendant_or_equal`
> **调试**: 运行 `python3 bin/gac/check-submodule-rewind.py --verbose` 可查看每层容忍的通过原因

### 监控策略 (Monitoring Policy)

#### WARN 阈值

当同一容忍层触发次数超过 `--warn-threshold`（默认 3）时，输出 WARN 提示。这表明该子模块的 rebase 策略可能不规范，建议人工 review。

```bash
python3 bin/gac/check-submodule-rewind.py --warn-threshold 3
```

#### CI 结构化集成

CI workflow (`governance-check.yml`) 已集成 `--json` 输出：

```bash
python3 bin/gac/check-submodule-rewind.py --json > /tmp/rewind-report.json
python3 -c "import json,sys; d=json.load(open('/tmp/rewind-report.json')); v=d.get('violations',[]); w=d.get('warns',[]); print(f'rewind violations={len(v)}, warns={len(w)}'); sys.exit(1 if v else 0)"
```

JSON schema:
```json
{
  "ok": true,
  "violations": [],
  "details": [],
  "warns": [],
  "tolerance_counts": {}
}
```

#### 人工 Review 触发条件

以下容忍层触发时，建议在 commit message 中附带说明：

| 容忍层 | 建议 commit message 格式 |
|:---|:---|
| `force-pushed-away` | `chore(submodule): bump <name> (force-push, old SHA gc'd)` |
| `feature-branch:*` | `chore(submodule): bump <name> (from feature branch <name>)` |
| `detached-head-tip` | `chore(submodule): bump <name> (detached HEAD, branch <name>)` |

### 与现有检查的协同

| 检查 | 职责 | 与 CR-SUBMODULE-REWIND 关系 |
|:---|:---|:---|
| CR-M4-SUBMODULE-HYGIENE | 检测 submodule dirty / tracked-derived / pointer-stale | 互补: hygiene 防脏, rewind 防回退 |
| CR-SUBMODULE-BUMP-AUTO | 检测主仓-子仓指针不对称 (滞后) | 互补: bump 防滞后, rewind 防倒退 |
| CR-SUBMODULE-REWIND | 检测指针被主动回退 (history rewrite) | 新增: 覆盖 rewind 场景 |

## Consequences

### Positive

- **事故复发阻断**: `4662b95a5` 类回退在 pre-commit 阶段即被拦截, 不会进入 CI
- **X1 审计强化**: 子模块指针变更是跨仓影响最大的操作之一, 回退检测补齐 X1 审计最后一环
- **CI 自愈**: 与 CR-M4-SUBMODULE-HYGIENE / CR-SUBMODULE-BUMP-AUTO 形成完整的子模块指针治理三角

### Negative / Trade-offs

- **Force-push 误报**: 子模块正常 force-push (如 rebase) 也会触发 rewind 检测。Mitigation: 子模块 force-push 需同步更新主仓指针并附带 ADR 说明
- **新子模块跳过**: 首次添加的子模块无 previous commit, 自动跳过 (不误报)

### Compatibility

- 向后兼容: 当前 main 分支无 rewind, 检查通过
- 与现有 gac-local-gate 39 项检查兼容, 新增第 40 项

## Implementation

- **Check script**: `bin/gac/check-submodule-rewind.py`
- **Tests**: `tests/unit/gac/test_check_submodule_rewind.py`
- **CI workflow**: `.github/workflows/governance-check.yml`
- **GaC registry**: `.omo/_truth/registry/governance-checks.yaml::CR-SUBMODULE-REWIND`
- **Gate wiring**: `bin/gac/gac-local-gate.py` (DEFAULT_POLICY gates)
- **ADR**: `.omo/_knowledge/decisions/0380-submodule-rewind-detection.md`

## Verification

| Check | Result |
|:---|:---|
| `python3 bin/gac/check-submodule-rewind.py` (current main) | **PASS** (0 rewinds) |
| `python3 bin/gac/check-submodule-rewind.py --json` | **PASS** (valid JSON schema) |
| `python3 bin/gac/check-submodule-rewind.py --verbose` | **PASS** (tolerance layers logged) |
| `pytest tests/unit/gac/test_check_submodule_rewind.py` | **9/9 PASS** |
| gac-local-gate | 40/40 checks registered |
| CR-SUBMODULE-REWIND 逻辑验证 | `git merge-base --is-ancestor` 语义正确 |

## Related

- ADR-0152 (M4 submodule hygiene)
- ADR-0158 (submodule bump auto)
- ADR-0379 (CI plane convergence)
- P71 baseline recovery pattern
- P78 triple-axis diagnostic pattern
