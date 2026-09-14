---
schema: value-evidence/engineering-tests/v1
bet: BET-Y1Q3-T4-01
axis: engineering
evidence_key: tests
test_files: 
ci_status: all_green
verified_at: 2026-08-22
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-26
type: ephemeral
status: archived
---

last-reviewed: 2026-08-26
---
工程测试证据:
- NorthStar 测试: 验证三轴分离(工程绿不推价值)+ causal 派生(只从真实 receipt)
- compound-attribution 测试: 验证 overall=unprovable 推导
- spec-binding-lint 测试: 验证 completion-evidence 三轴矩阵 + credential-bound attestation verifier
  (含 valid/tampered/missing 三态 attestation 测试)

main CI: Cascading Topological Tests success(#1876 后保持绿)
