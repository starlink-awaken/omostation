---
title: 场景卡存储归一提案 — 三套存储对账与收敛路线
type: plan
owner: governance-team
last_updated: 2026-09-05
bet: BET-Y2Q1-T7-03
---

# 场景卡存储归一提案 (BET-Y2Q1-T7-03)

> 状态: **待夏明星架构拍板** — 本提案只陈述事实与选项, 不含已执行的迁移

## 1. 现状对账 (2026-09-05 实测)

| 存储 | 存量 | 读写方 | 语义 |
|------|------|--------|------|
| `docs/scene-cards/` (含 v2/ 子目录) | 63 张 | scene-card-lifecycle.py (五档 transition)、scene-card-registry.py、agent-workflow 场景分发 | 主力舰队: bet/falsifier/lifecycle/activation 全生命周期 |
| `.omo/_truth/scenarios/` | 5 张 | scene-card-review.py (calibration/promote/weekly-review)、scene-card-candidates.py | 校准与审查视图 (scene-shadow-activate skill 描述的 calibration ≥0.6 在此) |
| `.omo/_truth/registry/` 注册表衍生 | — | scene-card-connector/intake-pipeline/task-bridge (工作面连接器) | 管道中转, 非卡片本体 |

**症状**:
1. 同名概念两处定义 — scene-shadow-activate skill 指引新卡写入 `.omo/_truth/scenarios/`, 而实际 63 张主力卡在 `docs/scene-cards/`; 两套 validate/lint 口径不同 (v2 schema vs calibration)
2. 升级路径分裂 — lifecycle 工具管五档, review 工具管 promote, 互不知晓对方的 tier
3. shadow→assisted 的 trial 证据链刚在 BET-Y2Q1-T7-02 打通 (Check4 按 scene 精确匹配), 但只覆盖 lifecycle 侧

## 2. 选项 (老王推荐 A)

### A. 归一到 docs/scene-cards/ (推荐)
- `.omo/_truth/scenarios/` 5 张卡迁移合并进 docs/scene-cards/ (冲突同名以 docs 版为准, scenarios 版标 superseded)
- scene-card-review.py 的 calibration/promote/weekly-review 改读 docs/scene-cards/, 与 lifecycle 的五档共用一套 tier 枚举
- skill 文档 (scene-shadow-activate) 同步改路径
- **成本**: 中 (1-2 天); **风险**: 低 — review 工具消费方少
- **收益**: 单一 SSOT, 消灭口径分裂; calibration 与 trial 证据链 (T7-02) 汇入同一条升级路径

### B. 保留双存储, 明确分工写进标准
- scenarios/ = 准入前工作区 (draft 提案/calibration), docs/scene-cards/ = 准入后舰队
- 迁移仪式: calibration 达标后由工具从 scenarios "毕业"到 docs
- **成本**: 低; **风险**: 中 — 分工约定无人强制就会再次漂移 (今天就是这么裂开的)

### C. 全部归到 .omo/_truth (registry 侧)
- 与「runtime facts → machine-readable SSOT」的 ARCHITECTURE §1 精神一致
- **成本**: 高 (63 卡迁移 + lifecycle/registry 两工具改造); docs 侧人类可读性受损

## 3. 决策点 (需拍板)

1. 选 A / B / C?
2. 若 A: 5 张 scenarios 卡里 `research-pipeline-legacy` 这类是否直接废弃 (有 v2 版本了)?
3. 迁移窗口: Y2Q1 内? 谁执行 (老王可代办, human_gate 留给你)?

## 4. 关联

- BET-Y2Q1-T7-02 (shadow 试验记录) — 已落地, PR #3215
- scene-shadow-activate skill — 路径指引与实况不符, 归一时同步修
- ADR-0387 (dual-track admission) — 本提案不触碰 admission_track 语义
