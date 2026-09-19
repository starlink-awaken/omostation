---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-28
bet_id: BET-Y1Q3-T4-07
risk_level: L3
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Product P0 WP5 — Human Adjudication to Principal-Bound Value

## 1. 目标

建立唯一可以推进 Product P0 价值轴的链路：一个真实非测试决策进入 Cockpit Decision Inbox，已绑定权威身份的人类做 adopt/edit/ignore 裁决，OMO 持久化 adjudication 和 `decision_outcome`，价值投影在进程重启后仍可重复读取。

本 WorkPacket 依赖 WP1、WP4 和 WP3，分别提供诚实场景门、principal authority 和 durable event/outbox path。

## 2. 价值真值边界

只有同时满足下列条件的记录可计为 qualifying outcome：

- `source_class == "real_human"`；
- principal 已由 WP4 authority receipt 绑定；
- adjudication 绑定已持久 decision、scene 和 episode；
- revision/digest 与裁决时展示的候选一致；
- adjudication idempotency identity 未被另一 principal 或 decision 重放；
- outcome 由 OMO 唯一 truth writer 写入 canonical Event Ledger。

PR、merge、CI、test、transport receipt、signed engineering evidence、agent self-report、synthetic、fixture、`user_provided` 或未绑定 decision/scene/episode 的人类文本都必须分区且不计 gate。

## 3. 合同

```python
@dataclass(frozen=True)
class HumanAdjudication:
    adjudication_id: str
    decision_id: str
    principal_id: str
    verdict: str
    source_class: str
    authority_receipt_digest: str
    adjudicated_at: str


def record_decision_outcome(
    adjudication: HumanAdjudication,
    *,
    scene_id: str,
    episode_id: str,
    burden_minutes: float | None,
) -> dict[str, Any]: ...
```

OMO 必须在一个事务边界内验证 lineage、写入 adjudication/outcome 事件并推进已有 value projection。Cockpit 除明确的 human adjudication command 外保持只读，且该 command 只委派 OMO，不直接写 YAML/JSON projection。

## 4. 写面与顺序

OMO child-first：

- `projects/omo/src/omo/personal_episode.py`
- `projects/omo/src/omo/engineering_delivery_consumer.py`
- `projects/omo/tests/test_personal_episode.py`
- `projects/omo/tests/test_engineering_delivery_consumer.py`

OMO 真值 writer 合并后才可更新 Cockpit projection/command：

- `projects/cockpit/src/cockpit/web/api_decision_inbox.py`
- `projects/cockpit/src/cockpit/web/api_outcomes.py`
- `projects/cockpit/src/cockpit/tests/test_api_decision_inbox.py`
- `projects/cockpit/src/cockpit/tests/test_api_outcomes.py`

不得直接修改 `.omo/_truth/registry/memory-os.yaml` 或任何 value YAML 来伪造正向样本。

## 5. 拒绝矩阵

以下记录均不产生 qualifying outcome，计数和价值状态不变：

- 缺 principal authority receipt；
- decision、scene 或 episode 不存在；
- scene 不同或 revision digest 已变；
- duplicate adjudication；
- cross-principal replay；
- `source_class` 非 `real_human`；
- 只有 PR/test/attestation/transport/agent 自报；
- 只有未关联决策的人类评语。

## 6. 真实 canary 与验收

1. Cockpit 展示一个真实非测试 decision，包含 scene、episode、revision digest 和负担量输入。
2. authority-bound human principal 选择 adopt、edit 或 ignore。
3. OMO 写入恰好一个 adjudication 和一个 `decision_outcome`。
4. 相同请求重放不增加计数，进程重启后读取结果一致。
5. 新鲜 observer 可重复读到 qualifying count `>= 1`，并能回溯 principal/decision/scene/episode/adjudication lineage。
6. 一条 outcome 证明链路成立；是否进入长期 `ACCEPTED` 由人类对 real signal、verdict、revision 和 time burden 的证据审议决定。

```bash
cd projects/omo && uv run pytest tests/test_personal_episode.py tests/test_engineering_delivery_consumer.py -q
cd projects/cockpit && uv run pytest src/cockpit/tests/test_api_decision_inbox.py src/cockpit/tests/test_api_outcomes.py -q
```

## 7. 完成证据

WP5 的 value `ACCEPTED` 必须直接绑定：

- `real_signal`
- `human_verdict`
- `revision`
- `time_burden`
- authority receipt digest
- durable `decision_outcome` event/receipt

缺任一项都保持 `NOT_PROVEN`。

## 8. 回滚与停机

回滚时冻结新 adjudication，保留已有 append-only history，并从 Event Ledger 重建 projection。不删除或改写已发生的人类裁决。任一 lineage 不可证明、任一负例误计价值、或 Cockpit 绕过 OMO truth writer 时立即停机。

## 9. 价值政策

`value_indicator_policy=true`，但只对上述全部直接证据成立的真实 human adjudication 生效。默认状态仍是 `NOT_PROVEN`。
