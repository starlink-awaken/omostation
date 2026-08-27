# KEMS Worktree 堆积问题调查报告

> Agent: akems-worktree-explorer | 日期: 2026-08-01

---

## 核心结论 (TL;DR)

**KEMS 任务没有专属 workflow，worktree 是 agent session 通过 `gac-worktree.sh claim <session>` 手动/半自动创建的。** session 命名 `kems-*` 是 agent 自己取的名字（不是系统强制），导致 22 个 worktree 里 20 个是 KEMS 相关。**清理机制存在但全部需要手动触发**，没有自动 cleanup 是堆积的直接原因。

---

## 1. Worktree 现状

```
总数: 22 worktree
├── 主仓: /Users/xiamingxing/Workspace (main)
├── KEMS 相关: 20 个 (ws-kems-* / ws-cockpit-kems-*)
└── 非 KEMS: 2 个 (ws-367ee3a1, ws-family-hub-pointer)
```

KEMS worktree 命名模式：
- `ws-kems-root-m24-20260731` → branch `work/kems-root-m24-preflight-20260731`
- `ws-cockpit-kems-m11-20260731` → branch `work/kems-m11-cockpit-graph-forecast-20260731`
- `ws-kems-cockpit-pointer-20260801` → branch `work/kems-cockpit-pointer-20260801`
- `ws-kems-production-handoff-pointer-20260801` → branch `work/kems-production-handoff-pointer-20260801`

**关键观察：** 同名 worktree 和 branch 并不一一对应 — session 名 (`ws-<session>`) 和 branch 名 (`work/<session>`) 是不同字符串。这说明 agent 创建 worktree 后可能改了 branch 名，或者通过不同路径创建。

---

## 2. Worktree 创建机制

### 2.1 主创建路径: `bin/gac/gac-worktree.sh`

**文件:** `/Users/xiamingxing/Workspace/bin/gac/gac-worktree.sh` (280 行)

```
用法:
  gac-worktree.sh claim <session>      # 创建 worktree + 分支 work/<session>
  gac-worktree.sh submit <session>     # push 分支 + 开 PR (base main)
  gac-worktree.sh merge <session>      # squash 合并 PR + release worktree + 删分支
  gac-worktree.sh release <session>    # 清理 worktree (手动, 合并后)
  gac-worktree.sh list                 # 列所有 worktree
```

**claim 流程 (line 41-118):**
1. 校验 session 名 (`[a-z0-9-]`)
2. G-CONV.7 D2 branch occupancy lock (`swarm-discipline-cli.py branch-claim`)
3. `git fetch origin main`
4. `git worktree add "$WS_PARENT/ws-$session" -b "work/$session" origin/main`
5. init 默认子模块 (projects/ecos, scripts, projects/omo, projects/cockpit, projects/agora)
6. ADR 占号提示

**worktree 落点:** `$WS_PARENT/ws-<session>` = `/Users/xiamingxing/ws-<session>`

### 2.2 Agent 技能路径: `using-git-worktrees` skill

**文件:** `~/.claude/skills/using-git-worktrees/SKILL.md`

- 优先用原生工具 (EnterWorktree, WorktreeCreate 等)
- 无原生工具时 fallback 到 `git worktree add`
- 默认目录: `.worktrees/` (项目内)
- **但 KEMS worktree 不在 `.worktrees/` 内，而是走 `gac-worktree.sh`**

### 2.3 Codex agent 路径

部分 branch 以 `codex/` 前缀命名:
- `codex/kems-root-runtime-handoff-20260801`
- `codex/kems-production-handoff-pointer-20260801-base`
- `codex/kems-production-closeout-pointer-20260801-base`
- `codex/kems-all-20260730`
- `codex/kems-pilot-20260730`

对应 worktree:
- `ws-cockpit-dual-claim-api-20260801` → branch `codex/kems-dual-claim-api-20260801`
- `ws-kems-cockpit-contract-20260801` → branch `codex/kems-cockpit-contract-20260801`

**说明 Codex agent 用自己的命名约定创建 worktree。**

### 2.4 Hook/自动化路径

**没有 hook 自动创建 worktree。** `.githooks/` 目录 (post-commit, pre-commit, pre-push, prepare-commit-msg-commit-assist) 不含 worktree 创建逻辑。

---

## 3. KEMS Task System

### 3.1 agent-workflows.yaml 中无 KEMS workflow

搜索 `kems` / `pointer` 在 `.omo/_truth/registry/agent-workflows.yaml` 中:
- `kems` → **0 命中**
- `pointer` → 仅出现在 `submodule-pointer-close` workflow (子模块指针关闭，与 KEMS 无关)

**结论：KEMS 不是agent-workflow 注册的正式 workflow。** 它们是 agent session 自己取名为 `kems-*` 的临时任务。

### 3.2 KEMS 命名约定

从 branch 名反推 KEMS 任务结构：
- `kems-root-mXX-<task>-<date>` — 根仓库任务 (m22-m37 系列 + 其他)
- `kems-cockpit-pointer-<date>` — cockpit 指针任务
- `kems-production-handoff-pointer-<date>` — 生产交付
- `kems-roadmap-<date>` — 路线图
- `kems-dual-adjudication-pointers-<date>` — 双重裁决

这些是 agent 自定义 session 名，不是系统强制命名空间。

---

## 4. 清理机制 (已存在但全部手动)

### 4.1 `gac-worktree.sh release <session>` — 手动清理单个

**文件:** `bin/gac/gac-worktree.sh` line 168-191

- G-CONV.7 D2 branch release
- `git worktree remove "$wt"`
- 分支保留 (注释提示手动 `git branch -D`)

### 4.2 `gac-worktree.sh merge <session>` — 合并时自动清理

**文件:** `bin/gac/gac-worktree.sh` line 193-258

- `gh pr merge --squash --delete-branch`
- `git worktree remove "$wt"`
- `git branch -D "$branch"`

**但 `--auto` 模式只 enable GitHub auto-merge，不立即清理。**

### 4.3 `bin/gac/gac-worktree-prune.sh` — 批量 patch-equivalent 清理

**文件:** `/Users/xiamingxing/Workspace/bin/gac/gac-worktree-prune.sh` (73 行)

- **默认 dry-run**，`--apply` 才真删
- 安全规则: 不碰 main、跳过 dirty (除非 `--force-dirty`)、跳过有 unique patch 的
- 判定: `git cherry origin/main "$br` → 无 `+` 行 = 已全在 main → 可删
- 执行: `git worktree remove --force "$wt"` + `git branch -D "$br"`

### 4.4 `compass_radar.py` — orphan 自动清理

**文件:** `/Users/xiamingxing/Workspace/bin/compass_radar.py` line 140-191

- `_count_orphan_worktrees()`: 统计 record 在但目录已删的 orphan
- `_prune_orphan_worktrees()`: `git worktree prune` 清 record
- 在 `run_radar()` 生成 health 前自动调用 (line 482-483)
- **只清 orphan record，不删有效 worktree**

### 4.5 P72 Pattern — 原则 7 退场清残

**文件:** `.omo/_knowledge/patterns/p72-follow-up-completion-pattern.md`

明确原则 7: "合并后 release worktree + 删本地+远 branch"，但这是**行为规范**非自动执行。

---

## 5. 堆积根因分析

| 因素 | 说明 |
|------|------|
| **无自动 cleanup** | 所有清理机制都需手动触发，无 cron/daemon/auto-release |
| **agent 习惯** | KEMS 任务创建 `work/kems-*` 分支 + worktree 后，任务完成 → 忘记 release |
| **分支命名不一致** | session 名和 branch 名不同，release 时可能找不到对应关系 |
| **Codex agent** | 部分 worktree 由 Codex 创建，可能不遵循 GaC 清理流程 |
| **`--auto` merge** | auto-merge 只 enable GitHub 自动合，不触发本地 cleanup |
| **无 worktree 数量上限** | 系统无 worktree 压力阈值自动清理 (compass_radar 只记 metric 不 action) |

---

## 6. 关键文件清单

| 文件 | 角色 |
|------|------|
| `bin/gac/gac-worktree.sh` | **worktree 创建/提交/合并/释放主脚本** |
| `bin/gac/gac-worktree-prune.sh` | 批量 patch-equivalent worktree 清理 (dry-run 默认) |
| `bin/compass_radar.py` | orphan worktree 检测 + 自动 prune (仅 record) |
| `bin/gac/swarm-discipline-cli.py` | branch occupancy lock (G-CONV.7 D2) |
| `.omo/_knowledge/patterns/p72-follow-up-completion-pattern.md` | 原则 7: 退场清残行为规范 |
| `docs/AGENT-ISOLATION-ROLLOUT.md` | worktree 隔离落地方案文档 |
| `~/.claude/skills/using-git-worktrees/SKILL.md` | Agent worktree 创建技能 |

---

## 7. 建议方向 (不在本任务执行)

1. **立即清理**: `bash bin/gac/gac-worktree-prune.sh --apply` 批量清已合并 worktree
2. **自动 cleanup hook**: post-merge hook 检测 `work/*` 分支是否已 squash-merged → 自动 release
3. **worktree TTL**: compass_radar 加 `wt_age_days > 7` 自动 prune 逻辑
4. **agent 行为规范**: KEMS 任务结束时强制 `gac-worktree.sh release`
