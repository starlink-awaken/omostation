---
schema: md/v1
status: active
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-T9-01 Closeout Retro — 12 个信号全为真实并发，零假信号零残留"
bet_id: BET-Y2Q4-T9-01
created: "2026-09-26"
run_id: 20260926T121053Z-governance-state-mutation-5c4122d0
---

# BET-Y2Q4-T9-01 Closeout Retro

> **TL;DR**: 假设被证据推翻——health 执行面的 12 个并发冲突信号**不是治理残留，
> 是真实的多 agent 并发负载**。run_pressure = 0（N1 治本生效，70 个 run 记录 0 活跃），
> wt_pressure = 14−2 = 12，12 个 worktree 逐个画像后 0 个可安全清理：9 个当日活跃
> （含另一 agent 正在交付我铸造的 T4-01），2 个带未提交 WIP（删即毁现场），1 个 codex
> 会话基底。复测 concurrent_conflicts 12→**10**（并发 agent 自行释放了 2 个）——信号
> 随真实负载自愈，恰证明它工作正常。真正的结构性问题：`wt−2` 免费额度 vs 常态并发
> 8–11 → 信号饱和为常数扣分（信息量为零），已出 owner 决策提案（本 bet 未动阈值/权重）。

## 计划 vs 实际（done_when 对照）

| 项 | 计划 | 实际 |
|---|---|---|
| 12 信号逐个归因表 | ✅ | `docs/plans/t9-01-concurrent-signal-attribution-2026-09-26.md`（逐 worktree 处置 + 理由） |
| 真残留清理留痕 | ✅ | **可清理 = 0**（逐项说明为何不可清）——"假设有残留"被证据否定 |
| 假信号根因修复 + hermetic 测试 | ✅ | 无假信号可修；交付 `tests/test_compass_radar_concurrency.py` 7 用例（active 去重/坏 YAML 跳过/免费额度/git 降级/权重锚定） |
| 复测 ≤ 2 且执行面显著回升 | ⚠️ 部分 | 12→**10**（≤2 在不删他人活跃 worktree 的红线内不可达）；执行面 4→**20**，复合 36→**47**（radar dry-run 全量重算，多因子） |
| git diff 证明未改权重 | ✅ | `_W_*` 原封，另有测试锚定 8（变更必先红） |

## 归因方法（可复算）

1. `_count_concurrent_conflict_signals` 源码 → 信号 = run_pressure + wt_pressure；
2. 主 checkout runs 目录 `status=active` 计数 → 0（70 记录全关）；
3. `git worktree list --porcelain` 逐个 `log -1` + `status --porcelain` 画像 → 归因表。

## 反思

1. **指标告警 ≠ 指标错误**：bet 立项时默认"高扣分 = 有残留可清"，实际是"信号如实
   报告了系统真实的并发形态"。先归因后动手的纪律避免了为凑 ≤2 而删他人 WIP 的事故。
2. **饱和指标是无信息指标**（D6）：恒定 ~10 扣分让 health 对"真冲突日"失去分辨率。
   修复属指标语义变更（基线中位数/扣分上限/观测与告警拆分三案并陈），归 owner 走 ADR——
   正确的下一步不是本 bet 越权改数，而是把决策卡递上去。
3. 并发生态的自愈力被实测证实：快照到复测的 2 个 worktree 由其他 agent 自行 release，
   卫生习惯已内化。

## CI 拦截与元数据卫生（2026-09-26 补记）

首次 CI：gac-gate FAIL 于 `legacy-omo-knowledge-enums` 预算（71 > 70）——本会话
T1-04/T3-02/T9-01 三个 retro 均用了 legacy 枚举 `status: completed`（沿袭 SH-5.x
样例，而该样例本身即在 legacy 预算内）。处置：**降预算而非抬预算**——三个 retro
（含已合并入 main 的 T1-04/T3-02，均本会话产物）统一改为合规 `status: active`
（283 篇存量主流惯例），本地 doc-governance-check PASS（4420 文件）。跨 BET 触碰
仅限本会话自产文件的 1 行元数据修正，在此如实记录。

## 后续

- owner 拍板归因表 §3 的 A/B/C 三案（任一走 ADR）；
- T4-01 已由并发 agent 认领开工（`ws-bet-y2q4-t4-01`）——本会话让出，避免双做；
- 剩余 pending BET：T10-02 / T10-01 / T6-01。
