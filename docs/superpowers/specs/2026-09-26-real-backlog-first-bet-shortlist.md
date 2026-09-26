---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 业务首单候选盘点 — 真实 backlog 首个交付项的决策收件箱卡
bet_id: BET-Y2Q4-T4-01
---

# BET-Y2Q4-T4-01 — 业务首单候选盘点

## 背景

ADR-0419 决策"从基建转向业务"（2026-08），但协作双轨仪表显示产能轨（真实 backlog）
完成率 0%：基建完成度 99.6% 与业务产出 0% 形成临界落差。业务首单的选题是人类决策点
（本仓自诊断"人类决策是当前系统瓶颈"），本 bet 的职责是把该决策所需的输入一次备齐。

## 目标

盘点 `docs/plans/` vision-roadmap（4 YAML + 5 MD）与活跃 goals，提炼 **≥3 个**候选
业务交付项，每项带工作量/价值/风险评估与推荐排序，产出**一张**决策收件箱卡供人类拍板。

## 写面

`.omo/tasks/planned/**`（决策卡物理位置，BRIEF 生成器按此目录读卡）、
`docs/plans/**`（盘点分析文档）、`docs/plans/3y-bet-ledger.yaml`、本 spec、retro。

## 验收（done_when 摘要）

1. 候选清单（≥3 项）落在 `docs/plans/` 分析文档：每项含 goal 草案、effort（天）、
   value 判据、risk、推荐顺序与理由；
2. 一张决策卡 yaml 落在 `.omo/tasks/planned/`（needs-human: true，链接候选、写明选择判据）；
3. `generate-brief.py` 决策收件箱渲染该卡（或如实记录渲染条件不满足的原因）；
4. 首单原则进卡：≤3 天可完成、走完整 BET 流程验证通道、不先建新基建。

## 红线

- 候选不得是纯治理/基建项（那正是要纠正的偏差）；
- 卡不得承诺没有可度量 done_when 的产出；
- 不替代人类拍板 —— 卡是输入，选择权在收件箱。

## verify

- `python3 -c "import yaml; yaml.safe_load(open('.omo/tasks/planned/<卡名>.yaml'))"` → exit 0
- `python3 bin/mof/generate-brief.py` → 决策收件箱含该卡（或记录渲染条件）
- `python3 bin/plan/bet-ledger.py lint` → 不引入新错误
- `make gac-local-gate` → exit 0
