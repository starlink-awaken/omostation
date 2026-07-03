# Agent 并发隔离落地计划 — Worktree + Branch Protection

> **状态**: 📋 待推进(就绪未启用) · **创建**: 2026-06-30 · **关联**: ADR-0106 P2 · `docs/GOVERNANCE-EVOLUTION-ROLLOUT.md:36`
> **临时治本**: `bin/gac-local-gate.py` scope staged(commit `896e60ba`,已验证 PASS)

---

## TL;DR

多 agent(老王 + 并发 governance agent)共享同一 worktree,导致 commit 死循环——GaC 的 doctor/compliance/verify 是 worktree-wide 检查,被并发 dirty 污染后 FAIL,拦住所有 commit。

**临时治本**(`gac-local-gate` scope staged)已生效并验证 PASS。**终态方案**(per-session worktree + main branch protection)脚本就绪、执行层待推进。

> **⚠️ Phase 0 OBSERVE 真相纠正(2026-06-30)**: 早期记忆 `ecos-auto-commit-behavior` 称"eCOS X-Plane Audit Agent 程序化 auto push main"——**经代码实证为误**。`X-Plane Audit Agent` 实为主仓 `git user.name`(所有 commit 署名,含手动);`.githooks/post-commit` 注释明写"不自动创建 commit"只做 L0 萃取;无 watcher/daemon 程序化 push。**direct push main 是 agent/人的工作习惯,非程序机制**。Phase 2 据此重新定义为「direct-push→PR 范式转变」(非改某个 agent 程序)。详见 §4 Phase 2。

---

## 1. 问题背景

- **根因**: 多 agent 共享 `/Users/xiamingxing/Workspace` 一个 worktree,各自改文件 → GaC 预提交门禁的 doctor/compliance/verify 读 worktree-wide 状态 → 撞到别的 agent 留的并发 dirty → FAIL → 拦 commit → 死循环。
- **临时治本**(2026-06-30, commit `896e60ba`): `bin/gac-local-gate.py` 改造为 scope staged——doctor/compliance/verify 只在 staged 涉 agent-workflow 时跑,否则 skip(隔离并发 dirty);`--strict` 模式 CI 跑全套。已验证:默认 PASS + 3 check skip + strict 暴露 doctor。
- **临时治本的局限**: 仍是「共享 worktree 下打补丁」,没从根上消灭撞车。终态应是**物理隔离**(每 agent 一个 worktree)+ **平台兜底**(main 保护,禁 direct push)。

---

## 2. 现状铁证 — 声明 vs 执行鸿沟(2026-06-30 实测)

| 机制 | 脚本(声明层) | 运行时(执行层) |
|:-----|:-------------|:-----------------|
| **worktree 隔离** | `bin/gac-worktree.sh` 112 行 ✅ claim/submit/release/list 全实现,对标 Linux kernel/Devin/Codex | `git worktree list`: 仅主仓 + 1 个 superpowers feature,**0 个 per-session worktree**;`rg` 全仓 **0 外部引用**(孤儿子脚本) |
| **github 分支保护** | `bin/gac-branch-protection.sh` 78 行 ✅ --set/--check/--remove,PUT branch protection API | `gh api repos/starlink-awaken/omostation/branches/main/protection` → **HTTP 404 "Branch not protected"**;repo public 非 fork 非 archived(可设但没设);**0 外部引用**(孤儿) |

**诊断**: 这俩 = ADR-0106 P2 终态方案,跟之前修过的 **BOS 声明/执行鸿沟 + commit 死循环**同一病根——**GaC 只写了「代码」(脚本),没「运行」(没执行/没编排进流程)**。`docs/GOVERNANCE-EVOLUTION-ROADMAP.md:36` 也把 "Worktree/release convergence" 列为终态目标,当前工具栏写的是 `gac-local-gate`(临时治本)。

---

## 3. 目标(终态)

1. **物理隔离**: 每 agent session 独立 worktree + 分支 `work/<session>`,各改各的,PR 合并。从根上消灭共享 worktree 撞车。
2. **平台兜底**: main branch protection——禁 direct push,强制 PR。agent 绕不过平台,被迫走隔离流程。
3. **保留临时治本**: `gac-local-gate` scope staged 作为 worktree 内的**第二道防线**(per-session worktree 内仍可能有并发?保险起见保留)。

---

## 4. 三阶段落地

### Phase 1 — worktree 单点试跑(低破坏,验证流程)

- **目标**: `gac-worktree.sh claim → submit → release` 全链路在**一个真实 agent session** 跑通。
- **动作**:
  1. 挑一个低风险、范围明确的 task(文档/单模块改动)。
  2. 老王用 `bash bin/gac-worktree.sh claim <session>` 起独立 worktree(落在 `$WS_PARENT/ws-<session>`)。
  3. 在 worktree 内干活、commit。
  4. `bash bin/gac-worktree.sh submit <session>` push 分支 + 开 PR(base main)。
  5. PR 合并后 `bash bin/gac-worktree.sh release <session>` 清理。
- **重点验证**: **子模块行为**——脚本注释 line 13 自标「子模块独立 worktree 后续」,当前是主仓 worktree 子模块共享。需验证子模块 commit/push 在 worktree 下不撞、gitlink 不悬空。
- **不动**: branch protection **不开**,direct push 仍可用(回退容易)。

### Phase 2 — direct-push → PR 工作流范式转变(branch protection 前置,硬骨头)

> **2026-06-30 Phase 0 OBSERVE 重定义**: 原"改 eCOS X-Plane Audit Agent 的 push 代码"基于过时记忆,靶点错误。真相:`X-Plane Audit Agent` = git identity(非程序);无程序化 auto-push;direct push main 是工作习惯。Phase 2 = **整个仓库工作流从 direct-push 迁移到 PR**。

- **目标**: 所有 main 变更走 `work/<session>` 分支 + PR 合并,消灭 direct push main。
- **关键认知**:
  - **L0 萃取不破坏** ✅ — `.githooks/post-commit` 是 **commit 级**触发(非 push 级),PR merge 也是 commit,派生文件生成/mof-extract 天然兼容。
  - **direct push 是工作习惯,非代码** — 改的是工具 + 指令 + hooks 守卫,不是某个 agent 程序。
  - **基础设施就绪** — `gh CLI 2.95.0` + `gac-worktree.sh submit`(已实现 `gh pr create --base main`)。

#### Phase 2 子阶段(渐进降风险)

| 子阶段 | 内容 | 风险 | 可逆 |
|:---|:---|:---|:---|
| **2a 工具补全** | pre-push direct-push advisory 守卫 + `gac-worktree.sh merge` 子命令(PR 合并+release 一体) + 子模块两段式 PR 机制 | 零(不改现有行为) | ✅ |
| **2b 指令更新** | CLAUDE.md/AGENTS.md §6 明确 PR 工作流,direct push main 列禁忌(2c 后强制) | 低(文档) | ✅ |
| **2c 守卫升级** 🔄路径A第1步advisory | 源 blocking done(893f2332) → **路径A回退 advisory**(本步, 已 install) → 第4步恢复. 原因: auto-PR 未通, escape hatch 滥用废 blocking (半吊子) | 中 | 第4步+Phase3 |
| **2d 灰度验证** | 真实低风险任务走完整 PR 流程(claim→submit→merge→release),验证 L0 萃取在 merge commit 触发 | 低(验证) | ✅ |
| **2e Phase 3 解锁** | branch protection 启用(ISC-4/5 达成后) | 高(平台级) | `--remove` 回退 |

- **风险**: 中——不"动 eCOS 核心"(原误判),而是改全局工作流习惯。最大复杂度在**子模块 gitlink 可达性**(PR merge 后子模块 commit 必须已在子模块远程)。**子模块策略详见 [`docs/SUBMODULE-PR-STRATEGY.md`](SUBMODULE-PR-STRATEGY.md)**(方案 A':主仓 PR + 子模块保持 direct push,复用 `sync-submodules-push.sh` 零改造)。
- **2c 确认节点**: blocking 守卫改变现有行为,执行前需用户显式确认。

### Phase 3 — 启用 branch protection(平台兜底)

- **前置**: Phase 2 完成(所有 main 变更能走 PR),否则 direct push 全被 GitHub 拒。
- **动作**: `bash bin/gac-branch-protection.sh`(交互确认 → PUT protection)。
- **策略**(脚本已设计,过渡期):
  - Require PR before merging(核心隔离)✅
  - 禁 direct push ✅
  - `required_approving_review_count: 0`(单人可 merge,不阻塞)
  - 不强制 Required CI(过渡,避免 omo 测试红卡 merge;稳定后加 required status checks)
- **稳定后加**: `required_status_checks`(gac-gate / ci-lint 等必过才能 merge)。

---

## 5. 前置依赖 / 阻塞清单

| 依赖 | 说明 | 阻塞阶段 |
|:-----|:-----|:---------|
| **direct-push → PR 工作流迁移** | 当前 agent/人显式 `git push origin main` 是工作习惯(非程序机制,2026-06-30 实证) | Phase 2 → Phase 3 |
| **子模块 worktree 行为验证** | 脚本注释自标「子模块独立 worktree 后续」,当前共享 | Phase 1 验收 |
| **子模块两段式 PR 机制** | 当前 `sync-submodules-push.sh` 是 direct push 子模块,需适配 PR(2a-4) | Phase 2a |
| **并发 governance agent 协调** | 其他会话的 agent 也要走 worktree+PR 流程 | Phase 2 |
| **agent 工作流改造** | agent 得学会先 `claim` 再干活(非直接改主 worktree) | Phase 1 起 |

---

## 6. 验收标准(ISC)

- **ISC-1**(Phase 1): `git worktree list` 含 ≥1 个 `work/<session>` worktree,且对应 PR 在 GitHub 上 visible。
- **ISC-2**(Phase 1): worktree 内子模块 commit/push 后,主仓 gitlink 不悬空(`bin/ssot-guardian.py` submodule_pointer_drift PASS)。
- **ISC-3**(Phase 2,重定义 2026-06-30): main 变更走 `work/<session>` + PR,direct push main 消失。细化为子 ISC:
  - **ISC-3a**(2a): `gac-worktree.sh merge <session>` 跑通(gh pr merge --squash + release + 删分支)
  - **ISC-3b**(2c, 🔄 路径A第1步: 回退 advisory (2026-07-01, 已 install)): pre-push 源 `.githooks/pre-push` advisory→blocking (direct push main 非 work/* → exit 1) + `DIRECT_PUSH_MAIN_OK=1` escape hatch. 验证: direct push main exit 1 / env 放行 rc=0 (sync+reachability 仍跑). **未 `make install-hooks`** → `.git/hooks/pre-push` 副本仍 advisory, 真实 push 行为未变 (不扰并发 agent). install 后 blocking 生效 (影响所有 direct push main), 待用户拍板 + Phase 3 一起上
  - **ISC-3c**(2d,修正): worktree commit 时 `post-commit` L0 萃取触发 (commit 级, worktree 共享 `.git/hooks`; `~/.ecos/commit-impact.log` 有记录). PR merge 是服务端 commit, **不触发本地 post-commit** — 萃取已在 worktree commit 时完成, 派生文件进 PR
  - **ISC-3d**(2d): ≥1 次完整 PR 流程跑通(claim→submit→merge→release),gitlink 不悬空
  - **ISC-3e**(2d smoke 发现,✅ 已治本 commit `2f78a9e9`): `gac-worktree.sh claim` 自动 init GaC gate 依赖子模块 (`projects/ecos` + `scripts`, ~7s) → `mof-schema-validate`/`mof-state-bridge`/`mof-drift`/`doc-ssot-snapshots` PASS. `INIT_ALL_SUBMODULES=1` 全部 (~60s), `SKIP_SUBMODULE_INIT=1` 跳过. 8x 加速 vs 全部 init
  - **ISC-3f**(✅ 已治本): worktree 完整 PR 流程被俩**仓库级不变量** check 拦 — `governance-evolution` (脚本 untracked + 依赖 agora/cockpit 子模块, worktree checkout 没有) + `doc-ssot-lint` (依赖 `docs/generated/*` gitignored, worktree 没有). 真治本 (KISS): 俩归 `CI_ONLY_CHECKS` (同 `project-layer-index`/`dependency-baseline-drift` 仓库级不变量模式, **不**搞 worktree 检测那套复杂机制) — non-strict pre-commit 跳过 (worktree 解锁), strict CI 兜底. 验证 (2026-07-01): 主仓 non-strict `ok=True` 俩跳过 / strict 仍含俩 / pilot worktree 直接跑俩均 FAIL (脚本 absent + generated absent, 证明就是 blocker). ⚠️ **残留债** (单独 followup, 非 ISC-3f 范围): `bin/governance-evolution.py` + `.omo/_truth/registry/governance-evolution-roadmap.yaml` 仍 **untracked** (并发 agent WIP 半 commit — gate 引用已 commit 但脚本/数据没), CI strict fresh checkout 跑不了 → 需 commit 这俩或撤 gate 引用
  - **ISC-3g**(2d, ✅ 治本 2026-07-03, worktree `sync-detached-fix`): `bin/sync-submodules-push.sh` 治 detached HEAD 子模块. worktree `--init` 产生 detached 子模块 (HEAD 在主仓 gitlink commit, 无 branch tracking), 旧逻辑判 `branch=HEAD`→`origin/HEAD` 不存在→`noupstream+failed` 拦 push (PR#91 实测 failed=17 无上游). 治本: detached → 视同 missing 跳过 (不计 failed); gitlink 可达性由 `submodule-reachability-gate` 兜底 (pre-push 独立跑). 区分真未推 (branch≠HEAD 走正常逻辑). 验证: worktree `sync --dry-run` failed 17→0. **解锁**: worktree push 不被 detached sync 拦, `gac-worktree.sh submit` 可用 (免手动 --no-verify). 由 PR#91 (CLAUDE.md+doc-ssot-lint) 实战踩出.
  - ⚠️ **ISC-3g followup B** (待办, 需 ecos 子模块 PR): sgf-policy.yaml 实测仅 `project-layer-index`+`dependency-baseline-drift` 有 `ci_only` — ISC-3f 描述的 `governance-evolution`/`doc-ssot-lint` 归 `CI_ONLY_CHECKS` **未在 sgf-policy 真落地** (疑被后来 sgf-policy 重构覆盖; DEFAULT_POLICY 同样没有). 现象: worktree pre-commit 仍被 `governance-evolution` (依赖 agora/cockpit 子模块脚本, worktree 部分 init 没有) 假阳性拦. 真落地需 ecos 子模块 PR 给 sgf-policy 这俩 check 加 `ci_only: true` (延续 ISC-3f 仓库级不变量模式). ISC-3g 本轮只治主仓 sync (A), followup B 另开
- **ISC-4**(Phase 3): `gh api repos/starlink-awaken/omostation/branches/main/protection` 返回 **200**(非 404)。
- **ISC-5**(Phase 3): direct push main 被拒(实测 `git push origin main` 被 GitHub 拒,提示需 PR)。
- **ISC-6**(全程): `gac-local-gate` 在 per-session worktree 下仍 PASS(临时治本兼容,第二道防线不破)。

---

## 7. 风险

| 风险 | 影响 | 缓解 |
|:-----|:-----|:-----|
| branch protection 一开 eCOS auto-push 全挂 | L0 萃取断,高 | Phase 2 必须先完成,Phase 3 不得抢跑 |
| 子模块在 worktree 下撞 | gitlink 悬空,ssot-guardian 红 | Phase 1 重点验证,必要时子模块也独立 worktree |
| agent 忘记 claim 直接改主 worktree | 隔离失效 | Phase 3 branch protection 兜底(direct push 被拒强制走 PR) |
| 过渡期 0 reviews 误 merge | 质量回退 | 稳定后加 required_status_checks + review 要求 |
| worktree 累积不 release | 磁盘膨胀 | `gac-worktree.sh list` 定期巡检 + release |

---

## 8. 回退

- **branch protection**: `bash bin/gac-branch-protection.sh --remove`(交互确认 → DELETE protection → direct push 恢复)。
- **worktree**: `bash bin/gac-worktree.sh release <session>`(清理单 worktree);分支 `work/<session>` 保留,合并后可 `git branch -D work/<session>`。
- **临时治本**: `bin/gac-local-gate.py` scope staged 独立于这俩,任何时候都保留(第二道防线)。

---

## 9. 关联引用

- **临时治本**: `bin/gac-local-gate.py:131-166` scope staged + `:225` --strict(commit `896e60ba`, 2026-06-30)
- **规则**: ADR-0106 P2(per-session worktree + branch protection 终态)
- **roadmap**: `docs/GOVERNANCE-EVOLUTION-ROLLOUT.md:36`(Worktree/release convergence,终态目标)
- **脚本**(2026-06-30 优化): `bin/gac-worktree.sh`(+session 命名校验 `[a-z0-9-]`/claim 分支冲突检测/submit·release 校验) · `bin/gac-branch-protection.sh`(+`--yes` 非交互 agent 可跑/`--check` 解析各项保护状态/`--help`)
- **记忆**: ~~`ecos-auto-commit-behavior`(direct push main 是 eCOS 设计行为,Phase 2 硬阻塞)~~ — **2026-06-30 实证纠正**: 该记忆已过时(post-commit 不 push,只 L0 萃取;X-Plane Audit Agent 是 git identity 非程序)。direct push main 是工作习惯,Phase 2 迁 PR 不破坏 L0 萃取(commit 级触发天然兼容)
- **同类病根**: BOS 声明/执行鸿沟(`bos-decl-exec-gap`,已修)· commit 死循环(本轮治本)

---

## 变更历史

| 日期 | 变更 |
|:-----|:-----|
| 2026-06-30 | 创建: 现状铁证 + 三阶段落地计划(基于 commit 死循环治本的后续终态规划) |
| 2026-06-30 | 脚本优化: `gac-branch-protection.sh` +`--yes` 非交互(agent/CI 可跑)/`--check` 解析各项保护状态/`--help`; `gac-worktree.sh` +session 命名校验/claim 分支冲突检测(claim→release 全链路验证 PASS, 无残留) |
| 2026-06-30 | **Phase 0 OBSERVE 真相纠正**: 代码实证推翻"eCOS X-Plane Audit Agent 程序化 auto push"旧认知(X-Plane Audit Agent = git identity;post-commit 不 push 只 L0 萃取;无 watcher/daemon)。Phase 2 重定义为 direct-push→PR 范式转变 + 5 子阶段(2a-2e)。TL;DR/Phase 2/前置依赖/ISC-3/关联 全部纠正 |
| 2026-06-30 | Phase 2a/2b 落地(commit `74c4b444`): pre-push advisory 守卫(实战验证 PASS — direct push main 警告不阻断) + `gac-worktree.sh merge` 子命令 + 子模块 PR 策略(方案 A', `docs/SUBMODULE-PR-STRATEGY.md`) + AGENTS.md §6.1 |
| 2026-06-30 | **Phase 2d smoke 深层发现 + C+D 治本**(commit `fda2c0f0`): smoke 暴露 worktree 隔离 + worktree-wide GaC check 冲突. C+D 局部治本(doc-link-check `--files` scope staged + sync-submodules 未 init 跳过, ISC-W1/W2 验证 PASS). **ISC-3e 发现**: 6+ check 依赖子模块脚本(mof-*/governance-evolution/doc-ssot-*), 未 init 跑不了 → **真治本是 claim 自动 init 子模块**(C+D 只局部). smoke 已 release, 核心发现已得, submit/merge 待 claim-init 实现后重跑 |
| 2026-07-01 | **ISC-3f 治本**(commit `af2444e3`): `governance-evolution` + `doc-ssot-lint` 归 `CI_ONLY_CHECKS` (仓库级不变量, 同 project-layer-index 模式). KISS 选 reclassify 而非 worktree 检测. 解锁 worktree 完整 PR 流程 (gate 不再被这俩拦). 三路验证: 主仓 non-strict ok=True 俩跳过 / strict 仍含俩 (CI 兜底) / pilot worktree 直接跑俩均 FAIL (证死是 blocker). ⚠️ 残留债: governance-evolution.py + roadmap.yaml untracked (并发 agent WIP), CI strict fresh checkout 跑不了 → 单独 followup |
| 2026-07-01 | **Phase 2c blocking 守卫**(源 done, 未 install): `.githooks/pre-push` advisory→blocking, direct push main (非 work/*) → exit 1 + `DIRECT_PUSH_MAIN_OK=1` escape hatch. 验证: 测试1 direct push exit 1 / 测试2 env 放行 rc=0 (sync+reachability 仍跑). 未 `make install-hooks` → `.git/hooks/pre-push` 副本仍 advisory, 真实 push 行为未变 (不扰并发 agent). install 即影响所有 direct push main, 待拍板 (建议 + Phase 3 一起) |
| 2026-07-03 | **ISC-3g 治本** (worktree `sync-detached-fix`): `bin/sync-submodules-push.sh` 治 detached HEAD 子模块跳过 (failed 17→0), 解锁 worktree `submit` 免 `--no-verify`. 由 PR#91 (CLAUDE.md+doc-ssot-lint) 实战踩出: worktree `--init` 的 detached 子模块被 sync 判"无上游"拦 push. reachability 由 `submodule-reachability-gate` 兜底. ⚠️ followup B (待办): sgf-policy.yaml 仅 `project-layer-index`+`dependency-baseline-drift` 有 ci_only, ISC-3f 的 `governance-evolution`/`doc-ssot-lint` ci_only 未真落地 → 需 ecos 子模块 PR 补 |
