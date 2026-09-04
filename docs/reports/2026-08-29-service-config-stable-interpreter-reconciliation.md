---
type: ephemeral
created: 2026-09-03
---

# Service-config stable interpreter reconciliation — 2026-08-29

## Finding

The existing generated plist files used `/opt/homebrew/bin/python3`, while
`gen-service-configs.py --check` under `uv run` selected `/usr/bin/python3`
after excluding uv temporary and virtualenv paths. This produced four false
drift findings without any service semantic difference.

## Repair

`_stable_python3()` now prefers an existing fixed Homebrew Python path, then a
fixed `/usr/local/bin/python3` path, before scanning the caller PATH. The
generator still rejects uv temporary/virtualenv interpreters and all registry
arguments/resilience/watch/output semantics are unchanged. No host plist was
written, loaded, unloaded, or rewritten.

## Verification

- Regression tests: `5 passed`.
- `gen-service-configs.py --validate --json`: `ok=true`, zero violations.
- `gen-service-configs.py --check --json` under `uv run`: `ok=true`,
  `drift_count=0`.
- `make gac-local-gate`: PASS, 57 checks executed, all green; six known
  unavailable checks remain skipped by the default non-strict policy.
- Four host plist SHA-256 values were identical before and after the check:
  `com.l4.governance.watch=412d0f16c84b68064f5e6e149227bac32b9f77fb156f7a12a4a9cef822ffc329`,
  `com.l4.resident.orchestrator=131dd5860d5f629c7a1764fb158ea01fff1dce60624c3905bbc987e5e49534db`,
  `com.l4.gac.watchdog=4d9050542cfd91c69cf53ffd9dc6642daf24e8c756f6c184d49d71e49aa3cf2f`,
  `com.l4.mail.daemon=f3558a2984203672beeb544346a27408106be55f3904b220c77d2cd768b1c7d9`.

The host drift itself was not papered over by rewriting plist files; the
generator/check identity was made deterministic at its source.
