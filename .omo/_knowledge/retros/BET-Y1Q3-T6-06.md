---
id: BET-Y1Q3-T6-06
type: retro
status: archived
date: 2026-08-18
run_id: 20260818T020320Z-bet-execution-182821e7
workflow_id: bet-execution
bet_id: BET-Y1Q3-T6-06
north_star_ref: docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
scope:
  - bin
  - docs/plans
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: "BET-Y1Q3-T6-06 Retro: 文档治理减负 — 维护模式"
---

# BET-Y1Q3-T6-06 Retro: 文档治理减负 — 维护模式

## Q1 目标回顾
doc-ssot-lint 已达 0 违规基线（186 文件）。目标：停止扩面（新增 lint 规则/文档要求），转纯维护模式；doc 类提交量砍半（两周 217 条 doc 提交 → ~8%）。

## Q2 实际结果
- **维护模式声明（done_when #1）**：已在 PR #1651 落地（`.omo/standards/doc-ssot-contract.md` §维护模式）。
- **基线锁定（done_when #3）**：doc-ssot-lint 保持 0 违规（本次验证：worktree 88 文件 + 共享根 186 文件均 ok=true，conflicts=0）。
- **观察口径（done_when #2）**：新增 `bin/ssot/doc-commit-ratio.py`（近 N 天 doc 类提交占比观察，仅观测不设门槛）。主仓 main 近 14 天实测：**纯 doc 提交 9.4%**（123/1306）、含 doc 提交 40.0%、doc 文件变更 19.6%。纯 doc 口径已接近 ~8% 目标，维护模式正在起效。
- **减法配额**：归档 `bin/ssot/conflict-marker-check.py` → `bin/_archive/2026-08-t6-06/`（零引用孤儿；gate 实际用 `bin/gac/check-conflict-markers.py`）。本次净增减 = +1 新脚本 -1 归档 = 0，符合 T6-05 减法配额。
- **台账修正**：write_surface 过时路径 `registry/x2-freshness-rules.yaml` → `_truth/x2-freshness-rules.yaml`；E2 观察口径引用新工具。

## Q3 目标偏差
- **bet 声明与实际交付意图错位**：run 初始绑定的是 T6-06（文档治理减负），但上一个 agent 曾把它误用于根目录 shadow surface 治理（PR #1657），造成一个 governance-audit run 错绑。本次已按事实收口：T6-06 实际交付维护模式 + 观察工具，根目录治理归 PR #1657。错位的旧 run 已以 blocked 关闭（见交接记录）。
- **doc-ssot-lint 在隔离 worktree 的环境假阳性**：worktree 未 init ecos 子模块时 `--json` 报 L0 约束源缺失（conflicts=1）。init ecos 后恢复 0 违规。这是环境问题，非漂移。
- **done_when #2 是观察型指标**：不能靠一次交付判定完成，需真实提交量积累。本 bet 交付的是观察工具与口径，占比达标留待后续窗口观察。

## Q4 机制沉淀（表面积记账）
- **bin_scripts 净增减**：+1（doc-commit-ratio.py）−1（conflict-marker-check.py 归档）= **0**。减法配额机制（T6-05）在本轮生效，未造成 bin 净增长。
- **验证归因**：workflow verify 在共享根报的 ssot-guardian（agora 指针漂移 / 0字节文件）与 governance-semantic-gate（ADR-0413/0414 frontmatter）均为共享树**存量**问题（concurrent agent 状态 + T6-07 遗留），非本 bet 引入；gac-executor 在共享根 ok=true，worktree 内 rc=1 为子模块不全的环境假阳性。
- **观察口径定义**：doc 类 = 提交含 .md 文件；区分「含 doc 提交」与「纯 doc 提交」两种口径，观察时以主仓 main 为基准（worktree 分支历史有偏差）。

## Q5 后续动作
- 持续用 `python3 bin/ssot/doc-commit-ratio.py --days 14`（主仓 main）观察 doc 占比，待真实提交量积累后复核 done_when #2（目标 ~8%，当前纯 doc 9.4%）。
- 存量债（与本 bet 无关，另开 lane）：ADR-0413/0414 frontmatter 缺失（T6-07 遗留）；共享树 agora 子模块指针漂移。
