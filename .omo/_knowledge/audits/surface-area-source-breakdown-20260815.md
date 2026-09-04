---
title: 表面积暴涨溯源审计 — +926K 行增量归因
type: audit
status: final
owner: governance-team
created: 2026-08-15
lifecycle: history
related:
  - bin/plan/bet-ledger.py
  - docs/plans/3y-bet-ledger.yaml
context: >
  触发: bet-ledger.py surface 显示 src_loc 较基线 726,412 → 1,652,857 (+926,445,
  +128%)。本审计回答"增量主要来自哪里"。双口径: (1) git numstat 增量归因 (自
  基线日 2026-08-06, 主仓 + 19 子模块各自 git log --numstat 累计); (2) 现状
  LOC 快照 (os.walk 按扩展名累计, 排除 .git/node_modules/__pycache__/.venv/dist)。
  两口径统计范围不同 (surface 用 git tracked 口径, 现状快照含工作树全部文件),
  数字不直接可比, 差额如实标注。
last_updated: 2026-08-25
---

# 表面积暴涨溯源 — 2026-08-15

## 1. 结论先行

**9 天（2026-08-06 → 08-15）全域净增 ≈ 389,030 行**（git numstat 口径），增量 Top 6 子模块贡献 143K+，主仓根自身贡献 +217K（占总净增 56%）。剩余 ~537K（926K surface 增量 − 389K git 净增）为**口径差**：surface 的 git tracked 口径把 gbrain 重写（+468K/−468K，净 0）等大规模重写的**加法侧**全额计入，而 numstat 净值口径把它抵消——两者都真实，回答的问题不同。

## 2. 主表：git numstat 增量归因（自 2026-08-06）

| 排名 | 位置 | +行 | −行 | 净增 | 说明 |
|---|---|---|---|---|---|
| — | **主仓 root** | 262,184 | 44,957 | **+217,227** | 56% 净增来自主仓自身（bin/ + docs/ + .omo/） |
| 1 | projects/omlxc | 51,094 | 2,818 | +48,276 | 新 agent 运行时项目，几乎纯增 |
| 2 | projects/omo | 37,047 | 1,074 | +35,973 | 治理内核持续膨胀（workflow/blueprint） |
| 3 | projects/agora | 119,602 | 90,475 | +29,127 | **大规模重写**（net 低但 churn 极高） |
| 4 | projects/ecos | 17,606 | 614 | +16,992 | MOF/L0 生成器 |
| 5 | projects/cockpit | 18,186 | 5,445 | +12,741 | CLI/UI |
| 6 | projects/aetherforge | 11,367 | 1,242 | +10,125 | 8 月新增项目（基线后建库，全体量即增量） |
| 7 | projects/runtime | 6,805 | 75 | +6,730 | |
| 8 | projects/l4-kernel | 7,380 | 893 | +6,487 | |
| 9 | projects/kairon | 2,168 | 90 | +2,078 | |
| 10 | projects/cockpit-ui | 2,076 | 7 | +2,069 | |
| 11 | scripts | 1,210 | 12 | +1,198 | |
| — | projects/gbrain | **468,200** | **468,200** | **0** | **重写/rebase 对称噪音**——加法侧 468K 正是 surface 口径暴涨的最大单点来源 |
| — | metaos/c2g | 13 | 6 | +7/0 | 基本静止 |
| — | family-hub/model-driven/omo-debt/bus-foundation/observability | 0 | 0 | 0 | 基线后无提交 |
| | **合计 19 子模块** | 742,754 | 570,951 | **+171,803** | |
| | **全域（含主仓）** | | | **≈ +389,030** | |

抽样命令（可复现）：`git -C <mod> log --since=2026-08-06 --numstat --pretty=format:` 逐行累计；主仓在隔离 worktree 测得（避免主仓 feature 分支工作树污染）。

## 3. 校验口径：现状 LOC 快照（os.walk 全工作树，2026-08-15）

| 位置 | 当前 LOC | | 位置 | 当前 LOC |
|---|---|---|---|---|
| scripts | 2,033,356 ⚠️ | | projects/agora | 177,186 |
| projects/kairon | 222,418 | | projects/runtime | 39,596 |
| 主仓根(除子模块) | 617,101 | | projects/l4-kernel | 21,433 |
| projects/gbrain | 404,530 | | projects/omlxc | 42,812 |
| projects/omo | 169,723 | | 其余 9 个 | <16K each |

⚠️ `scripts` 的 203 万行与 surface 口径差异极大——该目录含大量数据/生成资产（非手写源码），**os.walk 口径把数据文件也算 LOC**。这印证了 surface 用 git tracked + src 扩展名口径的合理性，也说明"现状快照"只做结构参照，不作增量论据。

**口径闭合说明**：surface +926K vs numstat 净增 +389K，差 ~537K。主因有二：(1) gbrain 对称重写的加法侧 468K 计入 surface、在 numstat 中被减法抵消；(2) surface 基线快照（2026-08-06 硬编码于 `bet-ledger.py:49`）与当前 git tracked 集合的差异（aetherforge/omlxc 等基线后新增项目全体量计入）。两者皆为口径现象，**不是数字造假**，但 surface 指标对"重写型变更"的灵敏度值得在归并 bet 中注意。

## 4. 归因叙事（给后续归并 bet 的输入）

1. **主仓根是最大增量源（+217K, 56%）**——不是某个子模块，是 bin/ 309→476 脚本、docs、.omo 注册表。T6-SUBTRACT 轨道的减法目标应优先对准主仓根。
2. **omlxc/omo 双引擎 9 天 +84K**——两者都是"新建即增长"型（omlxc 全新项目、omo 治理内核），有真实功能诉求，但增速值得在下一次 plan review 中对照其 bet 密度。
3. **agora 是 churn 之王（±120K/90K）**——重写密集，每次重写在 surface 口径下都"涨"。若要压 surface，减 agora 的重写频率比删代码有效。
4. **gbrain +468K/−468K 净 0**——纯重写噪音，但 surface 口径被它推高 ~468K，占 +926K 的一半。**这是 surface 指标设计问题**：建议后续 bet 给 surface 加 numstat 净值列（本审计的脚本可直接复用）。
5. **aetherforge/omlxc 为基线后新建**——"增量"含项目出生体量，与"既有项目膨胀"性质不同，归并判定时应分开。

## 5. 方法限制（如实）

- numstat 的二进制/重命名/移动文件按 0 行计，真实增量略低估
- `--since` 按 commit 日期，跨基线日的长分支 merge 可能漏计/多计
- 主仓 numstat 在隔离 worktree 测（其 HEAD=origin/main cd550370 时代），与主仓原位 feature 分支的 log 集有差异
- 现状快照含未跟踪文件，与 git tracked 口径不闭合处已在 §3 标注
