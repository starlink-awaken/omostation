---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-04
related:
  - p71-baseline-recovery-pattern.md
  - p73-truth-driven-engineering-pattern.md
  - p74-workflow-solidification-pattern.md
---

# P75 — CI Red Recursive Triage Pattern (CI 红递归分层诊断)

> **适用范围**: omostation CI 红 (`gh pr checks` fail) 的系统性诊断与修复. CI 红是 "递归洋葱" — 修一层暴露下一层, 单轮 CI 只报顶层.
>
> **实战来源**: PR#107 + PR#108 (2026-07-04) 修复 30+ 类 CI fail, 6 层递归到全绿.
> **关联**: [[ci-fix-recursive-layers]] / [[gac-gate-fail-diagnosis]] / [[aetherforge-workspace-transitive-dep]] / [[worktree-pr-landing-sop]]

## 1. 触发场景

任一即触发 P75 诊断:

1. `gh pr checks <PR> | grep fail` 非空 (PR CI 红).
2. main 分支 CI 红 (`gh run list --branch main` 含 FAIL).
3. 本地 gate (`gac-local-gate`) FAIL 但不知根因.

## 2. 六层递归诊断 (PR#107+#108 实战层序)

CI fail 按 "洋葱剥层" 诊断. 每修一层 → push → CI 暴露下一层. **不要只修一层** (会反弹):

| 层 | 典型 fail | 诊断 | 修复模式 |
|---|---|---|---|
| **L1 配置根因** | `No solution` / `ModuleNotFound` / `invalid input` | pyproject `uv.sources` / workflow `with:` | 显式依赖 + path source / 删无效 input |
| **L2 子模块** | test assert / drift / import | `omo lint` / mutation-surfaces / **uv.lock tracked?** | registry 同步 / sync 逻辑 / **track uv.lock** |
| **L3 CI 环境** | `PYTHONPATH` 缺包 / `set -e` 中断 / `.omo/tests` 缺 | `verify-omo.sh` 段 python 差异 / step 缺 `\|\| true` | `pip install` 补全 / `skip if absent` / `\|\| true` |
| **L4 lint 噪音** | SC2086 / F841 / MD031 | shellcheck severity / ruff ignore / markdownlint | `--severity=error` 聚焦 / ignore 一致 / 格式 |
| **L5 生成器格式** | 自动注入段 MD004/031 | consensus-inject 输出 `*` / 引用 fence | **修生成器** (非修输出, 避免下次覆盖) |
| **L6 本地工具** | `--directory` 绝对路径 CI 无 | evidence-smoke 绝对路径 | `local-only` (诚实区分本地工具 vs 真鸿沟) |

## 3. 真假 fail 区分 (P73 truth-driven)

每个 fail 先判定 (避免瞎修):

- **真 bug (引入)**: 我改的文件相关 + main 绿 → **立即修**.
- **预存 (主仓同红)**: `gh run list --branch main` 同 FAIL → 修或 admin merge (§7 三条件).
- **环境 (CI 独有)**: 本地 PASS / CI FAIL (tracked 运行快照 / 子模块 checkout / 本地工具) → **降级** (git fallback / local-only) 或 CI 适配.

## 4. 工具链

```bash
gh pr checks <PR> --repo <repo> | grep -i fail              # fail 列表
gh run view <run-id> --repo <repo> --log-failed | grep -iE "error|fail|SC|MD|assert|ModuleNotFound"  # fail log
gh run list --branch main --repo <repo>                     # 预存判定
# 本地复现:
uv run --project projects/<sub> python -c "import <pkg>"    # resolve 验证
uv run --project projects/<sub> pytest tests/<test> -q      # test 复现
uv run --directory projects/agora python bin/gac/evidence-smoke.py --gate 95  # evidence
uv run --with pyyaml python bin/gac/gac-local-gate.py --scope staged --json   # 本地 gate
```

## 5. 陷阱表 (PR#107+#108 实战, 7 类高发)

| 陷阱 | 症状 | 本轮案例 |
|---|---|---|
| **D1** uv.lock gitignored | CI 无 lock, uv sync 不装依赖 | omo `.gitignore L17 uv.lock` (CI ModuleNotFoundError pydantic, 本地 OK 因 uv run 自动更新 lock 没 commit) |
| **D2** PYTHONPATH 系统 python 缺包 | verify-omo `[N/5]` 段 python 切换 | `[3/5]` 用 `PYTHONPATH python3` (缺 pydantic/pytest), `[2/5]` 用 `uv run` (venv) |
| **D3** set -e 中断 | 某 lint exit 1 静默, 后续没跑 | interface-check `governance surfaces` exit 1 致 pytest 没跑 (命令 echo 显示但执行不到) |
| **D4** workspace 传递不暴露 | `aetherforge-gateway not found` | omo 缺 `aetherforge` 顶层包 (见 [[aetherforge-workspace-transitive-dep]]) |
| **D5** tracked 运行快照 stale | CI 拿 commit 旧值误判过期 | R-GOV-3 `governance_feedback_last_run` / health.yaml `generated_at` (>24h, 本地服务新鲜) |
| **D6** 生成器输出格式 | 自动注入段 lint fail | consensus-inject `*` (MD004) / 引用内 ``` (MD031) — 修生成器非修输出 |
| **D7** 本地绝对路径 | CI 无本地工具 | evidence `--directory ~/ToolBox/bos-skill-cli` (本地工具不入 repo) |

## 6. 修复决策树

```
CI fail
├─ grep ParserError / ModuleNotFound / No solution? → L1 配置 (pyproject / uv.sources)
├─ test assert / drift / import (本地 test 也 fail)? → L2 子模块 (registry / sync / uv.lock tracked?)
├─ PYTHONPATH / set -e 中断 / .omo 缺? → L3 CI 环境 (pip install / || true / skip)
├─ SC / F / MD lint? → L4 lint (severity / ignore / 格式)
├─ 自动注入段 (CLAUDE.md Onboarding 等)? → L5 生成器 (修生成器)
└─ 绝对路径 / 本地工具 (本地 0 gap, CI 1)? → L6 local-only
```

## 7. admin merge 三条件 (CI 非全绿时)

CI fail 非全绿但需 merge 时, 三条件**全部满足**才 admin merge:

1. **本地 GaC gate 绿** (`gac-local-gate --scope staged --json` ok=True, 我改的部分全绿).
2. **CI fail 全预存/环境** (`gh run list --branch main` 同 FAIL, 或本地 PASS/CI FAIL 的环境差异).
3. **用户授权** (盲修/合并明确授权).

否则继续修 (按 §6 决策树). 见 [[worktree-pr-landing-sop]].

## 8. 反模式 (避免)

- **❌ 只修一层就 merge**: 下一层 fail 会反弹 (CI 又红).
- **❌ 盲目 --no-verify**: 绕 gate 不诊断根因 (除非 §7 三条件).
- **❌ 修生成器输出而非生成器**: 下次注入覆盖 (memory [[feedback-loop-recovery-generator-trap]]).
- **❌ 把本地绝对路径当 gap**: CI 无本地工具不是代码鸿沟 (D7).
- **❌ 忽略 uv.lock tracked**: gitignored lock 致 CI 无法重现 (D1).
