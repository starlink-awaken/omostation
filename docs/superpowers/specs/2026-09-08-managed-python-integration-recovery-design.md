---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-09
last-reviewed: 2026-09-09
title: A3 Managed Python test-only integration recovery
bet_id: BET-Y1Q4-T10-142
value_indicator_policy: false
implementation_authorized: true
---

# A3 Managed Python test-only integration recovery

## 1. Context and verified baseline

The managed-Python selector itself is healthy for both required profiles: the
`stdlib` and `pyyaml` probes resolve to the managed Python 3.14.7 runtime and
produce `managed-python-runtime-receipt/v1` receipts. The remaining A3 gap is
limited to two integration-test fixtures in
`tests/unit/gac/test_managed_python_runtime.py`:

1. the thin-hook fixture copies the tracked `pre-commit` and `pre-push` hooks
   but omits the real `bin/gac/hook-runner.sh`, so the test exits 127 before it
   can exercise the production hook chain; and
2. the clone-snapshot fixture calls the Make target without the now-required
   `DELIVERY_ATTEMPT_ID`, so the production contract correctly rejects it.

The current focused baseline is therefore 4 passed and 2 failed. These are
fixture-contract failures, not evidence that the production selector or hooks
must change.

## 2. Goal

Restore truthful managed-Python integration coverage by updating only the
existing test fixture so that it exercises the current production contracts.
The delivery must prove the real thin-hook-to-runner-to-selector path and the
current clone-snapshot Make contract without modifying production behavior.

## 3. Exact implementation contract

The only human-authored tracked implementation surface is:

```text
tests/unit/gac/test_managed_python_runtime.py
```

The implementation must:

1. copy the real `bin/gac/hook-runner.sh` into the test's temporary repository
   together with the real thin hooks and hook manifest;
2. keep the fake managed-Python executable as a leaf-call logger only, never as
   a replacement for the real hook runner;
3. create bounded stubs for every manifest leaf traversed by the tested hooks;
4. prove that a non-zero blocking leaf remains non-zero through `pre-push`; and
5. invoke `make clone-snapshot` with both `AGENT_ID=probe` and
   `DELIVERY_ATTEMPT_ID=managed-python-test-01`.

The following production surfaces are read-only inputs to the test:

```text
.githooks/pre-commit
.githooks/pre-push
bin/gac/hook-runner.sh
.omo/_truth/registry/hook-manifest.yaml
bin/gac/managed-python
Makefile
```

## 4. Acceptance criteria

| ID | Assertion | Evidence |
|---|---|---|
| A3-AC-01 | The focused file finishes with 6/6 tests passing. | Exact pytest command and exit code 0. |
| A3-AC-02 | The hook fixture executes the tracked thin hooks through the real tracked runner and managed selector boundary. | Test trace from the leaf-call logger. |
| A3-AC-03 | A blocking manifest leaf's non-zero result propagates through `pre-push`. | Focused negative-path assertion. |
| A3-AC-04 | The clone-snapshot fixture supplies the required delivery-attempt identity. | Focused Make-target assertion. |
| A3-AC-05 | `stdlib` and `pyyaml` selector probes both resolve to executable Python 3.14.7 with their exact requested capabilities. | Two `managed-python-runtime-receipt/v1` JSON receipts. |
| A3-AC-06 | Default workflow verification, compliance and repository GaC accept the one-file implementation diff. | Command receipts plus required PR contexts. |

Canonical focused verification:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 GIT_OPTIONAL_LOCKS=0 \
  /opt/homebrew/bin/python3 -B -m pytest -q -p no:cacheprovider \
  tests/unit/gac/test_managed_python_runtime.py
OMO_MANAGED_PYTHON=/opt/homebrew/bin/python3 \
  bin/gac/managed-python probe --profile stdlib --json
OMO_MANAGED_PYTHON=/opt/homebrew/bin/python3 \
  bin/gac/managed-python probe --profile pyyaml --json
```

## 5. Non-goals and evidence boundary

- Do not modify production hooks, the hook runner, the managed-Python selector,
  the hook manifest, the Makefile, CI or host configuration.
- Do not change any existing BET, Spec, completion evidence or value evidence.
- Do not treat a test-only green result as proof that the full A3 operational
  release is complete.
- Value remains `NOT_PROVEN` and is excluded from personal value indicators.

## 6. Circuit breakers and rollback

Stop and request a scope successor if any production surface must change, the
accepted Spec digest drifts, the generated WorkPacket contains any path other
than the single test file, or a default governance/CI gate rejects the actual
changes. Rollback is a clean revert of the one-file test commit; no runtime or
host rollback is required because this contract permits no runtime mutation.

## 7. Delivery order

1. Merge this accepted Spec, its single candidate BET binding and the bootstrap
   waiver in one binding-only PR.
2. Re-read the merged Spec digest from `main`.
3. Start a fresh, normally bound workflow for `BET-Y1Q4-T10-142`; the unbound
   bootstrap run must not be reused.
4. Generate a WorkPacket whose write surface is exactly the one test file.
5. Reproduce the two focused failures, apply the fixture-only repair, run all
   acceptance checks, submit one implementation PR and verify the merged object.

## 8. Decision log

| Decision | Ruling | Reason |
|---|---|---|
| Repair tests or production code | Test fixture only | Current production selector probes are healthy; both failures are missing fixture inputs. |
| Hook execution boundary | Real thin hooks and real runner | Replacing the runner with a fake would create a false green. |
| Make invocation | Supply `DELIVERY_ATTEMPT_ID` | This is the current production identity contract, not an optional test detail. |
| Value status | `NOT_PROVEN` | Integration coverage is engineering evidence, not personal value evidence. |
