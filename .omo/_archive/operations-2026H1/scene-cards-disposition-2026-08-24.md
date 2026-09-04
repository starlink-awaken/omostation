---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: 场景卡三分处置表 — 2026-08-24
type: doc
---

# 场景卡三分处置表 — 2026-08-24

> 依据: bin/ssot/scene-card-lifecycle.py readiness(generic gate) + scene-activation-sweeper.py 分类(50-87) + agora runtime 组件溯源
> 原则(Q6): 不为分数激活未就绪的卡; 宁归档不虚活

## 处置总表

| 卡 | 状态 | 生效 blocker | 处置 | 依据/缺失组件 |
|----|------|-------------|------|--------------|
| research-pipeline | pending_business_confirmation | 业务确认 | **问主人** | sweeper L81-82 |
| project-supervision | pending_business_confirmation | 业务确认 | **问主人** | 同上 |
| periodic-reporting | pending_business_confirmation | 业务确认 | **问主人** | 同上 |
| meeting-supervision | pending_business_confirmation | 业务确认 | **问主人** | 同上 |
| engineering-delivery | OMO_admission_evidence | trial 未持久化 | **修**: 建 `bin/ssot/internal-scene-trial.py` Phase 2 --record | 卡内注记 L78; lifecycle Check4 L202-206 |
| document-review | calibration=null (lifecycle_gate 非 activation_blockers!) | 校准未测 | **修**: 跑 document-review 流产出校准值(样本30已集) | lifecycle_gate L17-24; lifecycle 脚本不读此字段⚠️ |
| agora-bos-gateway | admission_provider_unavailable_in_production | 生产未绑定 admission provider | **问主人**(生产部署决策) | port.py:144,176-189 |
| agora-bos-gateway | backends_connection_ratio_low | stdio 后端被健康检查跳过致比率假低 | **修** | tools_health.py:109-114,246-256 |
| agora-bos-gateway | audit_chain_broken | hashchain 断链 | **修** | tools_health.py:165-171; 修复路径 :428-435 |
| agora-bos-gateway | unauthorized_register_endpoint | AGORA_AUTH_MODE=permissive 放行 /v1/backends/register | **修**: 设 required+API_KEY | mcp_entry.py:90-147; tools_auth.py:34-49 |
| unified-inbox | 无 blocker(已assisted) | — | 观察: proposal_only vs assisted 不一致待核 | 卡 L47 |
| knowledge-curation | 无 blocker(已assisted) | journey spec 缺文件(非blocker) | 观察 | 卡 L18 |

## 汇总
- 问主人 ×5（四卡业务确认 + 生产 admission 决策）
- 修 ×5（internal-scene-trial 建设 / 校准运行 / agora 三项基础设施）
- 归档 ×0 · 无 blocker ×2

## UHS 影响
当前 scenes=71.4。修×5 完成后 4 卡可转 assisted/active → 预计 87 达标;
问×5 待拍板即时生效。
