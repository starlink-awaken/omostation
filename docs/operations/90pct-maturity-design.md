# 架构成熟度 90% 设计 — Round 2 (差距治理深化)

> 生成: 2026-08-24 · 状态: 草案 (待审阅)
> 依据: `bin/gac/maturity-scorecard.py` (6.8/10 → 目标 9.0) + 台账状态 + 本轮治理踩坑实证
> 决策流程: grill-me 设计树 (用户授权 "全面按照你的推荐"), 详见 ADR/决策卡
> 本文件同时是 iterable 分项的验证开关 (`maturity-scorecard.py::score_iterable` 检测本文件存在)

---

## 0. 目标

| 指标 | 当前 | 目标 | Gap |
|------|------|------|-----|
| 架构成熟度 (maturity-scorecard) | 6.8/10 | 9.0/10 | 2.2 |
| Y1Q3 台账收尾 | 37/39 | 39/39 | 2 bet |
| 治理自进化债 (本轮踩坑) | 4 项未闭合 | 全闭合 | 4 bet |

## 1. 关键发现: 6.8→9.0 需要两条腿

`maturity-scorecard.py` 每项是**二元检测** (过=8 分, 不过=6 分), 上限 8/9 (optimizable 最高 9)。
即便 4 个 6 分项全修好, 也只到 (8+8+8+8+8+9)/6 = **8.17**。

**要到 9.0, 必须让 scorecard 检测粒度升级** (加 9/10 档验证标准), 否则 9.0 数学上不可达。

> 这是"治理自进化"的实证: 衡量工具本身需要进化, 而不只是修分项。

## 2. 差距清单 (双层)

### 第一层: 成熟度分项骨架 (G1-G6)

| # | 分项 | 当前 | 差距 | 方案 | 验证开关 (过=8) | 对应 bet |
|---|------|------|------|------|----------------|---------|
| G1 | evolvable | 6 | script registry 有 gaps | 登记全部 444 scripts | `script-registry.py validate` = VALIDATION PASSED | BET-Y1Q3-T10-01 |
| G2 | iterable | 6 | 无 phased plan | 本文件 (含 Phase 1-5) 落盘 | 本文件存在 | BET-Y1Q3-T10-02 |
| G3 | traceable | 6 | 部分 ADR 链接 broken | 修复 broken ADR links | `adr-link-validator.py` rc=0 | BET-Y1Q3-T10-03 |
| G4 | troubleshootable | 6 | 部分 checks 缺 owner | 完成 owner 字段迁移 | `governance-migration.py --dry-run` = No changes needed | BET-Y1Q3-T10-04 |
| G5 | observable | 8 | 未集成新指标 | compass_radar 集成新指标 | compass_radar 输出含新指标 | BET-Y1Q3-T10-05 |
| G6 | (scorecard 本身) | — | 检测封顶 8/9 | **scorecard 粒度升级到 9/10 档** | scorecard 能产出 9/10 | BET-Y1Q3-T10-06 |

### 第二层: 治理自进化债 (G7-G10, 本轮踩坑实证)

| # | 债 | 现象 | 方案 | 对应 bet |
|---|-----|------|------|---------|
| G7 | Droid-Shield run-id 误报 | run-id 被当 secret, 拦全 workspace push (CONV-3 被堵) | run-id 占位符化规范 + 治理文档规则 | BET-Y1Q3-T10-07 |
| G8 | closeout 硬门/bet 绑定缺失 | waiver run 无 bet → vision→retro 拦 closeout | 治理演进专属 bet 机制 | BET-Y1Q3-T10-08 |
| G9 | worktree submodule init 策略 | 12 个 submodule 未 checkout → gate 环境性失败 | worktree init 策略 + gate 环境感知 | BET-Y1Q3-T10-09 |
| G10 | 成熟度口径三方对齐 | health(70→90) vs scorecard(6.8→9.0) vs 台账验证态 不一致 | 三方口径统一 SSOT | BET-Y1Q3-T10-10 |

### Y1Q3 收尾 (G11-G12, 已有 bet 认领)

| # | bet | 说明 | 工作量 |
|---|-----|------|--------|
| G11 | BET-Y1Q3-T1-11 | platform-rebase 独立 clone 退役 provenance 收敛 | 1 day |
| G12 | BET-Y1Q3-T6-14 | resident 常驻体系与治理接线深度复盘 | 4 hours |

## 3. Phase 划分 (iterable 验证需要)

- **Phase 1 (速赢, 0.5 day)**: G12 (4h) + G2 (本文件已落) — 立即可闭合
- **Phase 2 (分项修复, 2-3 day)**: G1 + G3 + G4 + G5 — 4 个 6/8 分项过验证开关
- **Phase 3 (自进化, 2-3 day)**: G6 + G7 + G8 + G9 + G10 — scorecard 升级 + 治理债闭合
- **Phase 4 (收尾, 1 day)**: G11 (1 day) — Y1Q3 台账 39/39
- **Phase 5 (校准)**: 重跑 scorecard 确认 9.0 + 口径对齐 + 远期 Y3 观察项登记

## 4. Bet 映射汇总

| Bet ID | 差距 | Phase | 预计 |
|--------|------|-------|------|
| BET-Y1Q3-T10-01 | G1 evolvable | 2 | 1 day |
| BET-Y1Q3-T10-02 | G2 iterable | 1 | 0.25 day |
| BET-Y1Q3-T10-03 | G3 traceable | 2 | 0.5 day |
| BET-Y1Q3-T10-04 | G4 troubleshootable | 2 | 0.5 day |
| BET-Y1Q3-T10-05 | G5 observable | 2 | 0.5 day |
| BET-Y1Q3-T10-06 | G6 scorecard 升级 | 3 | 1 day |
| BET-Y1Q3-T10-07 | G7 Droid-Shield | 3 | 0.5 day |
| BET-Y1Q3-T10-08 | G8 closeout 硬门 | 3 | 0.5 day |
| BET-Y1Q3-T10-09 | G9 worktree init | 3 | 0.5 day |
| BET-Y1Q3-T10-10 | G10 口径对齐 | 3 | 0.5 day |

## 5. 验收标准

1. `maturity-scorecard.py` overall ≥ 9.0 (需 G6 完成, 否则封顶 8.17)
2. `script-registry.py validate` PASS (G1)
3. `adr-link-validator.py` rc=0 (G3)
4. `governance-migration.py --dry-run` "No changes needed" (G4)
5. Y1Q3 台账 39/39 (G11+G12)
6. 4 笔治理自进化债全部闭合 (G7-G10)

## 6. 远期观察项 (Y3, 本轮不做)

- Y3H1 3/4 + Y3H2 3/4 (各缺 1 bet) — 记入规划文档, Y3 前校准
- family-hub (paused) 若 Phase 49+ 成真实目标可复活 (ADR-0423)
