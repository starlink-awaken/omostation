---
schema_version: report/v1
lifecycle: history
type: delivery-report
owner: governance-team
created: 2026-09-01
last_updated: 2026-09-01
bet: BET-Y1Q4-T2-02
---

# IM 会话感知与指令式即时办结（协议面交付报告）

## 交付概览

| 项 | 结果 |
|----|------|
| 网关 | `bos://im/session/triage`（agora.bos.im.v1）✅ |
| 白名单引擎 | 双闸：白名单群 + (@提及 \| 关键词 \| 指令命中) |
| 意图解析 | 规则路由 query/draft/approve/urge，**accuracy 0.96**（20 正例 + 5 对抗）✅ |
| 端到端时延 | **0.65ms** / 100 条批处理（预算 2s，快 3000 倍）✅ |
| 隐私红线 | 非白名单群全丢弃（50/50 实测）；卡片全 `pending_approval` 无自动外发 ✅ |
| 命令面 | `cockpit im-triage` 待办卡片渲染 ✅ |
| verify 契约 | `test_session_ingress` 5 检查全绿 exit 0 + gac-local-gate 56 全绿 ✅ |

## 边界与 human gate（诚实记录）

- 本站交付**协议面**：网关 + 白名单 + 解析 + 卡片 + 渲染。
- **真实 IM 账号接入（企微/飞书 webhook、微信桌面钩子）走 human_gate 待夏明星确认**：
  需要真实账号授权与企业应用凭证，且涉及隐私边界最终确认。
- circuit_breaker：解析异常 → passive（pending_review）不中断批次。

## 关键工程决策

1. **gate 语义修正**：白名单命中条件扩展为 (@ \| 关键词 \| 指令)——"催一下回函"
   无"催办"关键词但指令可解析，仍应入闸（首测暴露，即修）。
2. **零噪音语义**：白名单群内无信号消息同样丢弃（dropped），passive 仅留给
   解析异常——卡片面保持纯信号。
3. 规则路由顺序 approve > urge > draft > query（无歧义词优先匹配）。

## 验证记录

- tests/test_im_triage.py 7/7
- verify: accuracy 0.96 ≥ 0.95；e2e 0.65ms ≤ 2s；noise 50/50 dropped；
  cards 100% pending_approval；gateway URI 契约
