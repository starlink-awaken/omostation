# BET-Y1Q1-T1-07 实施计划 — git 入口收口（PATH shim 强制 swarm-git）

> 认领前全面分析 → 用户选方向 B（先建注入机制，完整做 4 条 done_when）
> appetite: 3 days | risk: L2 | profile: governance-agent | workflow: bet-execution

## Context（为什么做这个）

D4 escape-hatch 有个**设计者已知的缺口**（`swarm-coordination.yaml::gates.d4_escape_hatch.entry` 原文："Bare git --no-verify still skips hooks by git design"）：`bin/gac/swarm-git` 会校验 `SWARM_ESCAPE_ID` 白名单 + 写 `.omo/_delivery/swarm-escape/` 台账，但 raw `git` 仍在 PATH 中，agent 用 `git --no-verify` 零成本绕过。实测 2026-08-06 提交 `49d3ffed5` 就这么干的（escape_id 不在白名单，台账无记录）。

**目标**：把「记得用 wrapper」变成「只有 wrapper 可用」——agent 环境 PATH 前置 shim，让 `git` → `swarm-git` 强制；同时补 swarm-git 对高危操作（`clean -fd`/`reset --hard`/`stash -u`/共享分支 `rebase`）的拦截（当前只拦 `--no-verify`）。

## 认领前分析的关键发现（Q3 打假，影响方案）

1. **done_when 假设的 `~/agents/<id>/bin/` 不存在**（只有 `~/.agents/`，无 per-agent bin）—— 需**新建**
2. **AGENT_ID 运行时不注入**（grep 全仓 + env 实测，OMC/Claude Code 都不设）—— 需**新建注入机制**
3. **swarm-git 当前只拦 `--no-verify`**（bin/gac/swarm-git:23-47），不拦 clean/reset/stash/rebase；swarm_discipline.py 无 `argv_has_dangerous`
4. **settings.json env 字段存在**（25+ keys），可注入 AGENT_ID + PATH —— 注入机制可行
5. **agent definition frontmatter 无 env 字段** —— per-agent AGENT_ID 不支持，只能全局（区分 agent session vs 人类终端已足够）
6. **settings.json env 只影响 Claude Code session**，人类终端 shell 不读它 → **circuit_breaker 天然**（人类 PATH 无 shim + 无 AGENT_ID）

用户选 B：先建注入机制，T1-07 完整做。因此 write_surfaces 扩展含 `~/.claude/settings.json` + `~/agents/<id>/bin/`（原 write_surfaces: bin/gac/swarm-git, bin/gac/**, AGENT-BRIEF.md, AGENTS.md）。

## 方案（4 部分，对齐 4 条 done_when）

### 1. swarm-git 扩展拦高危（done_when 第 2 条）— 先做，独立可验证
- `bin/gac/swarm_discipline.py`：新增 `argv_has_dangerous(argv)` —— 检测 `clean -fd`/`clean -fdx`/`reset --hard`/`stash -u`/`stash --include-untracked`/共享分支（main/master）`rebase`。模板照抄 `argv_has_no_verify`（第 686 行）+ `check_git_argv_escape`（第 702 行）
- `bin/gac/swarm-git`：在 `--no-verify` 检查（第 23-47）后，加高危 argv 分支 → 调 `argv_has_dangerous` → 命中则 `exit 1`（写 `swarm-escape` 台账记 `dangerous_block`，或 emit_conflict_event）。**高危无 escape**（non_goals 不新增审计维度，agent 禁做这些操作）
- 共享分支 rebase 判定：argv 含 `rebase` + 当前分支 ∉ `work/*|pr/*` → 拦（参考 .githooks/pre-push:42-43 的分支判断）

### 2. shim 脚本（done_when 第 1 条的 shim 侧）— bin/gac/git-shim（新）
```bash
#!/usr/bin/env bash
# agent git shim: AGENT_ID 空→透传 real git; 非空→swarm-git
set -euo pipefail
if [ -z "${AGENT_ID:-}" ]; then exec /usr/bin/git "$@"; fi
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$ROOT" ] && exec /usr/bin/git "$@"
exec "$ROOT/bin/gac/swarm-git" "$@"
```
- 放 `bin/gac/git-shim`（write_surfaces 内），chmod +x
- **circuit_breaker 在此层**：AGENT_ID 空（人类终端）透传，非空（agent session）走 swarm-git

### 3. 注入机制 + 安装（done_when 第 1 条的 runtime 侧）— 用户选 B 的核心
- **`~/.claude/settings.json::env`** 加：
  - `AGENT_ID`: `"claude-code"`（全局，区分 agent session vs 人类终端）
  - `PATH`: 前置 `$HOME/agents/shim/bin`（共享 shim 目录，不 per-agent，因 frontmatter 不支持 per-agent env）
- **shim 安装目录**：`~/agents/shim/bin/git` → symlink 到仓库 `bin/gac/git-shim`（claim worktree 后在 worktree 写 git-shim，安装时 symlink）。**不 per-agent**（frontmatter 限制），全局共享一个 shim（AGENT_ID 全局值足够 circuit_breaker）
- **多 runtime 覆盖**：本次先 Claude Code（settings.json）。Cursor/OMC/自建 runtime 的等价配置写进 AGENT-BRIEF 备注（各自 env 注入机制），标"后续扩"
- **PoC 前置**：改 settings.json 前先在一个 scratch session 验证 env 注入生效（`echo $AGENT_ID` 非空 + `which git` 指 shim），再正式改

### 4. 文案（done_when 第 4 条）
- `docs/plans/AGENT-BRIEF.md` §8 禁止清单 + §3 新增「逃生口只有 swarm-git 一个入口，raw `git --no-verify` 被 PATH shim 拦截」
- `AGENTS.md` §1.6 / §6.1 同步补 PATH shim + 高危禁做（clean/reset/stash/rebase 现在有强制拦截，不只是规劝）

## 改动面（write_surfaces 扩展，用户授权 B）

| 文件 | 改动 | lane |
|---|---|---|
| `bin/gac/swarm_discipline.py` | + `argv_has_dangerous()` + 危险检测辅助 | code |
| `bin/gac/swarm-git` | + 高危 argv 拦截分支 | code |
| `bin/gac/git-shim`（新） | shim 脚本（AGENT_ID circuit_breaker） | code |
| `docs/plans/AGENT-BRIEF.md` | 文案（逃生口 + 高危禁做） | docs |
| `AGENTS.md` | 文案同步 | docs |
| `~/.claude/settings.json`（超原 write_surfaces） | env 加 AGENT_ID + PATH 前置 | config（用户全局配置，改前确认） |
| `~/agents/shim/bin/git`（超原 write_surfaces） | symlink → bin/gac/git-shim | 安装产物 |

跨 code+docs lane → 拆 2 commit（各单 lane）；settings.json + symlink 是安装步骤（交付时 human 确认）。

## 验证（done_when 4 条 + verify 2 条）

```bash
# 1. verify 第1条: raw git --no-verify 被 shim 拦
AGENT_ID=probe SWARM_ESCAPE_ID=bogus git commit --no-verify --allow-empty -m probe
# 期望: 非0 (shim → swarm-git → escape-check 拒 bogus)

# 2. verify 第2条: 台账 +1
ls .omo/_delivery/swarm-escape/ | wc -l   # 逃生前后对比 +1

# 3. done_when 第2条: 高危被拦
AGENT_ID=probe git clean -fd /tmp/test   # 期望非0
AGENT_ID=probe git reset --hard          # 期望非0
AGENT_ID=probe git stash -u              # 期望非0

# 4. circuit_breaker: AGENT_ID 空透传 (人类)
env -u AGENT_ID git status               # 期望正常 (透传 real git)

# 5. 单测: swarm_discipline argv_has_dangerous
cd projects 2>/dev/null || true
python3 -c "import sys; sys.path.insert(0,'bin/gac'); from swarm_discipline import argv_has_dangerous as f; \
  assert f(['clean','-fd']); assert f(['reset','--hard']); assert f(['stash','-u']); \
  assert f(['rebase','main']); assert not f(['status']); assert not f(['clean','-n']); \
  print('PASS')"

# 6. gate 自检
make gac-local-gate
```

## 风险 + circuit_breaker

- **settings.json 改动影响所有 Claude Code session** → circuit_breaker: shim 层判 AGENT_ID 空（人类终端）透传。**PoC 验证后再改正式 settings.json**
- **AGENT_ID 全局值**（非 per-agent）→ 只区分 agent session vs 人类，不区分哪个 agent（write-owner-audit 已有 AGENT_IDENTITIES 集合做身份，互补不冲突）
- **多 runtime 覆盖不全**（Cursor/自建）→ 文档说明，标后续扩；不阻塞 Claude Code 主路径
- **shim 性能**：每次 git 调用过 shim（bash exec 开销 <10ms，可忽略）
- **appetite 超期**：B 扩大工期（注入机制 runtime 层）。若超 1.5×（4.5d）触发 circuit_breaker → 阶段1（swarm-git+shim+单测，write_surfaces 内）先交付，阶段2/3（注入机制+多 runtime）拆 T1-07b

## 拆解 / 工期

| 阶段 | 内容 | 工期 | lane |
|---|---|---|---|
| 1 | swarm-git 扩展拦高危 + swarm_discipline argv_has_dangerous + 单测 | 1d | code |
| 2 | git-shim 脚本 + circuit_breaker（AGENT_ID 透传）+ 单测 | 0.5d | code |
| 3 | AGENT-BRIEF + AGENTS.md 文案 | 0.5d | docs |
| 4 | PoC: settings.json env 注入生效验证（scratch session） | 0.5d | config |
| 5 | 正式装：settings.json + ~/agents/shim/bin/git symlink + verify | 0.5d | config+安装 |
| - | retro: .omo/_knowledge/retros/BET-Y1Q1-T1-07.md（五问） | 含上 | docs |

## 认领命令（claim-check 已确认 YES）

```bash
bash bin/gac/gac-worktree.sh claim bet-y1q1-t1-07
uv run --with pyyaml python bin/agent-workflow.py start bet-execution \
  --profile governance-agent --objective "BET-Y1Q1-T1-07 git 入口收口 — shim 强制走 swarm-git"
# claim write_surfaces (逐个真实文件, 不 glob):
#   bin/gac/swarm-git, bin/gac/swarm_discipline.py, bin/gac/git-shim,
#   docs/plans/AGENT-BRIEF.md, AGENTS.md
```

**注意**：`~/.claude/settings.json` + `~/agents/shim/bin/` 超原 write_surfaces（用户选 B 授权），但这两个是**用户全局配置 + 安装产物**，改前需 human 确认（AGENT-BRIEF §9：改 write_surfaces 之外停下问人）—— 实施时阶段 4/5 前会再向你确认。
