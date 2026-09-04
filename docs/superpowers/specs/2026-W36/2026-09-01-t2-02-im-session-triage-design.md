---
schema_version: specification/v1
spec_version: 1.0.0
title: IM session perception & one-shot directive triage
bet_id: BET-Y1Q4-T2-02
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-01
last_updated: 2026-09-01
type: ssot
last_updated: 2026-09-03
---

# IM session perception & one-shot directive triage (T2-02)

## Intent

接入企微/飞书/微信会话信号，白名单过滤后提炼结构化待办卡片；支持一句话指令
（查阅/拟稿/审批/催办）触发织星后台动作并返回待发卡片。

## Privacy & safety red lines (non_goals)

- 白名单双闸：仅白名单群组 + 白名单关键词命中的消息才进入提炼，其余丢弃
- 不自动回复、不静默外发——所有外发卡片都停在"待发"状态等夏明星确认
- 真实 IM 账号接入（webhook/桌面钩子）走 human_gate，本站先交付协议面

## Architecture (KISS, two-day appetite)

```
projects/agora/src/agora/server/tools_bos/im.py（BOS IM 域模块）
├─ ImMessage(id, platform, chat_id, sender, text, ts, is_group)
├─ WHITELIST: chats + keyword patterns（隐私红线单源）
├─ _parse_directive(text) → Directive(action, payload)
│   规则路由: 查阅(查/看看/搜) | 拟稿(拟/写/起草/生成) |
│            审批(批/同意/通过) | 催办(催/提醒/催办)
├─ _to_task_card(msg, directive) → 结构化待办卡片
│   (priority: @提及/催办 > 关键词强信号; deadline: 时间词推断)
├─ bos_im_session_triage(messages) — bos://im/session/triage 统一网关
├─ circuit_breaker: 解析异常 → passive 模式(标记 pending_review, 不动作)
└─ main(argv): test_session_ingress（verify 契约，exit 0）

projects/cockpit/src/cockpit/commands/im_triage.py
└─ cockpit im-triage: 渲染今日 IM 待办卡片（读 .omo/state/im-triage/*.json）
```

## Performance & accuracy contracts (done_when)

- 端到端 ≤2s：纯本地规则引擎毫秒级，test 断言实测耗时
- 意图解析 ≥95%：合成评测集（正例 20 + 对抗例 5），断言准确率
- bos://im/session/triage：BOS 工具函数 + 协议 schema v1

## Verify (BET contract)

- `uv run python -m agora.server.tools_bos.im test_session_ingress` → exit 0
- `make gac-local-gate` → exit 0
