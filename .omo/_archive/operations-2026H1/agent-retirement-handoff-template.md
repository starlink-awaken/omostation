---
type: standard
owner: governance-team
created: 2026-08-15
lifecycle: contract
related:
  - docs/reports/2026-08-15-multi-repo-collab-retro-v2.md (E7)
  - .omo/standards/agent-workflow-contract.md
last_updated: 2026-08-18
title: Agent 退役交接模板（E7 根治）
---

# Agent 退役交接模板（E7 根治）

> **Agent 停工前必须填写此清单，确保无孤儿资源遗留。**
> 
> 填写完成后提交到对应 workflow 的 closeout 附件，或在 PR body 中粘贴。

## 前置条件

- ✅ 所有活跃 claim 已 close / 已转交
- ✅ 所有活跃 workflow run 已 verify / 已转交
- ✅ 所有未推送 commit 已推送或明确废弃

---

## 一、在途 Worktree 清单

| Worktree 路径 | 分支 | 状态 | 用途 | 处置 |
|--------------|------|------|------|------|
| `~/Workspace/.git/worktrees/<name>` | `feature/foo` | `dirty/clean` | BET-Y1Q1-T1-05 | 已提交 PR #1234 / 已删除 |
| （无） | — | — | — | — |

**填写说明**：
```bash
# 列出所有 worktree（包括主仓和子模块）
git worktree list --porcelain
find .git/modules -name "gitdir" -exec cat {} \; 2>/dev/null | while read gitdir; do
  basedir=$(dirname "$(dirname "$gitdir")")
  git -C "$basedir" worktree list --porcelain
done
```

---

## 二、在途 Orca Worker 清单

| Terminal Handle | 用途 | 是否可回收 | 备注 |
|-----------------|------|------------|------|
| `orca-term-001` | blueprint-control-loop 执行器 | ✅ 可回收（任务已完成） | 48h 后未活动则自动清理 |
| `codex-worker-bar` | 文档生成专用 | ❌ 暂保留（SR-06b 使用中） | 已标注用途，接手人确认 |
| （无） | — | — | — |

**填写说明**：
```bash
# 列出所有 Orca 终端/worker
orca terminal list
```

**回收规则**：
- 孤儿 worker 超过 48 小时未活动 → 可直接回收
- 有明确任务标注的 → 留给接手人评估

---

## 三、活跃 Claim / Workflow Run 清单

| Claim ID / Run ID | 状态 | 用途 | 处置 |
|-------------------|------|------|------|
| `bet-ledger claim T9-01` | `in_progress` → 已转交 `agent-blueprint` | 子模块指针更新 | 接手人已确认 |
| `workflow run xxx` | `verified` → 已 closeout | 场景卡验证 | 无遗留 |
| （无） | — | — | — |

**填写说明**：
```bash
# 列出活跃 claim
uv run --with pyyaml python bin/plan/bet-ledger.py status | grep "in_progress"

# 列出活跃 workflow run
uv run --with pyyaml python bin/agent-workflow.py status
```

---

## 四、未推送 Commit 位置

| 仓库 | 分支 | 未推送 Commit SHA（若有） | 处置 |
|------|------|--------------------------|------|
| `~/Workspace` (主仓) | `work/e7e8-fixes` | `a1b2c3d` (仅此 PR 的修改) | 已在 PR #1512 |
| `projects/omo` | `feature/coordination` | 无 | — |
| （无） | — | — | — |

**填写说明**：
```bash
# 检查未推送 commit
git log --branches --not --remotes --oneline

# 子模块同理（需 cd 进去）
cd projects/omo && git log --branches --not --remotes --oneline
```

---

## 五、接手人第一步命令

接手人认领此 agent 遗留任务时，**按顺序执行以下盘点命令**：

### 5.1 验证 Worktree 状态

```bash
# 主仓 worktree 清单
git worktree list --porcelain

# 子模块 worktree 清单
find .git/modules -name "gitdir" -exec cat {} \; 2>/dev/null | while read gitdir; do
  basedir=$(dirname "$(dirname "$gitdir")")
  echo "=== $basedir ==="
  git -C "$basedir" worktree list --porcelain
done
```

### 5.2 验证 Orca Worker 存活

```bash
orca terminal list
# 检查每个 terminal 的 last_activity，超 48h 标记为可回收
```

### 5.3 验证 Claim / Workflow 状态

```bash
# 活跃 claim
uv run --with pyyaml python bin/plan/bet-ledger.py status | grep "in_progress"

# 活跃 workflow run
uv run --with pyyaml python bin/agent-workflow.py status
```

### 5.4 验证未推送 Commit

```bash
# 主仓
git log --branches --not --remotes --oneline

# 子模块（遍历）
for sub in projects/*; do
  [ -d "$sub/.git" ] || continue
  echo "=== $sub ==="
  git -C "$sub" log --branches --not --remotes --oneline
done
```

### 5.5 检查孤儿 venv / 缓存（E8 补充）

```bash
# 列出 ~/agents/ 下所有 venv（检测无主残留）
ls -la ~/agents/*/ws/.venv 2>/dev/null | while read line; do
  echo "$line"
  # 检查对应的 agent clone 是否还有 identity
  agent_dir=$(echo "$line" | cut -d/ -f1-4)
  [ -f "$agent_dir/ws/.git/agent-clone-identity.json" ] || echo "警告: 无 identity venv → $line"
done
```

---

## 六、签署确认

- **填写人**：`<agent-id>` / 人类填写时填姓名
- **填写时间**：`<ISO-8601 timestamp>`
- **接手人**：`<agent-id 或 "待认领">`
- **接手时间**：`<ISO-8601 timestamp 或 "待认领">`

---

## 示例：2026-08-15 blueprint-agent-governance 退役案例

**事故背景**：前任 agent 暴毙，`ws-blueprint-agent-governance` 目录无痕消失，Orca codex worker 存活但无人知晓，T1-18 任务卡 in_progress。

**若按此模板填写**：
- Worktree：`~/Workspace/.git/worktrees/blueprint-governance` (已删除，需人工重建)
- Orca Worker：`codex-worker-blueprint` (存活，标记为 SR-06b 复用)
- Claim：`T1-18` (in_progress，接手人已认领)
- 接手人运行 `orca terminal list` → 发现孤儿 worker → 复用作演习 executor

**成本对比**：
- 无模板：接手人手动翻找，耗时 ~60min，部分资源永久遗漏
- 有模板：接手人按命令执行，5 分钟完成盘点，零遗漏

---

## 强制执行（ADR-0203 红线）

从 2026-08-21 T1-05A 收口开始：
- Agent 停工前未填写此清单 → workflow verify 失败
- 人类直接终止 agent → 需事后补填（复盘审计项）
