---
schema_version: report/v1
type: report
title: BET-Y1Q4-T8-12 CLI behavior contract closeout
bet_id: BET-Y1Q4-T8-12
status: final
lifecycle: evidence
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T8-12 Closeout Receipt

## Verify

```text
uv run --project projects/cockpit pytest projects/cockpit/tests/test_cli_contract.py -q
......                                                                   [100%]
6 passed in 0.28s
```

## Assertions locked

| Assertion | Evidence |
|-----------|----------|
| ExitCode 0..5 | `tests/test_cli_contract.py::test_exit_code_contract_values` |
| `--json` zero ANSI | `test_get_console_force_json_has_no_ansi` + e2e unknown-command |
| `trace_id` envelope | `test_json_print_envelope_includes_trace_id_and_zero_ansi` + e2e |

## Artifacts

- Spec: `docs/superpowers/specs/2026-09-05-cli-behavior-contract-design.md`
- Child PR: https://github.com/starlink-awaken/omostation-cockpit/pull/132
- Delivery SHA (child, post-rebase): `83990eac42d48ada7563d741572b313f7b050843`
- Retro: `.omo/_knowledge/retros/BET-Y1Q4-T8-12.md`
