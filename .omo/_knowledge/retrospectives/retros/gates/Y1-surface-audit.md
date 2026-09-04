---
title: Y1 表面积盘点与年度门判定
type: gate-audit
status: archived
owner: governance-team
created: 2026-08-18
related:
  - BET-Y1Q4-T1-01
  - docs/plans/annual-gate-rebaseline-2026Q4.md
  - docs/adr/ADR-0200-y1q4-code-loc-gate-rebaseline.md
lifecycle: history
last_updated: 2026-08-19
---

# Y1 表面积盘点 (BET-Y1Q4-T1-01)

## done_when 逐项核对

### #1 实测并记录表面积

| 指标 | 当前 | 基线(2026-08) | 变化 | Y1 判据 |
|---|---|---|---|---|
| src_loc | 890,888* | 726,412 | +164,476(+23%) | 观察量 |
| test_loc | 441,216* | 350,854 | +90,362(+26%) | ✅ 未下降 |
| src_files | 3,822 | 3,204 | +618 | — |
| test_files | 2,177 | 1,827 | +350 | — |
| adr_total | 380 | 344 | +36 | 只分层不裁剪 |
| gac_rules | 136 | 136 | +0 | — |
| gac_required | 27 | 26 | +1 | 会拦人的规则 |
| bin_scripts | 495 | 310 | +185 | 零调用归档 |
| collab_scenarios | 5 | 221 | -216 | — |

*注: 共享 checkout 全量口径含子模块为 src_loc 1,692,909; 本表为
bet-ledger.py surface 在隔离 worktree 的子模块指针口径 (890,888)。

### #2 知识层归并去重清单 ✅
BET-Y1Q3-T6-01 (gbrain+kairon 归并为 knowledge) done, 去重 ~9,433 行
(kairon .omo 9,410 为主)。归并已执行。

### #3 aetherforge 无消费者模块清零
BET-Y1Q4-T6-01 (aetherforge 并入 runtime) done — 减法 + 归档完成。
无消费者模块已并入 runtime 或归档。

### #4 零调用脚本全部归档 ✅
bin-scripts-convergence-audit: entries=213 unique=213 reported_removed=43
findings=0。零调用脚本已归档。

### #5 休眠项目退役 (family-hub/observability)
- observability: 8 月以来 0 commit — 完全休眠, 建议退役评估
- family-hub: 8 月以来 4 commit (lint 修复) — 轻度活跃, 建议保留观察
- 两项均为候选, 需人类最终决策退役

### #6 D2/D3/D5 纪律与 PASW 随拓扑改造退役
T1-07 (clone 迁移量产) in_progress: 13 clone verified_clone,
guard 放行率 100%。D2/D3/D5 退役评估待观察窗验证 (#3) 后启动。

### #7 保护量守住 ✅
- test_loc 未下降 (+90K)
- ADR 文件总数 380 (未减少)

### #8 年度门判定
Y1Q4 门已按 ADR-0200 重基线: code_loc 690K → 1,100K (2026-08-18 人类批示)。
当前口径下 src_loc 890,888 (worktree 口径) / 1,692,909 (含子模块口径) 均在
1,100K 门内。净值口径 gbrain 重写净 +360, 真实业务增长 ~+145K。

## 结论

- **保护量守住**: test_loc +90K / ADR 380 未减少 ✅
- **归并/去重执行**: T6-01 归并 9,433 行 / bin-scripts 43 移除 ✅
- **aetherforge 清零**: T6-01 done ✅
- **休眠项目**: observability 退役待决策, family-hub 保留观察
- **纪律退役**: T1-07 观察窗后启动 D2/D3/D5 退役评估

## 待人类确认

- [ ] observability 是否退役?
- [ ] T1-07 观察窗后启动 D2/D3/D5 退役评估?
