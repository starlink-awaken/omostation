---
schema_version: specification/v1
spec_version: 1.0.0
title: ledger 并发回写根治 — save_ledger_locked 加锁原子通道
bet_id: BET-Y1Q4-T10-136
status: accepted
lifecycle: contract
last-reviewed: 2026-09-07
type: plan
owner: governance-team
last_updated: 2026-09-07
---

# ledger 加锁回写规格 (BET-Y1Q4-T10-136)

## 内容

- save_ledger_locked(transform): flock 进程互斥 + tmp+rename 原子落盘
- complete 的 status 回写迁移至锁内读-改-写 (幂等, 并发已写时静默跳过)

## 验收

- 变换单测通过 (正确+幂等)
- 原子写冒烟通过
