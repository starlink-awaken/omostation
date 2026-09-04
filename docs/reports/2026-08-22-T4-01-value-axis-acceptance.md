---
type: ephemeral
created: 2026-09-03
---

# BET-Y1Q3-T4-01 价值轴验收报告

- 报告编号: VALUE-ACCEPTANCE-Y1Q3-T4-01
- 生成时间: 2026-08-22
- 验收对象: BET-Y1Q3-T4-01「真实个人价值证据脊柱」价值轴(value)
- 验收结论: **ACCEPTED(通过)** —— credential-bound 人类价值证据链完整、可验证、自洽

## 1. 验收范围

本报告覆盖 T4-01 的 **value 轴**(AC-08 真实价值样本)验收。工程(engineering)与
运行(operational)轴由推进方在 #1853-#1867 系列中评估, 不在本报告范围。

验收依据:
- spec: `docs/superpowers/specs/2026-08-20-value-proof-truth-rebaseline-design.md` §7.2
- 完成标准: `#1832` completion-evidence-matrix/v1, value=ACCEPTED 需
  real_signal + human_verdict + revision + time_burden + **credential-bound attestation**

## 2. 验收证据链

| 环节 | 证据文件 | 关键字段 | 验证结果 |
|---|---|---|---|
| 1. 真实信号 | `value-evidence/BET-Y1Q3-T4-01/real_signal.md` | content_sha256: `c2c072f2...` | ✅ 匹配 ledger SignalObserved |
| 2. 人类裁决 | `value-evidence/.../human_verdict.md` | verdict=accept, credential 指纹 `OEfesj1+...` | ✅ 匹配公钥指纹 |
| 3. 修订 | `value-evidence/.../revision.md` | revision_digest: `bf98089f...` | ✅ 匹配 evidence:// 引用 |
| 4. 时间负担 | `value-evidence/.../time_burden.md` | review 30s < saved 120s | ✅ Phase 2 门有利 |
| 5. 凭证绑定 | `human-attestations/BET-Y1Q3-T4-01-accept.yaml` | SSH 签名(ssh-keygen -Y verify) | ✅ **PASS** |

`validate_completion_evidence` value 轴 errors = **NONE** ✓

## 3. 事件链(ledger)

episode `episode_088af4df0c0ed55f204e2bae`, 7 事件完整:

```
1. Episode.Decision.v1         — 信号→episode 决策
2. Mandate.Granted.v1          — A2/R0 授权
3. Decision.Policy.v1          — 执行策略
4. Action.Started.v1           — 动作开始
5. Action.Succeeded.v1         — never-send draft 生成
6. Evidence.LocalDraft.v1      — evidence:// 引用(不含路径)
7. Outcome.Human.v1            — accept + RevisionReceipt
```

链完整性: `verify_chain` ok(39 事件, 无坏序列)

## 4. NorthStar 实证

| 指标 | 值 |
|---|---|
| current_week_qualifying_outcomes | **1** |
| four_week_value_gate | collecting |
| verdict_distribution | {accept: 1} |
| signal_to_verdict_latency_seconds | 91.5 |
| truth_axes.operational_proof | proven |
| truth_axes.personal_value | collecting |

## 5. 隐私合规(AC-08)

- 正文: 仅存 content_sha256 摘要, 无正文明文 ✓
- 绝对路径: evidence:// 不透明引用, 无 file:// ✓
- 凭证: 签名无密钥泄露, 公钥指纹仅用于身份绑定 ✓

## 6. 验证方法

1. `validate_human_attestation` — SSH 签名验证(真实密钥) PASS
2. `validate_completion_evidence` — value=ACCEPTED 矩阵 errors=NONE
3. ledger `verify_chain` — 哈希链完整
4. 交叉一致性 — episode_id / signal_id / content_sha256 / credential / digest
   在证据文件与 ledger 间逐项比对一致

## 7. 结论

T4-01 价值轴 **ACCEPTED**。真实低敏信号(跨仓耦合机制半删观察)走通
`SignalReceipt → never-send candidate → 用户 accept → RevisionReceipt/OutcomeFeedback
→ credential-bound attestation` 全链。这是系统首个**由真实人类裁决 + 凭证签名**
共同推动的 value 轴证据, 满足 #1832 完成标准的 value 轴要求。

**遗留**: engineering(VERIFIED)+ operational(PROVEN)轴证据由推进方补齐后可整体 closeout。

---
*验收人: principal:xiamingxing(凭证绑定)*
*验签公钥: ssh-ed25519 SHA256:OEfesj1+Ll2UT1xCKWvbdo4xNNZvqQUnNsFtYLQfRKw*
