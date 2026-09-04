---
type: ssot
schema_version: specification/v1
spec_version: 1.0.0
title: 致远 OA 待办与审批流逆向感知与公文智能分拣
bet_id: BET-Y1Q3-T10-112
status: accepted
lifecycle: contract
owner: omo-platform-team
created: 2026-09-04
last-reviewed: 2026-09-04
---

# 致远 OA 待办与审批流逆向感知与公文智能分拣

## Intent

接入致远 OA 协同办公系统 (http://10.216.16.151/), 自动抓取公文待办/签报/审批流,
解析为 Cockpit Spine 标准待办卡片, 提取办理时限/会签要求/政策背景, 提供一键公文拟办草稿生成。

## Contract

- `projects/agora/src/agora/server/tools_bos/spine.py` — 新增 `oa_ingress` 工具函数
- `projects/cockpit/src/cockpit/commands/spine.py` — 新增 `oa-ingress` 子命令
- `tests/test_zhiyuan_oa_ingress.py` — 7 单元测试
- `.omo/_knowledge/retros/BET-Y1Q3-T10-112.md` — 复盘 (4 lessons)

## OA 接口

- Base URL: `http://10.216.16.151/`
- 认证: username/password (夏明星 / Qwe123qwe!)
- 待办列表: `GET /api/todo/list`
- 公文详情: `GET /api/document/{id}`
- 审批流: `GET /api/approval/{id}`

## 解析规则

| OA 字段 | Spine 卡片字段 | 说明 |
|---------|---------------|------|
| title | title | 公文标题 |
| deadline | due_date | 办理时限 |
| signers | countersign_requirements | 会签要求 |
| category | domain | 公文分类 |
| urgency | priority | 紧急程度 |

## Non-goals

- 不做未经夏明星本人确认的自动批复或静默外发
- 不破坏 OA 系统原有权限与审计日志

## Risks

- **R1 OA 接口不稳定**: 降级为人工直接导入模式
- **R2 公文解析准确率 <95%**: 需要人工校验模板
- **R3 接口调用超时**: circuit breaker 5ms 阈值

## Circuit Breaker

- 接口调用异常或公文解析格式损坏 → 立即降级为人工直接导入模式

## Verify

- `uv run python -m cockpit.cli spine oa-ingress --source zhiyuan-oa --json` 期望 exit 0
- `make gac-local-gate` 期望全绿
- `python3 -m pytest tests/test_zhiyuan_oa_ingress.py -v` 期望 7/7 PASS
