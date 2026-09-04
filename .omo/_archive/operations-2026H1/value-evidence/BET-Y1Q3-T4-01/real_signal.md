---
schema: value-evidence/real-signal/v1
bet: BET-Y1Q3-T4-01
signal_event_id: evt_6a91f63077fe64fb9344b10e
signal_id: signal_6a91f63077fe64fb9344b10e
episode_id: episode_088af4df0c0ed55f204e2bae
observed_at: 2026-08-21T12:48:23Z
content_sha256: sha256:c2c072f23357e3a1c638c93ad8e05ac14a3dd46b7a40980eaf71ac46ec0f453e
title: 跨仓耦合机制半删的观察
lifecycle: history
owner: governance-team
last_updated: 2026-08-26
---

last-reviewed: 2026-08-26
---
真实低敏信号: 跨仓耦合机制(WorkPacket instruction binding)清理时只删生成侧、
不盘点消费侧, 导致 BET start 全链失败(#1815→#1825)。教训: 跨仓耦合机制删除前
必须先盘点全部消费侧。正文不入库, 仅存 content_sha256 摘要(AC-08 合规)。
