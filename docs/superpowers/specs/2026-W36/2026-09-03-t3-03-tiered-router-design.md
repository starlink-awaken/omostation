---
schema_version: specification/v1
spec_version: 1.0.0
title: Tiered speculative router (light/mid/heavy)
bet_id: BET-Y1Q4-T3-03
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-03
last_updated: 2026-09-03
type: ssot
last_updated: 2026-09-03
---

# Tiered speculative router (T3-03)

三层分级 (extends ADR-0197): light 1.5B/3B (意图+槽位 <5ms) / mid 8B/14B
(校验+初筛) / heavy 27B/70B (深度拟稿)。路由纯规则 <1ms; 投机级联 light 草稿
低置信升阶。verify: speculative_router_eval (80/20 评测集, 秒结率/升阶/延迟断言)。
