---
lifecycle: contract
owner: governance-agent
last_updated: 2026-08-08
session-span: 2026-08-07 ~ 2026-08-08
related-bets: [BET-Y1Q1-T1-07]
related-prs: ["#1082", "#1085", "#1088", "#1131", "#1133"]
title: 2026-08-08 深度复盘：fork bomb 治理 → state drift → 治理漏洞全链
type: doc
---

# 2026-08-08 深度复盘：fork bomb 治理 → state drift → 治理漏洞全链

> 跨 session 连续工作（T1-07 git 入口收口 + 本轮 retro/state-drift/closeout）
> 核心主题：**高风险工作的防护与预案**
> 方法论：P73 truth-driven（先看事实再下结论）+ P78 triple-axis diagnostic

---

## 一、事件时间线（Timeline）

### Phase 1 — T1-07 fork bomb 事故（2026-08-07）
- `06:37` bet-execution run `66b7ef2c` 启动（BET-Y1Q1-T1-07 git 入口收口）
- 计划：把「记得用 wrapper」变成「只有 wrapper 可用」，堵 D4 已知缺口
- 实际：settings.json `env.PATH` 前置 `~/agents/shim/bin` → swarm-git 内部 `exec git` 走 PATH → shim → 无限递归 → **fork bomb**
- `ulimit -u 10666` 耗尽，系统多次重启仍复发（污染源未清）

### Phase 2 — 应急 + 三重防护（2026-08-07）
- REAL_GIT 绝对路径防递归（PR #1085，**根因修复**）
- SWARM_GIT_DEPTH>3 自检（PR #1088，defense-in-depth）
- `~/bin/check-fork-bomb-protection` 指纹检测（本地工具）
- settings.json + user.json 回滚（清 AGENT_ID + PATH shim）

### Phase 3 — 本轮深度治理（2026-08-08）
- T1-07 retro 五问复盘（PR #1131，D5 补救）
- main state drift 机械修复（PR #1133，bos-registry + state-sync）
- be3544c4 孤儿 run closeout（52 锁释放，active=0）
- 治理漏洞实证（D5 路径漂移 + 5 bet 缺 retro + closeout×done_when 解耦）

---

## 二、fork bomb 事故全链分析

### 根因链
```
settings.json env.PATH 前置 ~/agents/shim/bin
  → swarm-git 内部 `exec git` 解析到 shim（PATH 查找）
  → shim 调 swarm-git
  → swarm-git 再 `exec git` → shim → … 无限递归
  → fork failed: resource temporarily unavailable（ulimit -u 耗尽）
```
**关键缺陷**：swarm-git 早期版本用裸 `git` 而非绝对路径。任何通过 PATH 解析 git 的 wrapper 都有递归风险。

### 5 个打假发现（与 plan 不符的事实）
| # | plan 假设 | 实际发现 |
|---|-----------|----------|
| 1 | settings.json env 注入是安全的 PATH 前置 | PATH shim 递归 = fork bomb（最严重） |
| 2 | settings.json 是配置源 | 是生成工件（MergeSettings.ts 每次 SessionStart 重生成） |
| 3 | 改 settings.json 即持久 | SettingsBackport.ts 反向回写 user.json（污染源） |
| 4 | cp 能正常回滚 | shell alias `-i` 拦截，需 `/bin/cp -f` 绕过 |
| 5 | fork bomb 只杀进程 | 还破坏正打开的 git 索引（worktree gitdir 411K 损坏） |

### 三重防护（已在 origin/main）
| 层 | 机制 | PR | 作用 |
|----|------|-----|------|
| 根因 | REAL_GIT 绝对路径 | #1085 | 内部 git 调用不走 PATH，根本不递归 |
| 纵深 | SWARM_GIT_DEPTH>3 自检 | #1088 | REAL_GIT 失效/新 wrapper 时，深度超限中止 |
| 监测 | check-fork-bomb-protection | 本地 | 指纹扫描（shim/AGENT_ID/symlink），手动跑 |

### 残留发现：shim symlink（本轮新发现）
- `~/agents/shim/bin/git → bin/gac/git-shim`，**8/8 06:37 创建**（非本 session，daemon 时段）
- **当前零风险**：PATH 不含 shim/bin + 无 hook 自动重装 + git-shim 有 REAL_GIT 三重防护
- **处置**：非本 session 产物，待用户决定（删/留）。留则需警惕 PATH 不可被自动接上

---

## 三、state drift 系统性问题

### 现象
- bos-registry drift（live=158 vs file=156）→ evidence-gate failure
- goals `execution_mode_mismatch` flag 缺失 → state-goals-enforce failure
- state-plane-assets 1 issue → governance-verify failure
- **铁证**：main 自身 `320c3519d`/`bbb9f3c95` evidence-gate 也 failure（pre-existing）

### 根因
compact 期间 #1108-#1127 快速合并（20+ PR/天），**state sync 滞后**（ADR-0128 state-generation-concurrency）。bos-services.yaml 改了但 mirror 没 sync；runtime projections 没重新生成。

### 修复（本轮）
| 类型 | 操作 | 结果 |
|------|------|------|
| 机械 | `sync-bos-registry.py --write`（158/156 → 158/158）| ✅ evidence-gate 转绿 |
| 机械 | `make state-sync`（runtime projections 重生成）| ✅ system/health/BRIEF/INDEX 更新 |
| 语义 | goals execution_mode flag | ⚠️ 涉及 flag 机制语义，非机械，留单独评估 |
| 语义 | state-plane-assets 1 issue | ⚠️ 待定位具体内容 |

**教训**：state-sync dry-run 不覆盖所有 make target 的改动（BRIEF/INDEX 副产物未 preview）。机械 sync 后要 `git status` 全量核对，不能只信 dry-run。

---

## 四、治理漏洞发现（3 个，均系统性）

### 漏洞 1：D5 retro 路径漂移（最严重）
- workflow 定义 `path_glob: .omo/_knowledge/retros/**`
- 实际历史目录 `retrospectives/`（retros/ 本次才创建）
- **实证**：`bet-ledger.py retro-due` 显示 5 个已 done bet 全缺 retro
  - T1-01（废除 X3 mtime）/ T1-03（goals 复活）/ T2-01（signal-sources）/ T3-01（MOS belief 三表）/ T7-01（scene-card 五档）
- **影响**：D5 `retro-written` required check 形同虚设（空目录匹配即放行），所有历史 bet closeout 的 retro 校验未真正执行

### 漏洞 2：closeout × done_when 解耦
- `66b7ef2c` run `status=ok` + `closed_at` 齐全，但 done_when 4 条只过 3 条（第1条 PATH shim 未交付）
- closeout 流程不校验 done_when 全过 → **bet 假性完成**，状态失真

### 漏洞 3：孤儿 run（bet_id 占位符）
- `be3544c4` 的 `bet_id` 是 `{bet_id}` 模板占位符（start 时没绑 bet）
- 锁占用无法正确归属，closeout 时 D5 retro-written 会找 `retros/{bet_id}.md` 字面量
- **本轮已 closeout**（closeout 命令的 verify 不跑 execute phase，故未挂），但根因未治

---

## 五、高风险工作防护预案（经验固化 · 核心章节）

> 用户明确要求：**高风险工作一定要做好防护和预案**。以下 5 条预案从本轮实战提炼，未来同类工作必须遵守。

### 预案 1：fork bomb 永久防护
| 规则 | 说明 |
|------|------|
| **永不**在 settings.json env 注入 PATH | 用 SessionStart hook 内 `export PATH=...`（仅当前 session，不污染全局） |
| wrapper 必须用绝对路径 | REAL_GIT 模式（PATH 中非 shim 的 git 绝对路径） |
| 递归深度自检 | SWARM_GIT_DEPTH>3 中止（defense-in-depth） |
| 指纹定期检测 | `~/bin/check-fork-bomb-protection` 纳入 closeout 检查 |

### 预案 2：紧急回滚标准动作
```bash
# 1. 绕过 alias -i（cp 被 zsh 别名为 cp -i）
/bin/cp -f ~/backups/settings-clean-baseline-*/settings.json ~/.claude/settings.json
# 2. 同时清 user.json（Backport 反向污染源，否则 MergeSettings 会带回）
python3 -c "import json,pathlib; p=pathlib.Path('~/.claude/LIFEOS/USER/CONFIG/settings.user.json').expanduser(); d=json.loads(p.read_text()); d.get('env',{}).pop('AGENT_ID',None); p.write_text(json.dumps(d,indent=2))"
# 3. 验证
~/bin/check-fork-bomb-protection
```
**铁律**：回滚 settings.json 必须同时清 user.json，否则 SessionStart 又带回来。

### 预案 3：治理操作前备份
| 操作 | 备份对象 | 命令 |
|------|----------|------|
| closeout / run 变更 | run yaml | `cp .omo/_delivery/.../runs/<run>.yaml ~/backups/` |
| state-sync | system.yaml/goals/bos-registry | `make state-sync-dry` + cp 关键文件 |
| worktree release | dirty 文件清单 | `git -C <wt> status --short > ~/backups/<wt>-dirty.txt` |
| 危险操作 | 全局 | `~/backups/<task>-<ts>/` 目录化备份 |

**盲区警示**：`make state-sync-dry` 只 preview omo state sync 部分，**不覆盖** BRIEF/INDEX 副产物。机械操作后必须 `git status` 全量核对。

### 预案 4：CI drift 识别三步法
1. **先确认 main 自身 CI**：`gh run list --branch main --workflow <gate>` → 区分 pre-existing vs 新引入
2. **本地等价验证**：`sync-bos-registry.py --check` / `check-state-goals-alignment.py` / `omo lint state-plane-assets`
3. **语义 drift 不擅动**：goals `execution_mode` / state-plane 是治理语义状态，改前必须理解 flag/lint 逻辑，否则单独 bet + 人类确认

**本轮应用**：bos drift 是机械（修了），goals/state-plane 是语义（报告未修），interface-check 查证非新引入回退。

### 预案 5：worktree 卫生纪律
| 规则 | 说明 |
|------|------|
| release 前必查 dirty 内容 | 不能凭"gone 分支"判零风险（本轮 4 个 gone worktree 全有 dirty） |
| 子模块指针改动也要评估 | `Mm`/`m` 是 gitlink 改动，可能藏交付物 |
| `worktree prune` 只清悬空记录 | 已物理删除目录的 metadata，安全；不动任何文件 |
| 有 dirty 的 worktree 归 T1-00 | 并发写冲突止血 bet 统一处理，不零散 release |

---

## 六、本轮交付清单

| 交付 | PR/动作 | 状态 | 验证 |
|------|---------|------|------|
| T1-07 retro 五问（D5 补救）| PR #1131 | OPEN | doc-ssot-lint/ssot-guardian/workflow-lint 全绿 |
| main state drift 机械修复 | PR #1133 | OPEN | bos sync --check exit=0（evidence-gate 转绿）|
| be3544c4 孤儿 run closeout | 52 锁释放 | ✅ | active=0 closed=17 locks=0 |
| worktree prune | 2 悬空记录清理 | ✅ | worktree list 15→13 |
| 全量备份 | `~/backups/state-drift-fix-20260808T224612Z/` | ✅ | 5 文件 + worktree 列表 |
| 本深度复盘 | 本文件 | ✅ | — |

## 七、未完成项 + 下一步

### 需用户决策
1. **shim symlink** 删/留（`~/agents/shim/bin/git`，当前零风险但悬空）
2. **PR #1131/#1133 合并时机**（CI 剩余 goals/state-plane/interface 语义 drift）
3. **主仓脏状态**（dirty=41，HEAD 在 gone 分支，T1-00 bet 范畴）

### 新 bet 建议（按优先级）
| P | bet | 治什么 |
|---|-----|--------|
| P0 | T1-00 并发写冲突止血 | 主仓违规 + worktree 卫生（系统性） |
| P1 | D5 retro 路径统一 + 5 历史 retro 补写 | 漏洞 1（D5 check 形同虚设） |
| P1 | closeout × done_when 耦合修复 | 漏洞 2（bet 假性完成） |
| P2 | main state drift 语义治理 | goals flag + state-plane（非机械） |
| P2 | T1-07 done_when 第1条 SessionStart hook | PATH shim 安全注入 |
| P3 | start 命令 bet_id 必填校验 | 漏洞 3（孤儿 run 根因） |

---

## 八、五问速答（本 session 级）

1. **做对了什么**：fork bomb 三重防护落地 + retro 诚实记录 done_when 3/4 + 实证 3 个系统性治理漏洞 + 全程 worktree 隔离 + 操作前备份
2. **做错了什么**：worktree release 前凭"gone 分支"误判零风险（实际 4 个全 dirty，纠正后未 release）；state-sync dry-run 盲区（BRIEF/INDEX 未 preview）
3. **学到什么**：高风险操作的防护必须是**多层 + 可回滚 + 可验证**；机械修复和语义治理要分开（前者敢做，后者报批）
4. **净增减**：2 PR（#1131 retro 107 行 / #1133 drift 5 文件）+ 1 closeout + 1 复盘文档；本地工具复用未新增
5. **下一个 agent 要知道什么**：见第五节 5 条预案 + 第七节 bet 建议；shim symlink 当前安全但需溯源（8/8 06:37 创建者）
