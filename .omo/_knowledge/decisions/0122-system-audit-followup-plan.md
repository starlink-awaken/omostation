---
schema: md/v1
status: active
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
id: ADR-0122
related: 
---


# ADR-0122: 系统全面审计 18 项 Follow-up 实施计划 (排除 god-module)

- **Status**: PROPOSED → ACTIVE (本 PR 推 S0 后转 active)
- **Date**: 2026-07-02
- **Authors**: governance-team (基于 PR #11 系统全面审计 18 项 follow-up)
- **Supersedes**: 0119 systemic-optimization 28 项中与本审计重复部分
- **Related**: ADR-0115 (bin 治理面 4 phase) / ADR-0119 (S0-S3 28 item) / ADR-0120 (freshness semantics) / ADR-0121 (GCSI) / P71 baseline recovery pattern

## Context and Problem Statement

PR #11 (`23702782`) 系统全面审计 (架构/功能/文档/债务/配置 5 维) 报告 20 项问题. 本 PR 修 2 P0 + 加 1 守护规则. **剩余 18 项 follow-up** (god-module 用户排除) 需要分阶段规划, 避免散点式 commit 造成 lane 混乱和元治理盲区再次累积.

18 项 follow-up 来源:
- 1.1.4 gac-m1-sync 写 submodule 架构问题 (F-5)
- 1.1.5 omo-debt 弃用 (F-13)
- 1.2.2 16 planned 任务累积 (F-2)
- 1.2.3 governance score 下滑 (F-2 联动)
- 1.3.1 cross-refs 4701 死链 (F-3)
- 1.3.2 dead-path-refs 50+ (F-4)
- 1.3.3 `> 最后更新` 时间戳反复加 (F-9)
- 1.3.4 FCM/NORTH-STAR 数字 stale (F-10)
- 1.4.2 BOS 3 处越界 (F-7)
- 1.4.3 + 1.5.2 6 单点 BOS 域无 kind (F-8)
- 新加 1.1.4 pre-push hook 误报 (F-11)
- 新加 1.1.4 gitconfig 配置漂移 (F-12)
- 新加 omo-debt 弃用收编 (F-13)
- 依赖项: ADR-0119 S2-5/S2-6 (state-freshness) + ADR-0115 Phase 2/3/4

## Decision Drivers

- **避免 god-module 跨仓债**(用户明示排除)
- **可执行**: 每项有责任项目 + 工作量 + 依赖
- **阶段化**: S0/S1/S2 + P2 渐进, 避免单 PR 巨型化
- **lane 守门**: 每 commit 单 lane, pre-commit hook 强制
- **X-Plane 协作**: mode=advisory 不阻塞, 避其 claimed paths
- **跨仓协调**: F-7/F-8/F-13 需 agora/omo/cockpit 团队, 不能主仓独立做

## Considered Options

### A. 3 阶段路线图 (推荐)

- S0 即时 (本 PR, ~1h): 4 commit, 1 PR
- S1 短期 (1-2 周): 4 PR + 1 submodule commit, ~12h
- S2 中期 (3-4 周): 3 PR + ADR-0115 P2+4, ~16h
- P2 长期: 跨仓 rename 5 阶段 (本仓无法独立)

### B. 单 PR 全做

- ❌ 单 PR 巨型化 (>20 commit), review 难
- ❌ 跨仓 F-7/F-8/F-13 不属主仓 scope
- ❌ 违反 lane check + GaC 7 机制

### C. 接受现状 (不规划)

- ❌ governance score 持续下滑 (97.8 趋势)
- ❌ 元治理盲区累积 (P49 已清零又累积, 周期循环)
- ❌ 与 ADR-0119 systemic roadmap 方向冲突

## Decision

**采用 A: 3 阶段 + P2 长期**, 每阶段独立 PR, 阶段间保留可中断性.

## 18 项路线图

### S0 即时 (本 PR, ~1h)

| 项 | 文件 | 工作量 | 验收 |
|---|---|---|---|
| **F-9** GaC 规则 `CR-DOC-NO-LAST-UPDATED` (守文档不再有"最后更新时间戳"行, 治 X-Plane 自动化副作用) | `.omo/_truth/registry/governance-checks.yaml` | 5min | gac-validate 140→141 PASS |
| **F-10** 修 FCM "115 规则" / AGENTS "7 机制 + 115 规则" / NORTH-STAR "118 规则" 数字 → 140 (清理"现在的事实"段落, 不改历史快照日期) | `docs/FUNCTIONAL-CAPABILITY-MAP.md` + `AGENTS.md` | 10min | rg 0 stale 数字 |
| **ADR-0122** 写本计划 (本文件) | `.omo/_knowledge/decisions/0122-system-audit-followup-plan.md` | 30min | commit + push |
| **ecos submodule M1 commit** + 主仓 bump pointer (5 个 GAC-RULE-*.yaml 在 `projects/ecos/` 内 untracked, 需 submodule 维护者 commit) | `projects/ecos/` 内 commit + 主仓 submodule pointer bump | 15min | main 包含 5 GAC-RULE M1 instance |

### S1 短期 (1-2 周, 4 PR)

| 项 | 责任项目 | 工作量 | 依赖 |
|---|---|---|---|
| **F-3** 修 `check-cross-refs` 4701 死链 (大头: archive 文件旧路径引用, 修链接 OR 删 archive) | 主仓 + archive 清理 | 4h | - |
| **F-4** 修 `check-dead-path-refs` 50+ `.omo/PROJECTS/` 死引用 | 主仓 | 1h | 跟 F-3 同步 |
| **F-5** 修 `gac-m1-sync` 写 submodule 内架构问题: 改 omo broker 写 (路径 `projects/ecos/.git/worktrees/<wt>/modules/projects/ecos` 替换) | omo 仓 + bin/ 工具 | 2h | - |
| **F-6** ADR-0115 Phase 3: 7 个 check-* 工具接入 `gac-local-gate.py::CHECKS` (按 false-positive 风险分级: 立即接 / scoped / CI-only / 归档) | 主仓 | 3h | ADR-0115 已接受 |
| **F-11** 修 `bin/ssot/sync-submodules-push.sh` 的 `noupstream=$((noupstream+1))` 在 `set -euo pipefail` 下被 stdin parsing 误触发; 改用更稳的检测 (e.g. 不用 pipefail 或加 guard) | 主仓 | 1h | - |
| **F-12** 修 auto-PR ISO 配置漂移: `make install-hooks` 后 `T .githooks/pre-commit` 残留, 改 Makefile 或加 install-hooks fix-up | 主仓 | 1h | - |
| **ecos submodule M1 5 commit (bump pointer)** | omo 仓 + 主仓 | 1h | F-5 完成 |
| **ADR-0121** 跟踪: X-Plane branch `work/gcsi-adr-0121` GCSI 推进 | governance-team | 0 | 跟踪即可 |

### S2 中期 (3-4 周, 3 PR + ADR-0115 Phase 2/4)

| 项 | 责任项目 | 工作量 | 依赖 |
|---|---|---|---|
| **F-2** ADR-0119 S2-5: 新建 `bin/gac/state-freshness-check.py` (基于 ADR-0120 freshness fix) | 主仓 | 3h | S0 完成 |
| **F-2 cont.** ADR-0119 S2-6: state-freshness 纳入 gac-local-gate | 主仓 | 1h | F-2 step 1 |
| **F-2 cont.** governance-evolution initiative 进度填充 (8 个全 active, 0 done) | 主仓 | 2h | - |
| **governance score 回升 97.8 → 100** (配合 F-2 完成) | 主仓 | 2h | F-2 完成 |
| **F-8** 6 个单点 BOS 域加 `kind: bridge` 或 `kind: facet` 标签 (`bos://cockpit/` / `bos://l4-kernel/` / `bos://runtime/` / `bos://meta/` / `bos://swarm/` / `bos://omo/`) | agora 仓 + 各 owner 仓 | 3h | 跟 F-7 同步 |
| **F-13** 删 `projects/omo-debt/` 独立仓, 收编到 cockpit 入口 | 主仓 + cockpit | 1h | - |
| **ADR-0115 Phase 2** `gov-` → `governance-` 短前缀 rename (2 文件: `gov-history-stats.py` + `gov-trend-report.py`) | 主仓 | 1h | F-6 完成 |
| **ADR-0115 Phase 4** 4 个 dashboard 工具合并为单 `bin/gac/governance-dashboard.py <subcommand>` | 主仓 | 3h | F-6 完成 |

### P2 长期 (渐进, 跨仓协调)

| 项 | 描述 | 状态 |
|---|---|---|
| **F-7** BOS 域 3 处越界跨仓 rename 5 阶段: 本仓标准(已, ADR-0115) → agora PR 加 `kind:` + `deprecated_uri:` redirect → consumer PR 切新 URI → 主仓 bump → radar_cron 跑 gac-gc 删 deprecated | 跨仓协调, 5 阶段计划, 主仓无法独立 |
| **F-3 archive 文件** | 决定: 保留 (历史价值) 还是删 (减少死链) — ADR 决定, 默认保留 + 修链接 |
| **FCM "115 规则" / NORTH-STAR "118 规则"** | 接受现状(历史快照不可改) |
| **`.omo/_knowledge/management/append-only-log-pattern-*` deleted 引用** | 接受现状(archive 文档保留历史) |

## 阶段依赖图

```
S0 (本 PR)
  ├─ F-9 守时间戳 → 1 规则
  ├─ F-10 数字 → 2 文件
  ├─ ADR-0122 计划 → 1 ADR
  └─ ecos M1 commit → 1 submodule commit + 1 主仓 commit

S1 (1-2 周)
  ├─ F-3 + F-4 死链 ─────┐
  ├─ F-5 broker 写 ──────├─ 4 PR + 1 submodule commit
  ├─ F-6 check-* 接 ─────┤
  ├─ F-11 hook 误报 ─────┤
  └─ F-12 gitconfig ─────┘

S2 (3-4 周)
  ├─ F-2 + governance 回升 ──┐
  ├─ F-8 单点 BOS kind ───────├─ 3 PR + ADR-0115 P2+4
  ├─ F-13 omo-debt 删 ────────┤
  └─ ADR-0115 P2+4 ──────────┘

P2 (长期)
  └─ F-7 BOS 跨仓 rename (5 阶段) — 跨仓协调
```

## 责任分配

| 阶段 | 主要责任 | 配合责任 |
|------|---------|---------|
| S0 | governance-team (本 PR) | X-Plane (auto 监控) |
| S1 | governance-team + omo-team (F-5) | gbrain / agora teams (F-3 跨仓) |
| S2 | governance-team + cockpit-team (F-13 + P2) | agora / omo (F-8 + ADR-0115 P2/P4) |
| P2 | agora-team 主导 | omo / metaos (consumer 改) |

## Failure Modes (反模式)

- ❌ "S0 跳过, 直接做 S1/S2" — 立即可做的不做, 治理债累积
- ❌ "S1 跳过 F-5 broker 写, 直接做 F-6" — broker 写不改, F-6 接入的 check-* 工具有 false-positive 风险
- ❌ "S2 跳过 F-2 直接做 F-8" — governance score 持续下滑, 跨仓协调失去依据
- ❌ "P2 F-7 不启动" — BOS 域越界持续, 5 阶段计划作废
- ❌ "用 'gov-' 短前缀记新文件" — 重复触发 ADR-0115 Phase 2 治理面

## Consequences

### 正面

- 18 项 follow-up 有明确阶段 + 责任 + 工作量 + 依赖
- 避免散点 commit 触发 GaC drift
- 阶段间可中断, 不阻塞其他工作
- 与 ADR-0119/0115/0120/0121 现有 roadmap 协同
- governance score 回升路径明确

### 负面

- S1/S2 跨仓协调需多仓 owner 配合
- F-3 4701 死链修复 ROI 低(均匀分布, 无单点大贡献)
- P2 F-7 跨仓 rename 5 阶段需数月, 进度可能慢

## lane 守门实施登记（2026-10-30）

§决策驱动因子「**lane 守门**: 每 commit 单 lane, pre-commit hook 强制」此前**从未真正生效过**
—— 2026-10-30 实锤三条执行路径全部空转：

1. **pre-commit**：`bin/gac/hook-runner.sh` 的 `run_hook_pre_commit` 检查清单里**没有**
   `change-lane-check` ⇒ 从未触发。
2. **CI**：`sgf-policy.yaml` 把它登记为 `--staged`，而 CI 干净检出里没有 staged 文件
   ⇒ 读到空集 ⇒ 恒 PASS（实测 `PASS (0 files, lanes=-)`）。
3. **pre-push / PUSH_RANGE**：`change-lane-check.py` 的按-push-commit-范围判定分支，
   在 `.githooks/` 里**没有任何导出点** ⇒ 从未触发。

⇒ 规则写在 ADR、有实现、有注册，但**没有任何一条路径真正喂过它数据**。
这类空转比「没有这条规则」更危险：它让人以为 lane 纪律在生效。

### 本次落地

- **pre-commit 接线**（`bin/gac/hook-runner.sh`）：新增
  `bin/change-lane-check.py --staged`，**blocking**。判据输入 = 暂存区 = 本次提交实际要
  带上的文件集合 ⇒ 天然是「单个 commit 的变更集」，与本 ADR 的原文语义一致。
  profile 用 `pyyaml`：`classify()` 依赖 sgf-policy 的 gate→lane 映射，缺 yaml 时它会静默
  降级成空映射 ⇒ 判定偏宽（漏判），那比不接线更坏。
- **CI 侧接线**（PR #4979）：`bin/gac/check-change-lane-range.py` + gac-gate.yml 的
  `CR-CHANGE-LANE-RANGE` 步，按 PR base..head 逐 commit 判（advisory）。
- **规则放宽**（`ALLOWED_COMBOS` + `allowed_for`）：`governance_state` 原本是**无条件硬隔离**
  （与任何 lane 混合即拒）。接线前实测（近 120 个 commit 的逐 commit 判据）：
  基线违规 59%，其中「治理面(.omo/) + 文档面(docs/)」同交是仓内**主流收口形态**
  （retro + 台账 + 报告一起交），占全部违规的 27%。该组合现予放宽 ⇒ 违规降到 43%；
  剩余违规**全部**含 code / governance_code / config —— 那些是真该拆的（机制面与治理面
  不同质）。`runtime_snapshot` 的硬隔离不受影响。

### 实测（接线的真实效果）

- 混 lane 提交：真实 `git commit` 被拦下（rc=1），错误信息列出各 lane 与具体文件。
- 单 lane 提交：通过（rc=0）。
- 变异对照：撤销放宽 ⇒ 1 failed；过度放宽 code ⇒ 3 failed；摘掉 hook 接线 ⇒ 命中接线用例。

### 历史欠账处置结论（2026-10-31）

docs(adr-0122): 历史欠账处置结论 —— 台账显形 + 不改写历史（改写被保护分支拒绝）

本段登记「处理 ADR-0122 历史欠账」的实测结论。三个发现改变了处置形态:

**发现一: 历史欠账不会挡住 push**。push 范围从 `merge-base(origin/<branch>, local_sha)`
起算 ⇒ 历史 commit 在 merge-base **之前**, 不在范围内。实测: 一个基于 40 个 commit 前 main
的 stale 分支, 加一个新 commit 后 push 范围只有 1 个 commit。所以历史欠账不是「会挡住
工作」的障碍, 而是**治理面的记录缺口** ⇒ 处置是**登记显形**, 不是豁免机制。
(做成豁免就等于给新提交开了逃逸口, 与规则本意相反。)

**发现二: main 上的「混 lane commit」不是欠账指标**。本仓全 squash 合并 => main 的每个
commit = 一个 PR 的全部内容 => 一个跨多 lane 的 PR 必然产出「混 lane commit」。实测: 全历史
4895 个 commit 里 2665 个「混 lane」, 但最近 40 个 PR 里**只有 18 个 commit 自身混 lane**
(在 PR 分支上就是) —— 后者才是真正的提交形态缺陷。逐条登记几千个 squash 产物是登记
「squash 的记录方式」, 不是登记「欠账」。

**发现三: 改写 main 历史被 GitHub 拒绝**。main 是受保护分支
(`allow_force_pushes: False` + `enforce_admins: True`), 且这是仓库**明文架构决策**
(docs/generated/architecture-deep-analysis.md §17.2「main 分支保护 ✅ 已启用 (direct push
双重拒绝)」+「squash merge ✅ 所有 main 变更」; pre-rebase hook 亦指明授权通道是 merge/PR
合流)。仓内工具 `gac-branch-protection.sh` 只能改必需检查列表, 无权解除 force push 禁令。
⇒ 改写需**先解除保护** —— 那是独立的治理决策, 需单独授权。

**处置**:

1. **欠账台账** `.omo/_truth/registry/lane-debt-ledger.yaml` (生成面): 记 main 侧混 lane
   commit 的**成因分布** —— 用于判断「哪些是分类器边界偏碎」, 「哪些是真正的多面混合」。
   明确标注 squash 结构性产物**不是欠账指标**。台账**不被任何门禁消费** (纯记录面)。
2. **改写工具** `bin/ops/split-commits-by-lane.py` 已就绪并验证: 四项不变量全部成立 ——
   树 sha 逐字节等价、10447 个文件 blob+mode 逐个等价、287 个拆分 commit 全部单 lane、
   PR 号 100% 保留。待授权解除分支保护后可执行。
3. **分类器性能修复**: `classify()` 每次都重读解析 sgf-policy.yaml ⇒ 扫全历史跑不完;
   加 `lru_cache` 后 0.1s。这让全历史口径的统计得以落地。

**留给后续裁决的两项** (本段不夹带):
- `governance_code` 与 `governance_state` 的边界偏碎: 「改一个治理件 + 登记它」这类原子变更
  天然跨两个 lane。实测成因分布里 `boundary-governance-registration` + 
  `boundary-code-vs-governance-code` 合计占多数 ⇒ 分类器侧的边界修正是消化摩擦的主要方向
  (而非改写历史)。
- 43% 的红率是「新提交会被拦」的概率, 随规则生效会自然下降 (开发者会按提示拆提交)。

### 未闭合

- 43% 的红率意味着约一半**新**提交会被拦（历史不改）。这是规则本意（每 commit 单 lane），
  但若摩擦超出可接受范围，需要的不是放宽规则，而是**消化历史欠账**或分批整改提交形态。
- `governance_code` 与 `governance_state` 的边界仍偏碎：「改一个治理件 + 登记它」这类
  原子变更天然跨两个 lane（注册表在 `.omo/_truth/registry/`、ADR 在 `.omo/_knowledge/decisions/`）。
  本次未扩大 `governance_code` 边界（那会让 120+ 文件的 lane 归属变更），留作后续裁决。
- `PUSH_RANGE` 分支仍无导出点（pre-push 侧未接线）；CI 侧已由 `--range` 覆盖。

### pre-push 接线补记（2026-10-30 续）

`PUSH_RANGE` 导出点已补上（`bin/gac/export-push-range.py` + `hook-runner.sh` 的 pre-push 段），
`PUSH_RANGE` 分支的**判据粒度同时被修正**。

**粒度修正（必须记，否则下一个人会以为它本来就是 aggregate）**：
原 `PUSH_RANGE` 分支走 `changed_paths()` → `git diff --name-only <range>`，即把整段范围
**合并成一个文件集合**再判 —— 那是 aggregate 粒度，与本节「每 commit 单 lane」不符，
且实测会**误判**：「commit A = docs」「commit B = 子模块指针」两个 commit 每 commit 单
lane ⇒ 合规，合并判却得到 `{docs, submodule_pointer}` 的假违规（PR #4974 正是这形状）。
现已改为复用 `check_range()` 的 **per-commit** 判据，与 `--range` / CI 侧同口径。

**为什么 pre-push 阶段判 per-commit 有意义**：本仓全 squash 合并，但 pre-push 时分支上
的 commit **尚未被压缩** ⇒ 判据看得到「哪个 commit 混了 lane」，开发者据此拆；
而 squash 落到 main 之后就只剩一个混合 commit，那时已无从拆解。

**与 pre-commit 那道尺的分工**：pre-commit 拦「本次提交」（暂存区）；pre-push 拦
「本次推送的整个 commit 范围」⇒ **兜住绕过 pre-commit 的路径**。实测：用 `--no-verify`
建一个混 lane commit 后，pre-commit 被绕过而 pre-push 那道尺拦下（真实 `git push` rc=1，
精确指出违规 commit 与各 lane 的文件）。

**范围解析的两个坑**（均已实测并写进合同测试）：

1. **base 不能用 stdin 里的 remote_sha** —— 它是推送**前**远端指向的 commit，该对象在
   本地通常不存在（实测 `git cat-file -t` 失败）。取 `merge-base(origin/<branch>, local_sha)`：
   `origin/<branch>` 是 remote-tracking ref，本地必有；与 local_sha 求交即精确表示
   「本地分支相对远端多出的 commit」。
   **为什么不用 `origin/<branch>` 直接当 base**：分支可能落后于远端（远端有别人推的
   commit），那样算出的范围会含**不属于本次推送**的变更。
2. **新分支首次 push 时 `origin/<branch>` 还不存在** —— git 在 push **成功之后**才创建
   remote-tracking ref，而 pre-push 跑在 push 之前。此时退到 `origin/HEAD`（默认分支）
   作 base 候选。解析不出范围时**显式 SKIP 并给出原因**，不输出 `PUSH_RANGE` ⇒ 下游
   看到「没有范围」而不是「范围是空」（后者会被当成无违规而假绿）。

**实测**（真实 push，非模拟）：混 lane 的 push 被拦（rc=1，报出违规 commit 与各 lane 文件）；
单 lane 的 push 通过（rc=0）。

### merge commit 豁免（2026-10-31 补）

**规则与仓库策略直接冲突**：lane 尺要求「每 commit 单 lane」，而 merge commit 天然含
**两侧**的内容 ⇒ 必然混 lane（实测 40 个 merge commit 里 29 个混，73%）。这是合并动作的
**结构性事实**，不是提交形态缺陷。而本仓的合流路径**只剩 merge 一条**：
`pre-rebase` hook 明确拒绝 rebase onto main（「应走 merge/PR 合流」），main 自身又全
squash 合并 ⇒ 一视同仁地拦 merge commit，等于把唯一合规的合流路径堵死。

**处置**：merge 状态下判据**照常计算并报告**，但降级为 **advisory 不阻断**
（`bin/change-lane-check.py` 的 staged 路径）。范围判据（`--range` / PUSH_RANGE）
**不适用**该豁免 —— 它用 `--no-merges`，merge commit 根本不在范围内 ⇒ 范围里的混 lane
都不是 merge 造成的；若那里也按 MERGE_HEAD 豁免，等于给「push 时恰好有未完成 merge」
开了后门（MERGE_HEAD 在 merge 完成前一直存在）。

**MERGE_HEAD 的定位必须精确**（实测踩过两个坑）：

1. `git rev-parse --git-path MERGE_HEAD` 返回**相对路径**（`.git/MERGE_HEAD`），且该
   相对路径是相对**调用 git 时所在 cwd** 的 —— 换 cwd 结果就变（从子目录调用得到
   `../.git/MERGE_HEAD`），拼到别的基准上会指向错的仓库 ⇒ 判据静默失效。
2. `git rev-parse --git-dir` 在 linked worktree 下返回**主仓**的 `.git`，而 worktree 的
   MERGE_HEAD 在 `<main>/.git/worktrees/<name>/MERGE_HEAD` ⇒ 找不到。

⇒ 唯一无歧义的定位是 `git rev-parse --absolute-git-dir`（普通仓 ⇒ `<repo>/.git`；
worktree ⇒ `<main>/.git/worktrees/<name>`，MERGE_HEAD 正是 per-worktree 文件）。
且该查询必须与判据读的 index **同仓**（staged 路径走 `git diff --cached`，cwd=WORKSPACE）
⇒ 「正在创建的 commit」就是 WORKSPACE 仓的 commit，merge 状态按同一个仓判定。

**实测**（真实 git merge 现场，非模拟）：冲突 merge 解决后提交，两侧内容并入暂存区
⇒ 无豁免时 rc=1（`FAIL mixed lanes=code,other`），有豁免时 rc=0 且仍打出 `FAIL` 报告
与 NOTE。**另注**：clean merge（`git merge --no-ff` 无冲突）根本不触发 pre-commit hook
⇒ 豁免只影响**冲突解决后提交**这一条路径。

**合同测试**：`tests/unit/gac/test_change_lane_merge_exemption.py`（5 例，钉住 merge
状态检测、worktree 私有目录定位、报告但不阻断、以及范围判据**不**被豁免）。

## Verification

- [x] S0: make gac-local-gate PASS, F-9 规则加, F-10 数字刷
- [ ] S1 完成后: 4 PR merged, F-5 broker 写生效, F-6 check-* 接入
- [ ] S2 完成后: governance score 100, mof-drift 0 MEDIUM, ADR-0115 P2/4 done
- [ ] P2 启动: agora PR 走 5 阶段跨仓 rename

## Related

- PR #11 (`23702782`) — 系统全面审计 5 维 P0 闭环
- PR #10 (`f7beb558`) — X-Plane ADR-0120 freshness fix + matrix SSOT lint
- ADR-0115 — bin 治理面 4 phase
- ADR-0119 — systemic-optimization 28 item (S0-S3)
- ADR-0120 — freshness semantics
- ADR-0121 — GCSI governance convergence
- P71 baseline recovery pattern
