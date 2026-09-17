---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-17
type: ssot
---

# PR Retry SOP — CI Fail 时的决策树

> 源自 4014-4018 三轮 PR retry 实证收编. PR #3811 → #3827 → #3829 反复重开
> 暴露三个反复栽跟头模式 (PITFALL-COO-004/005/006). 本 SOP 把"PR fail 怎么办"
> 焊成 5 步决策树, 避免"close + 重开"成为默认反应 (那是最贵的错路).

## 反模式 (禁止)

- ❌ **看到 CI fail → 直接 close + 重开新 PR** (4014 #3811 实证: 浪费 1 天窗口)
- ❌ **看到 CI fail → 第一次提交就开始改自己代码** (可能不是本 PR 引入)
- ❌ **用 `git cherry-pick <old_commit>` 重放到新 base** (PITFALL-COO-005: 带 parent reverse)
- ❌ **看本地工作树判断 main 状态** (PITFALL-COO-006: 本地 ≠ origin/main)

## 5 步决策树

```
PR CI fail
│
├─ 1. 抓 fail step log
│     gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs
│
├─ 2. fail 文件是 gitlink 子模块?
│     ├─ YES → 见 PITFALL-COO-004, 跳到分支 4
│     └─ NO  → 进入 3
│
├─ 3. 看 PR diff 文件清单, fail 文件在本 PR 改动里?
│     ├─ YES → 修自己代码, 重新提交
│     └─ NO  → 进入 4
│
├─ 4. 看近 5-10 个 PR 同 lint 状态
│     gh pr checks <PR> | grep <lint>
│     重复跑 N 个 PR
│     ├─ 都 fail (= pre-existing 累计违规) → 不要 close PR, 加:
│     │   ## Known pre-existing failures (unrelated)
│     │   让人审能进 PR, 跟本 PR 无关
│     └─ 仅本 PR fail → 修自己代码
│
└─ 5. 重放改动时:
     ├─ 不要 cherry-pick 整个 commit (PITFALL-COO-005)
     │   cherry-pick 会带 parent 的 reverse 到 target base, 制造
     │   "删掉 main 上已合入内容" 的反向删除
     └─ 用 git show <old>:<path> 拿文件 + 在新 base 重做改动
        然后 git diff origin/<base>..HEAD --name-status 验证
        出现 "D" 行立即 git reset --hard origin/<base> 退回
```

## 关键工具 (配套本 SOP)

| 工具 | 用途 |
|---|---|
| `bin/gac/sync-main.sh` | 开工第一步: fetch + reset + submodule update. 防 PITFALL-COO-006 |
| `git fetch origin main && git reset --hard origin/main` | 任何 "main 是不是这样" 判断前必跑 |
| `git diff origin/main...HEAD --name-status` | cherry-pick 后立即验证无 reverse delete |
| `gh pr checks <PR> --json state,statusCheckRollup` | 跨 PR 看同 lint 状态, 排查 pre-existing |

## 实战模板 (PR body 加这一段)

```markdown
## Known pre-existing failures (unrelated)

本 PR 触发以下 lint fail, 但经排查都是 main 上**累积的 pre-existing 违规**,
跟本 PR 改动 4 文件 (`*.md`, `bin/*.py`) 完全无关:

- `interface-check`: fail 在 `projects/cockpit/src/cockpit/console/*.py` (子模块),
  近 5 个 PR #3815/#3816/#3817/#3818/#3819 同样 fail, pre-existing.
- `check-cross-refs`: 12 个文件 19 个 broken link 都在 `.omo/_truth/governance-evidence/waiver-*`,
  引用历史已删的 submodule 路径, 跟本 PR 无关.

## Test plan

- [x] `python3 bin/ssot/doc-ssot-lint.py --json` — pass
- [x] `make gac-local-gate` — pass (排除 pre-existing 已知问题)
```

## 相关 pitfall

- **PITFALL-COO-004** (medium): PR CI lint fail 不一定是本 PR 引入 — 子模块 pre-existing
- **PITFALL-COO-005** (high): cherry-pick 跨 base 重放带 parent reverse
- **PITFALL-COO-006** (medium): 本地工作树 ≠ origin/main 状态

## 验证

```
$ python3 bin/plan/bet-ledger.py lint
OK -- 419 bets, 14 tracks, no errors
```

## 参考

- 4014 PR #3811 (close + rebase retry) → #3827 (cherry-pick 失败) → #3829 (redundant, 已合) → #3839 (教训固化)
- 4018 PR #3839 (PITFALL-COO-004/005/006 入 INDEX.md)
- 4019 PR #3848/#3849/#3854 (3 lane 并行, 各 verify 后 commit, 不撞车)