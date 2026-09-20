---
schema: bet-retro/v1
bet_id: B1-3-health-predict
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-20
type: ephemeral
completed_at: 2026-09-20
---

# Retro: B1.3 — health-predict 7-day ledger drift forecast

## Summary

新增 `bin/ssot/health-predict.py` — 基于 `.omo/state/health.yaml` 当前快照
+ `auto-fix-loop` retro drift 计数, 启发式预测 7 天后 4 个核心健康维度
(drift / staleness / freshness / alignment), 输出 RED/YELLOW/GREEN 风险等级 +
建议动作. 实测 48+82 retro drift → drift 7d 后 +15.2 (GREEN→YELLOW).

## What went well

- **复用现有数据**: 不依赖历史快照, 只读 health.yaml 当前 + auto-fix-loop JSON
- **启发式规则可解释**: drift_score = current + retro_count × 0.5 × (horizon/30)
- **协同 B1.1**: 强制 SKIP_FIX_LOOP_BRANCH=1 让 retro 漂移计数生效, 不需要双跑脚本
- **8 单元测试覆盖**: 预测公式 + 风险分带 + 跨维度对齐 + 推荐动作
- **JSON 输出稳定**: drift / staleness / freshness / alignment 四维同结构,
  CI 解析简单

## What was learned

- **banker's rounding**: 100 - 0.05*7 = 99.65 → round(_, 1) = 99.7 (Python)
  → 测试断言改区间 [99.6, 99.7]
- **closeout-skip 必须强制**: auto-fix-loop 默认只在 closeout 分支输出
  RETRO-SKIPPED drift. health-predict 需要全量 retro 数, 必须
  SKIP_FIX_LOOP_BRANCH=1
- **drift_score 是反指标**: 低 = 好, 高 = 差. 其他维度高 = 好. band() 需
  按 kind 参数分支
- **嵌套函数不可测**: predict_horizon 内部 band() 函数, 测试只能通过
  外层 API 间接验证

## What to improve

- **历史快照缺失**: 当前 workspace 只有 1 个 health.yaml 快照, 无法做
  时间序列回归. 后续可加 `--record-snapshot` 模式, 把每次结果写入
  `.omo/state/health-history.jsonl` 形成趋势
- **linear 模型粗**: 当前是简单线性, 真实 drift 有阶段性爆发. 待 P107+
  数据积累后再考虑 seasonal / anomaly-aware
- **未对接 omo governance audit**: gov_anomaly_score 没纳入预测
- **CI 集成缺失**: 不像 auto-fix-loop 在 gate 里跑. 可在 cron weekly 加

## Metrics

- Files added: 2 (bin/ssot/health-predict.py 200L, tests/bin/test_health_predict.py 110L)
- Files modified: 1 (script-registry 自动建 yaml)
- Tests: 8/8 pass in 0.30s
- Drift prediction bands: 4 (drift/staleness/freshness/alignment)
- Real prediction: drift 0.0 → 15.2 (YELLOW), alignment 62.0 → 60.5 (YELLOW)
- PR: TBD
- Total LOC delta: +310

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| `bin/ssot/health-predict.py` 实现 | ✅ |
| 读 health.yaml 5 维分数 | ✅ |
| 复用 auto-fix-loop retro drift 计数 | ✅ |
| 启发式预测 (drift + staleness + freshness + alignment) | ✅ |
| RED/YELLOW/GREEN 风险分带 | ✅ |
| 推荐动作生成 | ✅ |
| JSON 输出 4 维同结构 | ✅ |
| 8 单元测试 (含 rounding tolerance) | ✅ |
| script-registry 登记 | ✅ |
| ruff check 0 errors | ✅ |
| 实测: drift 7d 后 +15.2 (B1.1 retro 48+82 累积) | ✅ |