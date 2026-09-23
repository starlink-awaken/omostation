---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-09-23
---
# 价值全窗独立裁决签名步骤（VALUE-WINDOW-20260923）

Agent **不能代签**。principal（夏明星）本地 `ssh-keygen -Y sign` 后，
把 `signature_b64` 写回 `VALUE-WINDOW-20260923-accept.yaml`。

前置：`value-recorder validate` 已 **30/30 qualifying**；GOLDEN_SLICE 三阈值全 met。
本 attestation 签的是 **整窗 accept**，不是单条 scene 裁决。

## 1. 生成待签 message（与 bet-ledger `_attestation_message` 字节一致）

```bash
python3 - <<'PY'
fields = {
  "schema_version": "human-attestation/v1",
  "principal_id": "principal:xiamingxing",
  "verdict": "accept",
  "episode_id": "episode_value_window_20260923",
  "signal_event_id": "evt_accept_value_window_20260923",
  "observed_at": "2026-09-23T07:16:39Z",  # 必须与 YAML 完全一致
}
order = [
  "schema_version","principal_id","verdict","episode_id","signal_event_id","observed_at"
]
msg = "\n".join(f"{k}={fields[k]}" for k in order) + "\n"
open("/tmp/value-window-attestation-message.txt","w").write(msg)
print(msg)
PY
```

`observed_at` 必须等于 `VALUE-WINDOW-20260923-accept.yaml` 中的值
（`2026-09-23T07:16:39Z`）。若 YAML 已改时间，以 YAML 为准重生成。

## 2. SSH 签名

```bash
ssh-keygen -Y sign \
  -f ~/.ssh/id_ed25519 \
  -n omostation-human-attestation \
  /tmp/value-window-attestation-message.txt
# → /tmp/value-window-attestation-message.txt.sig
```

`signer_identity` 必须在 `docs/operations/human-attestation-allowed-signers`（`xiamingxing`）。

## 3. 写入 signature_b64

```bash
python3 - <<'PY'
import base64, pathlib
sig = pathlib.Path('/tmp/value-window-attestation-message.txt.sig').read_bytes()
print(base64.b64encode(sig).decode())
PY
```

把输出替换 YAML 中的 `signature_b64: PENDING_SIGNATURE`。

## 4. 本地验签

```bash
uv run --with pyyaml python - <<'PY'
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('bl', 'bin/plan/bet-ledger.py')
bl = importlib.util.module_from_spec(spec); spec.loader.exec_module(bl)
errs = bl.validate_human_attestation(
  receipt_path=Path('docs/operations/human-attestations/VALUE-WINDOW-20260923-accept.yaml'),
  workspace=Path('.'),
)
print('OK' if not errs else errs)
PY
```

## 5. 签名通过后（agent 执行）

1. 重跑 `python3 bin/panorama/panorama-collect.py`
2. `panel_value.state` → `proven`（本 PR 已接线：验签通过才翻转）
3. `agent-brief.authority.value_proof` → `PROVEN`
4. `next_action: collect-qualifying-value-evidence` 应消失

## 禁止

- agent 代填 `signature_b64` / 伪造 message
- 窗口外回填 v2 样本
- 未验签就改 panel `state`
