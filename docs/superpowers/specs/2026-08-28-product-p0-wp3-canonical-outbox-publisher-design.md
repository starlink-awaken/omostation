---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-28
bet_id: BET-Y1Q3-T4-06
risk_level: L2
human_gate: false
type: ssot
last_updated: 2026-09-03
---

# Product P0 WP3 — Canonical Outbox Publisher

## 1. 目标

让 OMO 已有 `event_outbox` 从“可存储、可手工 mark”成为真正的单一生产发布路径：原子 lease、幂等发布、确定重试/backoff、不确定传输保守处理、持久回执和 dead-letter/failure 证据。

本 WorkPacket 依赖 WP2。Publisher 只消费 canonical Event Ledger 在同一事务中写入的 outbox rows，不创建第二 queue、bus 或 broker。

## 2. 当前反例

`LedgerBroker.outbox_pending()` 可查询 pending rows，`outbox_mark()` 可手工更新 state/attempts，但没有 production consumer 做并发排他、lease 回收、backoff、不确定传输处理或 receipt 持久化。存储存在不等于交付链成立。

## 3. 单一发布合同

```python
PublishFn = Callable[[str, dict[str, Any], str], str]


@dataclass(frozen=True)
class PublishResult:
    event_id: str
    destination: str
    state: str
    attempts: int
    receipt_id: str | None
    next_attempt_at: str
    error_class: str | None


def publish_due(
    broker: LedgerBroker,
    destination: str,
    publish: PublishFn,
    *,
    worker_id: str,
    now: str,
    limit: int = 100,
) -> list[PublishResult]: ...
```

Publisher 以 `(event_id, destination)` 作为幂等身份。只有成功获取 lease 的 worker 可调用 `PublishFn`。稳定 receipt 已存在时直接复用，不重发。

## 4. 数据与状态语义

优先在已有 `event_outbox` 表上增加最小 lease/receipt 字段：

- `lease_owner`
- `lease_expires_at`
- `receipt_id`
- `error_class`

若当前 schema 已能无歧义表达这些语义，则不迁移。不得新建另一张 queue 表。

状态规则：

- 明确成功 + receipt：`sent`。
- timeout/connection reset/运输结果不确定：保持 pending/uncertain，不写 `sent`。
- 明确可重试失败：按 `[5, 30, 120, 600]` 秒序列计算 `next_attempt_at`。
- 第五次明确确定性失败：`failed/dead-letter`，必须有 failure receipt。
- worker 崩溃后 lease 过期可回收，但无 receipt 时不能假定上一次未发送。

## 5. 写面

- `projects/omo/src/omo/event_ledger/schema.py`（仅当需要正式迁移）
- `projects/omo/src/omo/event_ledger/broker.py`
- `projects/omo/src/omo/event_ledger/publisher.py`
- `projects/omo/tests/test_event_ledger.py`
- `projects/omo/tests/test_event_outbox_publisher.py`

不得修改 Agora bus 为另一个 outbox owner，不得从 projector 直接调用 `outbox_mark()`。

## 6. 验收

1. 两个 publisher 并发竞争一行，`PublishFn` 恰好调用一次。
2. 已 sent row 重放返回已有 receipt，不重发。
3. timeout/connection reset 保持 uncertain/pending，不误标 success。
4. backoff 在确定 clock 下严格等于 `[5, 30, 120, 600]`。
5. 崩溃重启后不丢行，不无证据重复交付。
6. 第五次确定性失败有 dead-letter/failure receipt。
7. 一次 shadow-mode production canary 有直接运行回执，不推进个人价值。

```bash
cd projects/omo
uv run pytest tests/test_event_ledger.py tests/test_event_outbox_publisher.py -q
```

## 7. 回滚与停机

回滚时停止 publisher，保留所有 pending/uncertain/failed rows 和 receipt，不删除数据。任一并发测试出现重复调用、不确定传输被标记成功、或 lease owner 不能校验时立即停机。

## 8. 价值政策

`value_indicator_policy=false`。发布回执是运行证据，不是 principal-bound value。
