---
schema: value-evidence/engineering-tests/v1
bet: BET-Y1Q3-T4-01
axis: engineering
evidence_key: tests
test_files:
  - tests/test_north_star_meter_v2.py        # NorthStar causal 派生 + 三轴 fail-closed (21 tests)
  - tests/test_compound_attribution_report.py # compound-attribution 三轴报告 (12 tests)
  - tests/test_spec_binding_lint.py          # spec binding + completion-evidence + attestation (30 tests)
ci_status: all_green
verified_at: 2026-08-22

last-reviewed: 2026-08-25
---

工程测试证据:
- NorthStar 测试: 验证三轴分离(工程绿不推价值)+ causal 派生(只从真实 receipt)
- compound-attribution 测试: 验证 overall=unprovable 推导
- spec-binding-lint 测试: 验证 completion-evidence 三轴矩阵 + credential-bound attestation verifier
  (含 valid/tampered/missing 三态 attestation 测试)

main CI: Cascading Topological Tests success(#1876 后保持绿)
