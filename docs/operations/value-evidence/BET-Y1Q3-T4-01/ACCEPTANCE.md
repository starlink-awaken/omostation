# BET-Y1Q3-T4-01 价值轴 closeout 验收证据清单

- schema: value-axis-acceptance/v1
- bet: BET-Y1Q3-T4-01(真实个人价值证据脊柱)
- 轴: value(价值)—— status: ACCEPTED
- 生成: 2026-08-22
- 验证: `validate_completion_evidence` value 轴 errors = NONE ✓

## 证据链(credential-bound)

| 证据 | 文件 | 内容 | 验证 |
|---|---|---|---|
| real_signal | real_signal.md | 真实低敏信号(跨仓耦合观察), content_sha256 摘要 | sha256 匹配 |
| human_verdict | human_verdict.md | 用户 accept 裁决(经 personal-episode/feedback 端点) | credential 指纹匹配公钥 |
| revision | revision.md | RevisionReceipt(candidate_ref + revision_digest) | sha256 匹配 evidence |
| time_burden | time_burden.md | review 30s / saved 120s, 负担 < 节省 | 数值记录 |
| attestation | human-attestations/BET-Y1Q3-T4-01-accept.yaml | **SSH 签名**(ssh-keygen -Y verify PASS) | credential-bound 人类证明 |

## 完整事件链(ledger)

episode_088af4df0c0ed55f204e2bae 7 事件:
1. Episode.Decision.v1
2. Mandate.Granted.v1
3. Decision.Policy.v1
4. Action.Started.v1
5. Action.Succeeded.v1
6. Evidence.LocalDraft.v1(never-send draft, evidence:// 引用)
7. Outcome.Human.v1(accept + RevisionReceipt)

## north_star 实证

- current_week_qualifying_outcomes: 1
- four_week_value_gate: collecting
- verdict_distribution: {accept: 1}
- signal_to_verdict_latency_seconds: 91.5

## 隐私合规(AC-08)

- 正文: 只存 content_sha256 摘要, 无正文明文
- 绝对路径: evidence:// 不透明引用, 无 file://
- 凭证: 签名无密钥泄露(公钥指纹仅用于身份绑定)

## closeout 说明

本清单为 **value 轴**验收证据。完整 closeout 需三轴全绿:
- value: **ACCEPTED ✓(本清单)**
- engineering: VERIFIED(待推进方补 tests/diff/rollback 证据)
- operational: PROVEN(待推进方补 live_canary 等证据)
