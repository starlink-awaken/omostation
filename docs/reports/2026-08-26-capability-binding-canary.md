---
type: ephemeral
created: 2026-09-03
---

# Production-topology canary — exact capability binding (2026-08-26)

Scope-honest execution receipt for plan Task 7 step 3. Driver: real subprocess
runs of `bin/capability-sync.py` against a sandbox registry/receipt set
(`/tmp/canary_driver.py`, outputs embedded below). Nothing is inferred from
unit tests alone; items that require the live Agora gateway or OMO Tasks 2/3
are recorded BLOCKED / CONTRACT-COVERED instead of claimed.

## Executed negatives (provider invocation count 0 in every case)

| Case | Kind | rc | Receipt status |
|---|---|---|---|
| missing_binding | negative | 5 | rejected |
| wrong_packet_hash_shape | negative | 5 | rejected |
| non_exact_selector | negative | 5 | rejected |
| wrong_admission_worker_status | negative | 2 |  |
| partial_bundle | negative | 4 | rejected |

`wrong_admission_worker_status` exits rc=2 (argparse-level SystemExit from the
redacted error path) — non-zero/blocked as required; tracked as a cosmetic
exit-code alignment follow-up.

## Positives

| Required evidence | State |
|---|---|
| accepted Spec/WorkPacket start | **DEPS-DELIVERED / LIVE-RUN-PENDING** — T2 landed via omo #101; T3 landed via root #2285; only the gateway-backed execution remains |
| admitted dispatch | **DEPS-DELIVERED / LIVE-RUN-PENDING** — dispatch recheck consumes persisted admission (omo-integrity); live run pending |
| confirmed read-only native receipt | **CONTRACT-COVERED** — bound path unit contracts (root #2248 suite, cockpit #86); live-gateway run pending |
| replay with zero new invocation | **CONTRACT-COVERED** — idempotency-key contract in worker-lifecycle suites |
| cleanup proof | **CONTRACT-COVERED** — proved-cleanup validator exercised in native-receipt suites |

## Conclusion

Negative surface fully executed and blocked correctly. Tasks 2/3 have since
landed (omo #101, root #2285): the dependency blocker is cleared, so positive
topology now awaits only a gateway-backed execution run; value stays
NOT_PROVEN until then.
