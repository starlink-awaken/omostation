---
title: 收敛期六项 · 落地执行总表
status: active
type: execution-status
owner: 夏明星
created: 2026-07-15
updated: 2026-07-17
related:
  - .omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md
  - .omo/_knowledge/decisions/0218-agent-isolation-p0-verify-and-hygiene.md
  - docs/RUNTIME-DAEMON-REMEDIATION.md
  - docs/HEALTH-SCORE-ISC3-DESIGN.md
  - docs/CONVERGENCE-GOAL-DISPATCH.md
  - docs/STRATEGY-INDEX.md
note: >
  ADR-0210 收敛期 6 项落地实况。2026-07-15 沙箱盘点 → 2026-07-17 授权终端激活收口。
  运行时数字权威源 .omo/state/*.yaml。
---

# 收敛期六项 · 落地执行总表

> **2026-07-17 收口结论**：六项已从「已建未验 / 真·从零」推进到 **代码合 main + 运行态激活**。
> 杠杆仍是「核实+激活+收尾」——不是重造。运行时数字以 `.omo/state/*.yaml` 为准。

## 一、六项落地总表（2026-07-17）

| # | 收敛期项 | Pri | 真实状态 | 已建 / 落地 | 验收证据 | 归属 |
|---|---------|-----|---------|------------|---------|------|
| 1 | Agent Isolation | P0 | ✅ **达标** | pre-push + worktree + branch protection | `gh api .../protection` HTTP 200；ADR-0218 Confirmation | PR#411 |
| 2 | 修复 L1 runtime | P0 | ✅ **达标** | gateway 重启拾取 `_is_transient`；probe healthy | agora-gateway `healthy (probe)`；ratio ≥ 0.9 | 运行态 + PR#411 |
| 3 | 重构 health_score | P1 | ✅ **达标** | ISC-3 权重 0.3/0.5/0.2；执行面 governance；单源 ratio | compass + runtime@4e002ef dual-writer 修复 | PR#412 #413 |
| 4 | gitlink 巡检 cron | P1 | ✅ **达标** | foundry 5:45-gitlink-check；LaunchAgent 6h | `knowledge-foundry-cron.py` 槽位；故意 drift exit 1 | PR#411 + launchd |
| 5 | 单写者 + 门禁免疫 | P2 | ✅ **达标** | pre-commit write-owner-audit + repair-draft `--commit` | 非系统 staged system.yaml 被拦 + 本地 draft commit | PR#411 #412 |
| 6 | KOS 索引启动 | P1 | ✅ **已启动** | `kos-seed-import.py`；kos-index.sqlite | documents ≥ 673（含创意创作首批） | PR#411 + 入库 |

## 二、M1 门禁（ADR-0210）

| M1 门禁 | 2026-07-15 盘点 | 2026-07-17 收口 |
|---------|----------------|----------------|
| 并发 agent 主仓冲突 = 0 | 机制达标 | 机制持续（worktree+PR） |
| daemon 在线率 ≥ 90% | 假红灯 0.6–0.75 | **1.0 单源**（4/4 daemon；idle≠离线） |
| health_score 反映执行面 | 权重对/输入脏 | ISC-3 权重 + execution_surface + dual-writer 闭合 |

### 活体 SSOT 快照口径（示例；以现盘为准）

- `service_online_ratio`：health / system / `runtime_health_summary.ratio` **同源**
- agora-gateway：`healthy (probe)`（stdio transient 不计 dead）
- runtime 指针：`projects/runtime@4e002ef`（idle/healthy 计在线）

## 三、合入 PR 账本

| PR | 内容 |
|----|------|
| [#411](https://github.com/starlink-awaken/omostation/pull/411) | G-CONV.4/1/5/6 并行：foundry gitlink、ISC-4 confirm、write-owner、kos-seed、dispatch 文档 |
| [#412](https://github.com/starlink-awaken/omostation/pull/412) | G-CONV.3 执行面 + G-CONV.5 `--commit` + write_owners 路径规则 |
| [#413](https://github.com/starlink-awaken/omostation/pull/413) | runtime dual-writer：idle 在线 + top-level ratio 与 summary 单源 |

## 四、Workflow 纪律（dogfood）

- ADR-0203：`agent-workflow start → claim → verify → closeout`
- 独立 worktree + PR 合 main（禁止直推 main）
- 代表 run-id：
  - `20260717T121847Z-project-code-change-5a7f21ed`（#411）
  - `20260717T123831Z-project-code-change-127ac5fa`（#412）
  - `20260717T125342Z-project-code-change-a83e9a76`（#413）

## 五、G-CONV.7 Swarm 纪律（M1 硬前置 · ADR-0220）

| 项 | 状态 |
|----|------|
| 四闸门 D1–D4 | ✅ PR #415 + skeptic #416 |
| 72h 观测窗 | 🟡 **window_open**（`window-start` 2026-07-17T13:52:27Z → target +72h） |
| 冲突计数 | 读 `python3 bin/gac/swarm-discipline-cli.py window-status` |
| M1「冲突=0」 | **未宣布达标** — 仅当 elapsed≥72 且 conflict_count=0 |
| M1 重判 CLI | `python3 bin/gac/m1-closeout-report.py --root <live>` → `m1_verdict` / `phase2_recommend` |

Foundry 5:50 槽位持续落盘 window-status；orphan_commit 扫描纳入观测。  
T+72 用 `m1-closeout-report.py` 一键重判（window_open 时禁止 phase2_recommend）。

## 六、剩余观察项（非阻塞）

1. **Workspace 功能分支**若仍停在 `docs/*`，日更 foundry LaunchAgent 的 `WORKSPACE` 指向该树时，需 merge/rebase `origin/main` 才能自动吃到 5:45/5:50 槽位（代码已在 main）。
2. **governance 子分**在多 worktree / 多 lock 时会诚实下探（ISC-3 设计如此）；composite 可能低于 100 而 runtime 仍满——属执行面敏感，不是假红灯。
3. **KOS 季度持续增长**：首批已 >0；后续靠季度入库节奏，非本轮一次性关门。
4. **foundry 其它槽位**（port-governance 等）偶发 fail 与 G-CONV.4 无关；gitlink / swarm-window 槽位独立。
5. **裸 `git --no-verify`** 仍可跳过 hook（git 设计）；agent 路径用 `bin/gac/swarm-git`。

## 六、历史盘点（2026-07-15，保留对照）

> 贯穿结论曾是：6 项里 5 项「已建未验」，仅 KOS 真·从零。  
> 2026-07-17 已完成「最后一厘米」激活；详见 §一。

---

*收敛期执行总表 · 更新 2026-07-17 · 夏明星 · 运行时数字以 .omo/state/*.yaml 为准*
