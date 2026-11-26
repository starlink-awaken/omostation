---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-356
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-26
accepted: "2026-11-26 Principal 会话拍板「a」— 债 CRON-CAPABILITY-SYNC-MAIN-DIRECT-COMMIT 三选一修法裁定 (worktree + 自动 PR 化, 先例 #4858)"
title: capability-registry-sync-daily 断根 —— 主仓直提改 worktree+自动PR
created: 2026-11-26
owner_decision: >-
  债 CRON-CAPABILITY-SYNC-MAIN-DIRECT-COMMIT 三选一修法, owner 2026-11-26 拍板
  (a): worktree + 自动 PR 化 (先例 83c23e1aa / PR #4858)。
---

# BET-Y2Q4-T10-356: cron 主仓直提断根 (worktree + 自动 PR)

## 背景与问题

`.omo/cron/registry.yaml` 的 `capability-registry-sync-daily` (每日 04:05) 命令链:
`cd "$HOME/Workspace" && 生成器 && git add && git commit` —— 设计即主仓 main 直提。
2026-11-26 04:05 实测: push 失败滞留 1 提交 + main 分叉 31 提交, 人工恢复
(tag `cleanup-archive/bad-epoch-sync-488d737ca` 存证)。不修则每日复发。

## 方案 (owner 裁定 a)

### 1. 生成器加 `--publish` 模式 (`bin/ssot/gen-capability-registry.py`)

新增 `publish_via_pr()`, 流程全程**不碰主仓工作区**:

```
fetch origin main
  → 临时 worktree (tempfile.mkdtemp, 基于 origin/main, 分支 auto/capability-sync-YYYYMMDD)
  → worktree 内重跑自身生成 (WORKSPACE 锚 __file__, 自动锚定 worktree 根)
  → git add 三路径 (capability-registry.yaml + INDEX-MCP.md + CLI-REFERENCE.md, 同旧面)
  → diff --cached --quiet == 0 → 无漂移, 清理收工 rc=0
  → 有 diff → commit ("chore(auto): capability-registry daily sync (YYYY-MM-DD)",
     不带 [skip ci] —— required checks 需真跑才能 auto-merge)
  → push -u origin <branch>
  → gh pr create --base main
  → gh pr merge --squash --auto --delete-branch (repo 未启用 auto-merge 时挂起等人, 可接受降级)
  → finally: worktree remove --force + 本地分支 -D
```

失败哲学: 任一步失败 → 清理 worktree → 非零退出 → cron 日志留痕; **绝不回退直提主仓**。
subprocess env 显式前置 /opt/homebrew/bin (cron PATH 精简, gh 在 homebrew)。
生成器保持 stdlib-only (新增 import: os/tempfile/datetime)。

### 2. cron 声明换链 (`.omo/cron/registry.yaml`)

command 改为:
`cd "$HOME/Workspace" && /opt/homebrew/bin/python3.13 bin/ssot/gen-capability-registry.py --publish >> runtime/cron/capability-registry-sync.log 2>&1`

改后用 `bin/ops/install-cron-plane.py --install` 重装本机 crontab 装载面
(安装器按调用点解析解释器, 声明面/装载面语义见 ADR-A / ADR-0119)。

### 3. 债条目 resolve (`.omo/debt/items/CRON-CAPABILITY-SYNC-MAIN-DIRECT-COMMIT.yaml`)

- lifecycle_state: identified → resolved
- history 追加: owner 裁定 (a) 于 2026-11-26, 本 BET 落地
- 次生病 (frontmatter last-reviewed 被生成重置) 定性为设计内行为收尾:
  sentinel 设计下生成物归机器权威, 人工审阅标记应记 debt/registry 而非生成物
  frontmatter, 不另立债。

## 验收标准

1. `python3 -c "import ast; ast.parse(open('bin/ssot/gen-capability-registry.py').read())"` 通过。
2. 既有模式回归: `--check` / `--json` / `--verify` 入口行为不变 (argparse 分支独立)。
3. `--publish` 端到端真跑一次:
   - origin/main 无漂移 → 输出无漂移跳过, rc=0, worktree 清理干净;
   - 有漂移 → PR 创建成功, squash --auto 使能, 主仓工作区 git status 零污染。
4. `install-cron-plane.py --install` 后 `crontab -l` 证实新命令链装载, 旧直提链消失。
5. 台账 604 bets, 本 spec digest 绑定。

## 非目标

- 不动 ADR-0373 sentinel (generated_at 1970 有意设计)。
- 不做 auto-merge 不可用时的兜底自动合并 —— PR 挂起等人审是可接受降级。
- 不解决 INDEX-MCP.md frontmatter 人工标记持久化 (定性设计内, 见方案 3)。
- 不改 gen-help-docs.py / post-commit-sync-check.py 的既有职责边界。

## 风险与回退

- cron 环境 keychain 锁 → gh 认证失败: 日志留痕, 分支已 push 远端不丢失, 人工收。
  验证阶段实测 cron PATH/keychain 行为。
- auto/capability-sync-* 分支日积: auto-merge 正常时不积压; 若挂起, 人工批量处理。
- 回退: revert 本 PR 即回旧直提链 (可接受, 债重开)。
