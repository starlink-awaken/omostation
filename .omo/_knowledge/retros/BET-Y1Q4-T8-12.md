---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T8-12 Closeout Retro — ExitCode / ANSI purity / Trace-ID
bet_id: BET-Y1Q4-T8-12
status: archived
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T8-12 Closeout Retro

> **TL;DR**: 落地 `cockpit.output` + `cli.py` 机器路径接线；ExitCode 0..5、`--json` 0 ANSI、`trace_id` 信封由 `tests/test_cli_contract.py` 锁死。Child PR `#132` → root pointer bump → ledger `delivery_accepted`。

## Deliverables
- Cockpit child: `#132` (`agent/bet-y1q4-t8-12-cockpit`) — `output.py` + `cli.py` + `test_cli_contract.py`
- Spec: `docs/superpowers/specs/2026-09-05-cli-behavior-contract-design.md`
- Closeout receipt: `docs/reports/2026-09-05-t8-12-cli-contract-closeout.md`

## Q1
Appetite 2 days；本轮实现+关账约数小时（含 Spec binding、PASW claim、child PR、root closeout）。

## Q2
- ExitCode 统一收敛至 ExitCode 规范：PASS（IntEnum 0..5 + 别名断言）
- 机器输出 (`--json`) 达到 0 ANSI 纯净度：PASS（`get_console(force_json=True)` + e2e unknown-command）
- `trace_id` 全链路贯穿：PASS（`configure_logging` 注入 env + JSON 信封 `trace_id`）
- Verify：`uv run --project projects/cockpit pytest projects/cockpit/tests/test_cli_contract.py` → 6 passed

## Q3
1. `accepted_specifications` 缺失会在 `start --bet` 被 SPEC_BINDING 拦截 — 必须先写 Spec 再 start。
2. claim docs/retro/ledger 需要 affected-graph 含 `workspace-root`；仅 `cockpit` 不够。
3. PASW：代码改在 `.subtrees/cockpit`，verify 路径仍是 `projects/cockpit` — 本地需 sync/copy 或 bump 后再跑门禁命令。
4. argparse 非法子命令走 `sys.exit(2)`，契约测试须 `pytest.raises(SystemExit)`，不能假设 `main()` 返回。

## Q4
净增：`output.py`、契约测试、Spec/retro/report；`cli.py` 小范围接线。不扩散全量子命令改写（non-goal / follow-up）。

## Q5
后续命令群可逐步改用 `cockpit.output.json_print` / `get_console`；结构化 JSON logging handler 留给 T8-14。关账两段 commit：delivery（含 pointer）→ done+completion_evidence（`merged_reachable_commit` 用 PR 分支可达 SHA，rebase 后用重写后的 delivery SHA）。
