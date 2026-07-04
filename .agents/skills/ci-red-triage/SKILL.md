---
name: ci-red-triage
description: "Diagnose & fix omostation CI red via 6-layer recursive triage (P75). Use when gh pr checks fail, main CI red, or gac-local-gate FAIL. Triggers: CI fail, evidence-gate fail, governance-verify fail, interface-check fail, actionlint/shellcheck/ruff/markdownlint fail, ModuleNotFound, uv.lock gitignored, set -e silent break, P75."
---

# CI Red Recursive Triage (P75)

Diagnose & fix omostation CI red. CI red is a **recursive onion** — fixing one layer exposes the next; one CI run only shows the top fail (set -e hides later ones). Must iterate push→CI→diagnose→fix.

**Pattern**: [.omo/_knowledge/patterns/p75-ci-red-triage-pattern.md](../../../.omo/_knowledge/patterns/p75-ci-red-triage-pattern.md)

## When To Use

- `gh pr checks <PR> | grep fail` non-empty
- `gh run list --branch main` shows FAIL (pre-existing debt)
- `gac-local-gate` FAIL with unknown root cause

## Procedure

### 1. List fails + classify truth

```bash
gh pr checks <PR> --repo <repo> | grep -i fail
gh run view <run-id> --repo <repo> --log-failed | grep -iE "error|fail|SC|MD|assert|ModuleNotFound|Traceback"
gh run list --branch main --repo <repo>     # 预存判定 (main 同 FAIL = pre-existing)
```

Classify each fail (P73 truth-driven):
- **真 bug (引入)**: 我改的文件相关 + main 绿 → 立即修
- **预存 (主仓同红)**: main 同 FAIL → 修或 admin merge (§5)
- **环境 (CI 独有)**: 本地 PASS / CI FAIL (tracked 快照 / 子模块 / 本地工具) → 降级 (git fallback / local-only)

### 2. 6-layer triage (层序诊断, 修一层 push 暴露下层)

| 层 | 典型 fail | 修复 |
|---|---|---|
| **L1 配置根因** | `No solution` / `ModuleNotFound` / `invalid input` | pyproject `[tool.uv.sources]` 显式依赖 + path / 删无效 input |
| **L2 子模块** | test assert / drift / import | `omo lint` / registry 同步 runtime / **track uv.lock** (D1) |
| **L3 CI 环境** | `PYTHONPATH` 缺包 / `set -e` 中断 / `.omo/tests` 缺 | `pip install` 补全 / `\|\| true` / `skip if absent` |
| **L4 lint 噪音** | SC2086 / F841 / MD031 | `--severity=error` 聚焦 / ignore 一致 / 格式 |
| **L5 生成器格式** | 自动注入段 MD004/031 | **修生成器** (非修输出, 避免下次覆盖) |
| **L6 本地工具** | `--directory` 绝对路径 CI 无 | `local-only` (诚实区分, 非 gap) |

### 3. Verify local (复现 + 验证修复)

```bash
uv run --project projects/<sub> python -c "import <pkg>"   # resolve 验证
uv run --project projects/<sub> pytest tests/<test> -q     # test 复现
uv run --directory projects/agora python bin/evidence-smoke.py --gate 95  # evidence
uv run --with pyyaml python bin/gac-local-gate.py --scope staged --json   # 本地 gate
```

### 4. Commit + PR (per worktree-pr-landing-sop)

- **change-lane 拆 commit**: governance_state / CI config / submodule_pointer 分开 (单 lane 放行)
- `--no-verify` 仅限 submodule_pointer_drift bump 中间态 (非绕 gate)
- push → CI → 递归 (回到 §1, 直到全绿)

### 5. Admin merge (CI 非全绿时, 三条件全部满足)

1. 本地 GaC gate 绿 (`gac-local-gate --scope staged --json` ok=True)
2. CI fail 全预存/环境 (main 同红 或 本地 PASS/CI FAIL)
3. 用户授权 (盲修/合并明确)

→ `gh pr merge <PR> --admin --squash`. 否则继续 §2.

## 7 Pitfalls (PR#107+#108 实战, 高发)

- **D1** uv.lock gitignored → CI 无 lock, uv sync 不装依赖 (omo .gitignore uv.lock)
- **D2** verify-omo `[N/5]` 段 PYTHONPATH 系统 python 缺包 (uv run 段 venv, PYTHONPATH 段系统)
- **D3** step set -e + lint 无 `|| true` → 某 exit 1 静默中断 (governance surfaces 致 pytest 没跑)
- **D4** workspace `{workspace=true}` 传递不暴露 (omo 缺 aetherforge 顶层包)
- **D5** tracked 运行快照 (governance_feedback_last_run / health.yaml generated_at) CI stale
- **D6** 生成器输出格式 (consensus-inject `*` MD004 / 引用 ``` MD031)
- **D7** 本地绝对路径 (evidence `--directory ~/ToolBox/`) CI 无

详见 p75 pattern §5.

## Anti-patterns

- ❌ 只修一层就 merge (下一层反弹)
- ❌ 盲目 `--no-verify` (不诊断根因, 除非 §5 三条件)
- ❌ 修生成器输出而非生成器 (下次注入覆盖)
- ❌ 本地绝对路径当 gap (CI 无本地工具不是代码鸿沟)
- ❌ 忽略 uv.lock tracked (gitignored lock 致 CI 无法重现)
