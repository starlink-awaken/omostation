---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# X2 Standard: Atomic Budget Ledger & Quota Integrity

> Status: MANDATORY | Applied: Phase 4
> Authority: llm_gateway.quota_ledger

## 1. 核心流程
系统必须确保“预检 -> 执行 -> 扣减”的原子性，维持财务 SSOT。

## 2. 预算拦截 (Pre-flight)
- 任何 LLM 调用前，必须调用 `check_budget_limit`。
- 如果 Projected Cost > Global Remaining 或 Task Local Budget，必须立即抛出 `BudgetExhausted` 异常。

## 3. 实时扣减 (Post-call)
- 调用成功后，必须通过 `append_quota_ledger_event` 将真实 Token 消耗记录至 `llm_quota_ledger.jsonl`。
- **并发控制 (Phase 15)**: 所有的 JSONL 写入必须通过 `fcntl.flock` 获取排他锁，确保多进程并发时数据的完整性。
- 严禁出现只调用不计费的“裸奔”请求。

## 4. 审计追踪
- 分类账必须包含：时间戳、模型 ID、输入/输出 Token 数、折算 USD。
- `get_remaining_budget()` 必须实时聚合分类账历史记录。
