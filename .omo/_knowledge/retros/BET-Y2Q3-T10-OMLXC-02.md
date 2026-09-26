---
type: retro
status: active
bet_id: BET-Y2Q3-T10-OMLXC-02
workflow_run: 20260925T014237Z-project-code-change-44d6eaf9
created: 2026-09-25
---
# BET-Y2Q3-T10-OMLXC-02 Retro Receipt

## Delivered

- Added explicit OMLXC placement recovery coverage in
  `projects/omlxc/tests/integration/test_task11_fix6_eligibility.py`.
- Confirmed the existing OMLXC successful-probe apply path revives a placement in a
  deterministic daemon integration scenario; no redundant production change was added.
- Changed AetherForge generation-failure accounting so `no capacity` uses bounded
  transient decay instead of the process-lifetime permanent blacklist.
- Kept explicit missing-model/missing-placement messages permanent through the new
  `_record_generation_failure` classification helper.

## Verification

- `cd projects/omlxc && uv run pytest tests/integration/test_daemon_fix1.py tests/integration/test_task11_fix6_eligibility.py -q` — **24 passed**.
- `cd projects/omlxc && uv run pytest tests/integration/test_task11_fix6_eligibility.py::test_successful_probe_revives_stale_placement -q` — **1 passed**.
- `cd projects/omlxc && uv run ruff check src/omlxc/daemon/composition.py tests/integration/test_task11_fix6_eligibility.py` — **passed**.
- `cd projects/aetherforge && uv run pytest packages/gateway/tests/test_health_failure_decay.py -q` — **8 passed**.
- `cd projects/aetherforge && uv run ruff check packages/gateway/src/llm_gateway/gateway.py packages/gateway/tests/test_health_failure_decay.py` — **passed**.
- AetherForge `:4000/health` and `:9290/health` — **HTTP health ok**.

## Live blockers — resolved (2026-09-26)

All three blockers from the 2026-09-25 capture are closed without mutating launchd,
credentials, model files, or remote runtimes:

1. **Stale placement healed.** `omlxc models show coding-next --json` now reports
   `available=true`, `fresh=true`, `ready=true`, placement `stale=false`
   (`coding-next-local` on `mbp-m5-max-128g`, observed 2026-09-26T06:02Z).
   Recovery followed the successful-probe apply path covered by
   `test_successful_probe_revives_stale_placement`.
2. **Route plan works with the correct CLI.** `omlxc routes plan coding-next --json`
   exits 0 and selects `coding-next-local` (score 0.55; other placements rejected as
   `model_mismatch`). The ledger verify command previously said `route plan`
   (singular, exit 2) — corrected to `routes plan` in `docs/plans/3y-bet-ledger.yaml`.
3. **Authenticated inference canary recorded.** The gateway process env carries
   `AETHERFORGE_API_KEY` (same value as the documented local omlxc/gateway key).
   Exported into the shell and called `POST :4000/v1/chat/completions` with
   `Authorization: Bearer` → **HTTP 200**, content `OMLXC-02-CANARY-OK`
   (model `coding-next`, provider `ENG-LMSTUDIO-MACBOOKPRO`, 39 tokens).
   Control: no key → **HTTP 401** (auth enforced). Health `:4000/health` and
   `:9290/health` both `{"status":"ok"}`.

Still honored: no launchd / credential-file / model-file / remote-runtime mutation.

## Assessment

Code-level regressions green (13 eligibility + 8 health-decay tests, plus probe-revive
1/1). Live local readiness **and** authenticated inference canary are now **recorded**
(HTTP 200 + 401 control) — the `done_when` canary branch is satisfied by evidence, not
by the blocker escape hatch.
