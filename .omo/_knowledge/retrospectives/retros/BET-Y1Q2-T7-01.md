---
lifecycle: history
owner: auto-fix-loop
last_updated: 2026-08-24
title: BET-Y1Q2-T7-01 Retro — 工程交付 dogfood 开 shadow
type: retro
---

# BET-Y1Q2-T7-01 Retro — 工程交付 dogfood 开 shadow

- 状态: done (2026-08-22)
- 历史: blocked(2026-08-22, 0/20)→ Phase A 采集管线 → Phase B 20 条达成 → done

## 结果

1. **采集管线闭环**(Phase A, omo #76/#77 + 主仓 #1888):
   - consume-engineering-delivery(机器记录供给侧)
   - engineering-delivery-review-queue(候选队列)
   - submit-engineering-delivery-review(人类裁决, HMAC 凭证)
   - engineering-delivery-shadow-observer(7 日窗口计数)
2. **首轮 20 条达成**(Phase B, 主仓 #1893):
   - 20 个真实合并 PR 全部 adopted(operator://xiamingxing, HMAC 签名)
   - observer: verdict=PASS, qualifying=20, status=ready_for_human_review
3. **human_gate 确认**(#closeout):
   - 用户对 observer PASS 做 SSH 签名 attestation(confirm)
4. **done_when 全部达成**:
   - lifecycle=shadow ✓
   - 7 日窗口 >=20 条 qualified decision outcome ✓
   - 永不计入价值指标 ✓

## 关键发现

- **HMAC 凭证绑定**: human verdict 用 server-owned key 签名, 客户端无法伪造
- **observer 需文件 key fallback**: env key 不够(重启后丢失), 需 .omo 文件持久
- **root 参数线程化**: _validate_qualified_record/_validate_primary_records 需传 root
- **spec binding**: done BET 需 accepted_specifications(bet_id 匹配), T7-01 创建专用 spec

## 遗留

- 后续周窗口需持续裁决(保持 20 条/周)
- shadow 场景永不计价值(价值轴保持 REJECTED)
