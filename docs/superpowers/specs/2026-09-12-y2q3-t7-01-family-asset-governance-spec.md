---
schema_version: specification/v1
spec_version: 1.0.0
title: 家庭资产负债平水审计、大额支出预警与法务合同审查场景包
bet_id: BET-Y2Q3-T7-01
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-12
last-reviewed: 2026-09-12
risk_level: L1
human_gate: true
type: ssot
last_updated: 2026-09-12
decision_ref: decision://accepted/BET-Y2Q3-T7-01
---

# 家庭资产负债平水审计、大额支出预警与法务合同审查场景包（BET-Y2Q3-T7-01）

## 背景（Context）

家庭财务管理涉及银行流水、固定资产维保、法务合同等多源数据，
当前缺乏自动化整合与风险预警能力。本 spec 在 Family Hub 平面上构建
资产负债平水审计、大额支出预警与法务合同审查三大能力，覆盖家庭财务治理核心场景。

## 目标（Goal）

1. 自动化解析家庭银行流水账单（CSV/OFX/PDF），生成月度净资产走势与现金流预测。
2. 大额异常支出检测与预警（超出历史均值 2σ 或设定阈值时标黄告警）。
3. 法务合同审查：检出模糊条款、违约风险与不公平条款。
4. 场景卡晋级至 assisted 状态（30-sample + calibration ≥ 0.6）。

## 非目标（Non-Goals）

- 不直接连接网银进行自动转账操作。
- 不替代专业法律意见，仅提供风险提示。
- 不做投资组合优化建议。

## 完成标准（Done When）

1. `docs/scene-cards/family-asset-governance.yaml` 场景卡晋级 assisted（30-sample 通过）。
2. 月度自动产出资产负债平水报表（净资产、现金流、负债比）。
3. 合同审查模块准确检出模糊条款与违约风险（precision ≥ 0.7）。
4. 大额支出预警触发准确率 ≥ 80%（基于历史数据回测）。

## 验证（Verify）

- `uv run python -m domain.family.test_asset_audit` → exit 0。
- `make gac-local-gate` → exit 0。
- `uv run --with pyyaml python bin/plan/bet-ledger.py lint` → exit 0（结构合法）。

## 决策引用（Decision Ref）

- `decision://accepted/BET-Y2Q3-T7-01`（2026-09-12 UTC 用户授权 spec 绑定，可审计）

## 交付面（Write Surfaces）

- `docs/scene-cards/family-asset-governance.yaml` — 场景卡定义
- `projects/family-hub/src/` — 审计/预警/合同审查模块实现
- `.omo/_knowledge/retros/BET-Y2Q3-T7-01.md` — 复盘
