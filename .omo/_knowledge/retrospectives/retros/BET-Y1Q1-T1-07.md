---
lifecycle: history
owner: governance-agent
last_updated: 2026-08-08
bet: BET-Y1Q1-T1-07
track: T1-TRUTH
window: Y1Q1
run_ref: 20260807T063711Z-bet-execution-66b7ef2c
title: BET-Y1Q1-T1-07 复盘
type: retro
---
# BET-Y1Q1-T1-07 复盘

> git 入口收口 — shim 强制走 swarm-git
> 把「记得用 wrapper」变成「只有 wrapper 可用」, 堵上 D4 已知缺口
> 关联事故: 2026-08-07 swarm-git PATH shim 递归 → fork bomb (系统资源耗尽, 多次重启)

---

## Q1 实际耗时 vs appetite？超出比例？

- **appetite**: 3 days
- **实际**: 约 0.5 天日历时间（task 生成 2026-08-07T01:36Z → run start 06:37Z → #1088 merge 11:25Z，核心开发 ~5h），**未超 appetite**
- **但**：触发了一次**计划外重大事故**（fork bomb），事故排查 + 系统恢复 + 防御加固消耗了额外 2 个 session，若计入事故恢复成本则显著超时
- **circuit_breaker 触发**：task 定义的 `shim 影响人类正常使用 → 改为只在 AGENT_ID 非空时生效` 实际演化为更严重的形态——shim 递归导致 agent 环境本身不可用，**主动搁置 done_when 第1条**（PATH shim 安装）作为熔断

**结论**：appetite 内完成核心拦截机制，但 done_when 第1条（PATH 注入）因事故熔断未交付，转为替代方案（见 Q5）。

---

## Q2 done_when 是否全部通过？哪条没过，为什么？

`evidence_required` 4 条逐条核验（诚实记录，不模糊化）：

| # | done_when | 状态 | 证据 |
|---|-----------|------|------|
| 1 | agent 环境 PATH 前置 shim: `~/agents/<id>/bin/git → bin/gac/swarm-git` | ❌ **未过** | fork bomb 事故后主动搁置。settings.json env 注入 PATH shim → swarm-git `exec git` 走 PATH → shim → 无限递归。改用 SessionStart hook 方案（待做） |
| 2 | swarm-git 拦截高危: `clean -fd` / `reset --hard` / `stash -u` / 共享分支 rebase | ✅ 过 | `bin/gac/swarm_discipline.py:691 argv_has_dangerous` (origin/main) + swarm-git bash 预过滤 + 共享分支 rebase 拦截 (PR #1082) |
| 3 | 每次逃生必写 `.omo/_delivery/swarm-escape/` 台账 | ✅ 过 | swarm-discipline 现有机制 + AGENT-BRIEF D4 文案明确「逃生口只有 swarm-git」(commit 1e3d7b88a) |
| 4 | AGENT-BRIEF.md 明确「逃生口只有 swarm-git一个入口」 | ✅ 过 | commit `1e3d7b88a` docs(brief): T1-07 逃生口文案 |

**3/4 通过，第1条未过。bet 不应置 done**（task `retro_required: true` 满足，但 `completed_at` 应保持 null）。

**治理漏洞**：run `66b7ef2c` 显示 `status: ok` + `closed_at: 2026-08-07T13:01:59Z`，但 D5 `retro-written` required check 未卡住——根因是 D5 check 的 `path_glob: .omo/_knowledge/retros/**` 与实际目录 `retrospectives/` 不一致（`retros/` 目录此前根本不存在），check 找不到目标即放行。本次补救新建 `retros/` 并写入本文件。

---

## Q3 过程中发现的与 plan 不符的事实（打假）？

plan 基于 2026-08-06 快照，假设「PATH shim via settings.json env 注入即可」。执行中发现 5 项重大偏差：

1. **PATH shim 递归 = fork bomb**（最严重）：settings.json `env.PATH` 前置 `~/agents/shim/bin` 后，swarm-git 内部 `exec git` 解析到 shim → shim 调 swarm-git → swarm-git 再 exec git → 无限递归。系统 `ulimit -u 10666` 耗尽，**多次重启仍复发**（因污染源未清）。根因：swarm-git 早期版本用 `git` 而非绝对路径。
2. **settings.json 是生成工件，不是源**：MergeSettings.ts (SessionStart hook) 每次会话把 system.json + user.json 合并重生成 settings.json。直接编辑 settings.json 的修改下次会话即丢失。
3. **SettingsBackport.ts 反向污染**：会把 settings.json 的 env 偏移回写 user.json——我回滚 settings.json 后，Backport 把 AGENT_ID 写进了 user.json，导致 MergeSettings 每次 SessionStart 又带回来。**必须同时清 user.json 才能根治**。
4. **shell alias `-i` 拦截 cp**：`cp` 被 zsh 别名为 `cp -i`，紧急回滚时交互式提示阻塞自动化。必须用 `/bin/cp -f` 绕过。
5. **worktree gitdir 在 fork 风暴后损坏**：411K 索引 + 损坏 gitdir，`git -C ws status` 超时。fork bomb 不只杀进程，还破坏了正打开的 git 索引文件。

**plan 的隐性假设错误**：「settings.json env 注入是安全的 PATH 前置方式」——实际上任何通过 PATH 解析 git 的 wrapper 都有递归风险，必须用绝对路径（REAL_GIT 模式）。

---

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？

T1-07 直接交付（commit `fef0e29f0` → `ae46bf1b1`，T1-07 write_surfaces 范围内）：

| 文件 | 变化 | 说明 |
|------|------|------|
| `bin/gac/git-shim` | **+43 新建** | AGENT_ID 断路器：空→透传人类，非空→swarm-git |
| `bin/gac/swarm-git` | +76 修改 | REAL_GIT 绝对路径防递归 + SWARM_GIT_DEPTH>3 自检 (defense-in-depth) |
| `bin/gac/swarm_discipline.py` | +22 | `argv_has_dangerous`：clean -fd / reset --hard / stash -u 组合标志解析 |
| `docs/plans/AGENT-BRIEF.md` | +3 | 逃生口只有 swarm-git 文案 |
| `AGENTS.md` | +4 | T1-07 纪律补强 |

- **净增**: ~145 行 + 1 新文件（git-shim）。**纯增量治理，无删除**——本 bet 性质是「加固入口」，不涉及减法。
- **GaC 规则**: 0 增 0 减（swarm-git 走 swarm-discipline 现有台账，未新增 GaC check）
- **ADR**: 0（事故教训暂记本 retro + docs/operations 回顾，未升 ADR；若 SessionStart hook 方案落地需开 ADR）
- **本地工具（未提交, 不入 surface）**: `~/bin/check-fork-bomb-protection`（指纹检测）+ `~/backups/settings-clean-baseline-*.tar.gz`（干净基线）

**配套删除**: 无。事故期间回滚了 settings.json/user.json 的 AGENT_ID + PATH shim 污染（恢复到事故前干净态，非功能删除）。

---

## Q5 下一个认领本 track 的 agent 需要知道什么？

### 必读（踩过的坑）

1. **done_when 第1条仍未完成**：PATH shim **不要**走 settings.json env 注入（必 fork bomb）。替代方案：**SessionStart hook 注入 PATH**（hook 内 export，仅当前 session 生效，不污染全局 settings）。落地前必须 PoC：在隔离环境验证 shim→swarm-git→REAL_GIT 调用链深度=1，且 SWARM_GIT_DEPTH 自检生效。
2. **fork bomb 三重防护已在 origin/main**（勿重复造）：
   - REAL_GIT 绝对路径（PR #1085，根因修复）
   - SWARM_GIT_DEPTH>3 自检（PR #1088，defense-in-depth）
   - 本地 `~/bin/check-fork-bomb-protection`（指纹检测，手动跑）
3. **settings.json 规则**：永远是生成工件。持久化改动改 `~/.claude/LIFEOS/USER/CONFIG/settings.user.json` 或 `settings.system.json`。改完跑 `~/bin/check-fork-bomb-protection` 验证。

### 治理漏洞（建议另开 bet）

4. **D5 retro 路径漂移**：workflow 定义 `path_glob: .omo/_knowledge/retros/**`，但历史目录是 `retrospectives/`。`retros/` 本次才创建。**实证（2026-08-08 跑 `bet-ledger.py retro-due`）**：5 个已 done 的 bet 全部缺 retro——`T1-01`（废除 X3 mtime）/`T1-03`（goals 复活）/`T2-01`（signal-sources）/`T3-01`（MOS belief 三表）/`T7-01`（scene-card 五档）。D5 `retro-written` check 确实形同虚设，是系统性问题，不止 T1-07。建议：统一路径（`retros/` 为准）+ 补写 5 个历史 retro + closeout 流程加「retro 文件存在性」硬校验（当前 `path_glob` 匹配空目录即放行）。
5. **run closeout 与 done_when 解耦**：`66b7ef2c` run status=ok 但 done_when 4 条只过 3 条。closeout 流程应校验 done_when 全过才允许 status=ok，否则 bet 会假性完成。

### 环境要求

6. 紧急回滚 settings 用 `/bin/cp -f`（绕过 alias -i），不要用裸 `cp`。
7. fork bomb 复发征兆：`echo alive` 返回 rc=1（系统无法 fork）→ 立即查 settings.json + user.json 的 PATH shim/AGENT_ID 指纹，不要怀疑 Bash 工具本身。

### 未做完的尾巴

- T1-07 done_when 第1条（SessionStart hook 方案）
- D5 路径漂移治理（retros/ 统一 + 历史审计）
- closeout × done_when 耦合修复
