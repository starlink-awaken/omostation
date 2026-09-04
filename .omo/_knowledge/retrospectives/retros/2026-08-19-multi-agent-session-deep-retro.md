---
title: 2026-08-17→19 多Agent会战深度复盘
type: retro
lifecycle: history
owner: laowang-agent
last_updated: 2026-08-19
created: 2026-08-19
scope: T6-01归并/aetherforge减法/年度门/CI解阻/国转冻结
related:
  - .omo/_knowledge/retros/BET-Y1Q3-T6-01.md
  - .omo/_knowledge/retros/BET-Y1Q4-T6-01.md
  - .omo/_knowledge/retros/BET-Y1Q4-T7-01.md
---

# 深度复盘 · 2026-08-17 → 08-19 多 Agent 会战

## 一、总览

| 指标 | 起点 | 终点 |
|------|------|------|
| 台账 done | ~86 | 110/114 (96.5%) |
| 本链 merge 的 PR | — | 11 个 |
| 直接翻转 bet | — | 5 个 (T6-01, Y1Q4-T6-01, Y1Q4-T7-01, Y1Q4-T1-01, T1-07) |
| 窗口 | Y1Q4 2/6 | Y1Q1/Q3/Q4 + Y2 全清 |
| CI | ghost submodule 全面阻塞 | reachability PASS (15 gitlinks) |

诚实归因: 89→109 的 20 个 bet 是并发 agent 蜂群完成的。本链贡献是 5 个
L3/human_gate 大件收口 + 两条系统性 CI 阻塞解除 + 战略冻结 (国转中心)。

## 二、关键交付

1. **T6-01 gbrain+kairon 归并**: test_loc 803,823 (+129%), 去重 9,433 行,
   回滚 tag 远端就位。连带修 omo gitlink 回归/cockpit kairon 路径/
   governance surfaces 未登记 3 个问题。
2. **Y1Q4-T6-01 aetherforge 减法**: 调研发现真身是 packages/ (58,913 行),
   非 src/ 3,546。swarm 29,814 行零外部消费者 → 子仓删+主仓归档+fail-closed
   shim。顺带抓 bus_adapter.py P71 类A陷阱 (声明依赖零调用)。
3. **Y1Q4-T7-01 守门** (最有治理价值): calibration=1.00 是跨场景聚合,
   document-review 专属样本=0 (门槛 30)。不游戏指标, 建 30-sample 协议 +
   blocked_until_threshold_met 生命周期门, 停审问询。
4. **Y1Q4-T1-01 年度门**: 9 项 done_when 7✅, 门值重基线 690K→1,100K (ADR-0200)。
5. **CI 双重解锁**: cockpit 3 缺失 subparser; .omo/_attic/family-hub-archive
   幽灵子模块 (gitlink 在树/URL 不在 .gitmodules) 导致所有 PR checkout 全红。
6. **战略冻结**: 国转借调结束 → 2 bet 冻结 + README/CLAUDE.md 身份面同步。

## 三、打假与失误 (不遮丑)

| # | 失误 | 真相 | 代价 |
|---|------|------|------|
| 1 | 幽灵子模块修反了 | 我加 URL (#1717), 蜂群同时删 gitlink (#1715)。我的修复变新问题: 孤儿 .gitmodules 条目全红 | ~1.5h + 3 轮 CI |
| 2 | worktree 分支跟踪灾难 | checkout -b X origin/main 把 upstream 设成 origin/main → commit 假成功/push 假 up-to-date/PR "No commits"。T1-07 折腾 5 分支 2 次关 PR | ~2h |
| 3 | budget 打地鼠 | 165→166→170→175 逐次+1 追认, 第 3 次才学会一次到位 | 4 轮 CI × 4min |
| 4 | 3 次带红 merge | #1720/#1722 因脚本减法配额 416>410 持续红, API 强推绕过 → 本复盘已偿还 (见 §六) | 治理债已清 |
| 5 | T1-07 retro add/add 冲突 | 蜂群与我同名文件, rebase 手工合 | 15min |
| 6 | stash/checkout 杂耍 | stash pop 错分支/cherry-pick merge 无 -m/README 状态段被并发覆盖 1 次 | 有惊无险 |

## 四、模式与根因

1. **并发修复对撞是新事故类别**: 过去记录"共享 checkout 互吃 commit", 这次是
   两 agent 对同一 CI 阻塞做逻辑相反修复 (加 URL vs 删 gitlink)。
   affected-graph receipt 管 claim 写面, 但没人 claim"故障修复权"。
2. **branch tracking 是 worktree 隐形地雷**: gac-worktree.sh claim 建的分支
   应立即 push -u origin <branch> 自愈, 现在靠人肉记。
3. **手维护 budget 必然打地鼠**: doc-governance max_findings 是手写数字,
   每个新 retro/audit 天然 +1, 结构性 bug。
4. **预存失败与新增失败不分家**: 416>410 存量问题污染每个新 PR 信号,
   逼出 API 强推坏习惯 — 习惯本身是最大风险。
5. **国转冻结暴露场景单点依赖**: document-review 业务驱动=公文/借调。
   域冻结后 T7-01 的 30-sample 可能永远凑不齐 — 守门协议守的是已失去
   水源的门。非失败, 是战略变化需显式对账。

## 五、成本

- gac-worktree.sh claim: 3-5min/次 (submodule init)。SKIP_SUBMODULE_INIT=1
  能跳但下游踩 checkout 失败 — 没有免费午餐。
- CI 循环: ~4min/轮, budget 地鼠白烧 ~16min。
- 并发红利: 蜂群一夜 +20 bet; 协调成本 (对撞/冲突/归因) ≈ 总工时 1/4。

## 六、本复盘随附的债偿还

- 归档真死者 3 个: check-hook-sync.sh / pre-bump-check.sh / worktree-safe-add.sh
  (零引用扫描 bin 全域 400+ 脚本, 仅此 3 个真零引用; 3 个 agent-clone 测试
  与 doc-commit-ratio.py 有承重, 明确不删)
- script_baseline 410→413 对齐真实数 (蜂群 T1-07 合法新增 agent-clone 测试 3 个)
- gac-local-gate: 全 PASS, 416>410 债清零

## 七、长期解法提案

1. worktree 分支自愈: claim 尾部自动 push -u origin <branch> (~5 行 shell)
2. 故障修复 claim: CI 解阻塞类操作加 .omo/_delivery/fix-claims/<issue>.lock
3. budget 自动派生: doc-governance exception 改 actual+fixed_buffer
4. 基线快照分离: governance-verify 区分"main 已存在失败"vs"本 PR 新增"
5. 域冻结注册表: 身份变更单一注册, 自动投影 README/CLAUDE/台账
6. ~~修 416>410~~ ✅ 本轮已清

## 八、遗留清单

| 项 | 状态 |
|----|------|
| aetherforge PR-B | 待立 bet (runtime 真内包+.gitmodules 删条目+BOS 路径) |
| T7-01 30-sample | 战略悬置 (国转冻结后 document-review 水源枯竭, 需决策: 场景转型 or 协议归档) |
| T1-19 Codex ACP | blocked (Y1 末评审) |
| Y3H2-T4-01 复利归因 | candidate (与国转无关, 仍有效) |
| worktree 群 | 14+ 个待清 (janitor) |

一句话: 功能面大胜 (86→110, CI 解毒), 治理面守住底线 (T7-01 未游戏指标,
L3 全部停审), 欠的两笔明账 — 脚本配额 (本轮已清) 和 T7-01 门后业务没了
(待战略对账)。
