---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-28
last-reviewed: 2026-08-28
bet_id: BET-Y1Q3-T4-04
risk_level: L3
human_gate: true
type: ssot
last_updated: 2026-09-03
---

# Product P0 WP4 — Principal Authority Binding

## 1. 目标

把 `principal_id` 从只能通过正则的字符串，升级为在效果准入前已由权威来源验证的单用户身份。负例必须在 provider、router、tool、ledger effect 前 fail-closed，并且可直接证明零调用。

## 2. 权威边界

- OMO 是唯一 principal authority verifier 和 admission 权威。
- Cockpit 只接收 credential reference/authority fields 并委派 OMO，不构造已验证回执。
- Agora 只转发 OMO 已验证的 authority reference 和 digest，不成为身份登记表。
- 持久层只保存 authority reference、credential digest、membership version 和有效期，不保存 credential secret。

## 3. 合同

在 OMO 现有 `sovereignty` 包内增加一个窄 authority adapter：

```python
@dataclass(frozen=True)
class PrincipalAuthorityReceipt:
    principal_id: str
    authority_ref: str
    credential_digest: str
    membership_version: int
    verified_at: str
    expires_at: str


class PrincipalAuthority(Protocol):
    def verify(
        self,
        principal_id: str,
        credential_ref: str,
        *,
        now: str,
    ) -> PrincipalAuthorityReceipt: ...
```

`ActionRequest` 必须增加 `principal_authority_ref` 和 `principal_receipt_digest`。canonical request hash 必须覆盖这两个字段。admission receipt 必须保留完全相同的 digest，以便 Cockpit、OMO 和 Agora 全链重放。

## 4. 拒绝矩阵

以下任一情况都必须拒绝且证明 provider/router/tool/ledger effect 零调用：

- 缺少 authority receipt；
- `principal:alice` 或其他 fixture-only identity 试图进入 production path；
- receipt principal 与 request principal 不同；
- credential digest 不同；
- membership 已过期、版本倒退或 authority 未知；
- receipt 跨 request/principal replay；
- Cockpit 或 Agora 构造未经 OMO 验证的 digest。

## 5. 写面和子仓顺序

OMO child-first：

- `projects/omo/src/omo/sovereignty/principal_authority.py`
- `projects/omo/src/omo/sovereignty/enforcement.py`
- `projects/omo/src/omo/sovereignty/__init__.py`
- `projects/omo/tests/test_sovereignty_policy_enforcement.py`
- `projects/omo/tests/test_sovereignty_mandate_admission.py`

OMO 合同合并后才可更新 Cockpit：

- `projects/cockpit/src/cockpit/agent_runtime_server.py`
- `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py`
- `projects/cockpit/src/cockpit/tests/test_agent_runtime_server.py`
- `projects/cockpit/src/cockpit/tests/test_agent_runtime_mcp_server.py`

OMO/Cockpit 合同可达后才可更新 Agora：

- `projects/agora/src/agora/capability_gateway.py`
- `projects/agora/tests/unit/test_capability_gateway.py`

根仓只在 child main ancestry 可证明后更新对应 gitlink，并将 OMO、Cockpit、Agora pointer 收口与子仓实现 PR 分开。

## 6. 验收

1. RED 证明 format-only `principal:alice` 在无 authority receipt 时仍会被拒绝。
2. mismatch、expired、rollback、unknown authority 和 cross-principal replay 负例全部为零副作用。
3. 一条本地权威绑定 canary 通过 Cockpit -> OMO -> Agora，三端 digest 完全相等。
4. 重放相同 request 不生成第二份 principal/admission receipt。
5. credential secret 不出现在 event ledger、log、exception 或 generated projection。
6. 所有 child PR/CI/main ancestry 和 root gitlink reachability 都有独立回执。

## 7. 验证命令

```bash
cd projects/omo && uv run pytest tests/test_sovereignty_policy_enforcement.py tests/test_sovereignty_mandate_admission.py -q
cd projects/cockpit && uv run pytest src/cockpit/tests/test_agent_runtime_server.py src/cockpit/tests/test_agent_runtime_mcp_server.py -q
cd projects/agora && uv run pytest tests/unit/test_capability_gateway.py -q
python3 bin/ssot/submodule-reachability-gate.py --source head --fetch --require-main --json
```

## 8. 回滚与停机

如果权威服务不可用，所有 effectful action 降级为显式人工确认或拒绝，不降级为 format-only identity。回滚顺序为 Agora -> Cockpit -> OMO，已写入的 receipt 保留 append-only。任一负例不能证明零调用时立即停机。

## 9. 价值政策

`value_indicator_policy=false`。身份绑定是价值证据的必要条件，但本 WorkPacket 本身不证明价值。
