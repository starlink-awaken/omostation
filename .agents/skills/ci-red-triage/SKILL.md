---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
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
- **预存 (主仓同红)**: main 同 FAIL → **修或登记 skip-layer known-debt**（`.omo/_truth/registry/gate-known-debt.yaml`，owner+过期）。不要默认 `--no-verify` / admin merge。GitHub admin merge 仍受 §5 三条件约束，且本轮 D4 固化不接线 `surface=github`。
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

**markdownlint 的实际口径**（L4/L5 高发误判）：本仓的 markdown lint 是 **Python `pymarkdown`**
（`.pre-commit-config.yaml` 的 `markdownlint` hook：`uv run --with pymarkdownlnt pymarkdown scan`），
**不是** node `markdownlint-cli` —— 后者会对同一文件报一批 `MD060` 之类本仓不承认的 rule，属于工具用错。
且该 hook 的 `files:` 只匹配 `^(README|CLAUDE|AGENTS|ARCHITECTURE|LAYER-INDEX)\.md$`，
`docs/**` 与 `.omo/**` **故意不 lint**（"详细文档格式灵活不 lint"）：对 `docs/` 下的文件跑 lint 报出来的
错，不是 CI 会拦的错。判 fail 归属前，先读 `.pre-commit-config.yaml` 里该 hook 的 `files:`。

### 3. Verify local (复现 + 验证修复)

```bash
uv run --project projects/<sub> python -c "import <pkg>"   # resolve 验证
uv run --project projects/<sub> pytest tests/<test> -q     # test 复现
uv run --directory projects/agora python bin/evidence-smoke.py --gate 95  # evidence
uv run --with pyyaml python bin/gac/gac-local-gate.py --scope staged --json  # 本地 gate
```

### 4. Commit + PR (per worktree-pr-landing-sop)

- **change-lane 拆 commit**: governance_state / CI config / submodule_pointer 分开 (单 lane 放行)
- `--no-verify` 仅限 submodule_pointer_drift bump 中间态 (非绕 gate)。预存失败走 known-debt / `local-preflight-preexisting`，agent 禁止 `emergency-human-hotfix`
- push → CI → 递归 (回到 §1, 直到全绿)

### 5. Admin merge —— 作用域只有**非必需检查**，不是"CI 红的逃生口"

先分清红的是哪一类检查，再决定 §5 能不能用。本仓 main 分支保护实测
（`gh api …/branches/main/protection` + `/required_status_checks` + `/enforce_admins`，2026-09-25）：

| 事实 | 值 |
|------|-----|
| `enforce_admins.enabled` | **true** |
| required contexts | **3 条**：`phase-gate` / `bet-done-transition` / `gac-gate` |
| 单个 PR 上的检查名总数 | 31（#4346 实测去重） |

`--admin` 只绕过那 **28 条非必需**检查；`enforce_admins=true` 的含义正是 **required 那 3 条对 admin 同样硬**。

三条件（全部满足才走）：

1. 本地 GaC gate 绿 (`gac-local-gate --scope staged --json` ok=True)
2. CI fail 全预存/环境 (main 同红 或 本地 PASS/CI FAIL)
3. 用户授权 (盲修/合并明确)

→ `gh pr merge <PR> --admin --squash`. 否则继续 §2。

**红落在 required 3 条里 → §5 结构性不可用，不要试**（下方一条实证拒绝）。剩余两条路：

- **main 侧修**：required 红的根因常不在本分支（陈旧 base / gitlink 不可达）。
  `gh pr update-branch` 重生成 merge ref 即可消掉，**不必动本分支任何文件**。
- **known-debt 登记**：`.omo/_truth/registry/gate-known-debt.yaml`（owner + 过期）。
  其 escape 是 `SWARM_ESCAPE_ID=local-preflight-preexisting && human_gate` ——
  **human_gate 那半边 agent 不能自签**，缺它就是自签豁免。

> 实证（#4346，2026-09-25）：`gh pr merge 4346 --admin --squash` 被拒
> `Required status check "gac-gate" is failing`。根因是 main 侧 omlxc gitlink 不可达，
> 本分支 6 个文件零 `.py` 零 gitlink，与这条红无因果。另一 agent 在 main 重新 pin 可达
> commit 后 → `gh pr update-branch` → `gac-gate` 转绿 → 普通 `--squash` 合并。
> 本 §5 此前把 `--admin` 写成 CI 非全绿时的通用出口，是错的。

## 7 Pitfalls (PR#107+#108 实战, 高发)

- **D1** uv.lock gitignored → CI 无 lock, uv sync 不装依赖 (omo .gitignore uv.lock)
- **D2** verify-omo `[N/5]` 段 PYTHONPATH 系统 python 缺包 (uv run 段 venv, PYTHONPATH 段系统)
- **D3** step set -e + lint 无 `|| true` → 某 exit 1 静默中断 (governance surfaces 致 pytest 没跑)
- **D4** workspace `{workspace=true}` 传递不暴露 (omo 缺 aetherforge 顶层包)
- **D5** tracked 运行快照 (governance_feedback_last_run / health.yaml generated_at) CI stale
- **D6** 生成器输出格式 (consensus-inject `*` MD004 / 引用 ``` MD031)
- **D7** 本地绝对路径 (evidence `--directory ~/ToolBox/`) CI 无
- **D8** 门禁 `TIMEOUT after 15s` / `returncode=-1` = **假红**：冷 worktree 首跑 env 解析吃满预算。
  判归属前先单独给该 checker 计时跑一遍（`bin/gac/<check>.py` 直跑），别把 `-1` 当 fail

详见 p75 pattern §5.

## Anti-patterns

- ❌ 只修一层就 merge (下一层反弹)
- ❌ 盲目 `--no-verify` 或把预存 CI 红当成可以忽略的背景（不诊断根因、不登记 fingerprint 债）
- ❌ 修生成器输出而非生成器 (下次注入覆盖)
- ❌ 本地绝对路径当 gap (CI 无本地工具不是代码鸿沟)
- ❌ 忽略 uv.lock tracked (gitignored lock 致 CI 无法重现)
