---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-25
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: 组织架构与政企人脉关系图谱（深度关联来件单位、历史沟通偏好与决策背景）
bet_id: BET-Y2Q1-T7-01
created: 2026-09-16
risk_level: L1
human_gate: false
last_updated: 2026-09-16
decision_ref: decision://accepted/BET-Y2Q1-T7-01
---


# 组织架构与政企人脉关系图谱（BET-Y2Q1-T7-01）

## 背景（Context）

在政企协作与政策研究场景中，需要深度理解来件单位的组织架构、关键决策人、
历史沟通偏好与决策背景。当前缺乏结构化的人脉关系图谱能力，
导致检索到政策/批复后无法快速关联到具体负责人与历史交互上下文。

本 spec 在 Kairon 知识图谱平面上扩展组织人脉子图（OrgGraph），
并在 Cockpit CLI 提供 `org-relation` 查询入口，实现：
- 单位→关键人物→历史来件→偏好标签的多跳关联
- 基于沟通频次与时间衰减的关系权重
- 结构化输出供 Agent 在检索增强时注入决策背景

## 目标（Goal）

1. 在 `kairon.graph.org_graph` 中实现 OrgGraph 类，支持单位/人物/来件三类节点与任职/来件/沟通三类关系。
2. 支持 JSONL 持久化与增量更新，兼容现有 KEMS-v2 的 KnowledgeGraph 接口模式。
3. 提供 CLI 入口 `org-graph --query <关键词>` 返回匹配的组织人脉子图（JSON）。
4. 在 Cockpit 提供 `cockpit org-relation <单位名>` 命令，调用 Kairon OrgGraph 并渲染为 Rich 表格。
5. 关系权重基于时间衰减（半衰期 365 天）与沟通频次加权。

## 非目标（Non-Goals）

- 不自动爬取外部公开数据，仅基于用户手动录入或历史来件数据构建。
- 不做实时通讯录同步（如企查查/天眼查 API 对接）。
- 不存储个人隐私敏感信息（身份证、手机号等 PII）。
- 不替代 CRM 系统，仅作为检索增强的背景知识层。

## 完成标准（Done When）

1. `projects/knowledge/kairon/src/kairon/graph/org_graph.py` 实现 OrgGraph 类，含 add_entity / add_relation / query / to_jsonl / from_jsonl 方法。
2. `projects/knowledge/kairon/src/kairon/cli.py` 新增 `org-graph` 子命令，支持 `--query` 与 `--json` 参数。
3. `projects/cockpit/src/cockpit/commands/org_relation.py` 实现 `org-relation` 命令，渲染 Rich 表格输出。
4. `uv run python -m projects.knowledge.kairon.cli org-graph --query 测试单位` → exit 0。
5. `make gac-local-gate` → exit 0。

## 验证（Verify）

- `uv run python -m projects.knowledge.kairon.cli org-graph --query 测试单位` → exit 0。
- `make gac-local-gate` → exit 0。
- `uv run --with pyyaml python bin/plan/bet-ledger.py lint` → exit 0（结构合法）。

## 决策引用（Decision Ref）

- `decision://accepted/BET-Y2Q1-T7-01`（2026-09-16 UTC 用户授权 GO，可审计）

## 交付面（Write Surfaces）

- `projects/knowledge/kairon/src/kairon/graph/org_graph.py` — OrgGraph 核心实现
- `projects/knowledge/kairon/src/kairon/cli.py` — CLI 入口扩展
- `projects/cockpit/src/cockpit/commands/org_relation.py` — Cockpit 命令
- `.omo/_knowledge/retros/BET-Y2Q1-T7-01.md` — 复盘

## 依赖

- BET-Y1Q3-T10-117（KEMS-v2 混合检索）— 已完成，提供 KnowledgeGraph 基础接口参考。
