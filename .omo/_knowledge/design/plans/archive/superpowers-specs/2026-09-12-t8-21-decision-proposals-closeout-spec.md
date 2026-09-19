---
schema_version: specification/v1
spec_version: 1.0.0
title: 常驻决策提案 (Decision Proposals) 闭环消费与 Cockpit 审批自进化通道
bet_id: BET-Y1Q4-T8-21
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-12
---


# 常驻决策提案闭环消费与 Cockpit 审批自进化通道（BET-Y1Q4-T8-21）

## 背景（Context）

`.omo/_knowledge/decision-proposals/` 已积累 149 份决策提案与 138 条建议，
但目前缺乏结构化消费通道：提案未被系统性审阅、分类、晋升或归档，
造成治理资产积压。本 spec 建立从提案到 Cockpit 呈递面再到 BET/ADR 结晶的闭环。

## 目标（Goal）

1. 提供 `cockpit resident decision triage` CLI 命令，支持按状态（reviewed/promoted/dismissed）
   和事件类型聚合过滤决策提案。
2. 在 Cockpit Web 仪表盘增加决策提案待办卡片，展示高优先级未处理提案。
3. 实现一键批准（approve）能力：将高价值建议结晶为 3Y-BET-LEDGER 新 Bet 或架构 ADR 的标准 YAML 模板。
4. 存量 149 份提案完成状态标记归档（reviewed / promoted / dismissed）。

## 非目标（Non-Goals）

- 不做未经人类确认的全自动生产代码合入。
- 不删除历史提案原始内容（保持不可篡改追溯）。
- 不替代 Cockpit 现有审批工作流，仅扩展决策提案专属通道。

## 完成标准（Done When）

1. `cockpit resident decision triage` CLI 支持 `--status` / `--type` 过滤并输出结构化列表。
2. Cockpit Web `/api/resident/decisions` 端点返回待办提案卡片数据。
3. `cockpit resident decision approve <proposal-id>` 一键生成 BET-YAML 或 ADR-YAML 模板。
4. 存量提案状态标记完成（149 份均有 reviewed/promoted/dismissed 之一）。
5. 单元测试覆盖 triage 过滤逻辑与 approve 模板生成。

## 验证（Verify）

- `uv run pytest projects/cockpit/tests/test_resident_decision_triage.py -q` → exit 0。
- `make gac-local-gate` → exit 0。
- `uv run --with pyyaml python bin/plan/bet-ledger.py lint` → exit 0（结构合法）。

## 决策引用（Decision Ref）

- `decision://accepted/BET-Y1Q4-T8-21`（2026-09-12 UTC 用户授权 spec 绑定，可审计）

## 交付面（Write Surfaces）

- `projects/cockpit/src/cockpit/cli/resident_cli.py` — triage & approve CLI
- `projects/cockpit/src/cockpit/web/api_reflection.py` — 扩展决策端点
- `projects/omo/src/omo/resident/decision.py` — 状态标记与归档逻辑
- `projects/cockpit/tests/test_resident_decision_triage.py` — 单元测试
- `.omo/_knowledge/retros/BET-Y1Q4-T8-21.md` — 复盘
