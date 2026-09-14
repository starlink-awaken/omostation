---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-05
---
# BET-Y1Q3-T1-12 value attestation 签名步骤

Agent 不能代签。按下列命令由 principal 本地签名后，把 `signature_b64` 写回
`BET-Y1Q3-T1-12-accept.yaml`，再更新台账 value 轴为 ACCEPTED。

## 1. 生成待签 message（与 bet-ledger 字节一致）

```bash
python3 - <<'PY'
fields = {
  "schema_version": "human-attestation/v1",
  "principal_id": "principal:xiamingxing",
  "verdict": "accept",
  "episode_id": "episode_bet_y1q3_t1_12",
  "signal_event_id": "evt_accept_bet_y1q3_t1_12",
  "observed_at": "2026-09-03T07:12:13Z",
}
order = [
  "schema_version","principal_id","verdict","episode_id","signal_event_id","observed_at"
]
msg = "\n".join(f"{k}={fields[k]}" for k in order) + "\n"
open("/tmp/t1-12-attestation-message.txt","w").write(msg)
print(msg)
PY
```

把 `2026-09-03T07:12:13Z` 换成 yaml 里的 `observed_at`（必须完全一致）。

## 2. SSH 签名

```bash
ssh-keygen -Y sign \
  -f ~/.ssh/id_ed25519 \
  -n omostation-human-attestation \
  /tmp/t1-12-attestation-message.txt
# 产出 /tmp/t1-12-attestation-message.txt.sig
```

identity 必须在 `docs/operations/human-attestation-allowed-signers` 中（当前为 `xiamingxing`）。

## 3. 写入 signature_b64

```bash
python3 - <<'PY'
import base64, pathlib
sig = pathlib.Path('/tmp/t1-12-attestation-message.txt.sig').read_bytes()
print(base64.b64encode(sig).decode())
PY
```

把输出填进 `BET-Y1Q3-T1-12-accept.yaml` 的 `signature_b64:`。

## 4. 本地验签

```bash
uv run --with pyyaml python - <<'PY'
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('bl', 'bin/plan/bet-ledger.py')
bl = importlib.util.module_from_spec(spec); spec.loader.exec_module(bl)
errs = bl.validate_human_attestation(
  receipt_path=Path('docs/operations/human-attestations/BET-Y1Q3-T1-12-accept.yaml'),
  workspace=Path('.'),
)
print('OK' if not errs else errs)
PY
```

## 5. 台账接线（签名通过后）

把 `completion_evidence.axes.value` 设为：

```yaml
status: ACCEPTED
evidence:
  attestation:
    ref: receipt://docs/operations/human-attestations/BET-Y1Q3-T1-12-accept.yaml
  human_verdict:
    ref: receipt://docs/operations/human-attestations/BET-Y1Q3-T1-12-accept.yaml
  real_signal:
    ref: receipt://.omo/_knowledge/retros/BET-Y1Q3-T1-12.md
  revision:
    ref: receipt://.omo/_knowledge/retros/BET-Y1Q3-T1-12.md
  time_burden:
    ref: receipt://.omo/_knowledge/retros/BET-Y1Q3-T1-12.md
```

engineering 需补 `merged_reachable_commit`（PR #2969 合入后的 main SHA）后，才可 `overall_state=outcome_accepted` + `status=done`。

## Canary 摘要（供验收）

- PR: https://github.com/starlink-awaken/omostation/pull/2969
- capability: `bos-service:bos://system/omo/debt`
- invocation_id: `sha256:037be67c40bdfa3e0af7e255de12f1e3203c2b4dfc23a5d3916b6310380784e3`
- receipt_digest: `sha256:02b5c14708fd60eddc3c24441331faa700a9363e7eb1b220fefa0a1e7652fea2`
- transport_state: confirmed；replay idempotent；cleanup proved
