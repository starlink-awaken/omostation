# Debt reporting entrypoints design

Date: 2026-06-02
Status: approved-by-default baseline (user requested continuation; user unavailable during design approval, so proceeded with the recommended bounded slice)
Scope: expose the newly added debt campaign and reporting surfaces through first-class registry/state entrypoints, refresh-flow integration, and reference validation, without changing reporting math or introducing cross-run historical analytics

## 1. Context

The debt-governance stack now has these derived surfaces:

1. `.omo/debt/dashboard/current.yaml` for debt health and cadence
2. `.omo/debt/dispatch/current.yaml` plus immutable run snapshots for surfaced handoff
3. `.omo/debt/campaign/current.yaml` plus run-scoped current views for run coordination
4. `.omo/debt/reporting/current.yaml` plus run-scoped current views for compact latest-run progress

However, the higher-level discovery surfaces still stop at the pre-campaign layer:

1. `.omo/debt/registry.yaml` exposes `dashboard_ref`, `review_pack_ref`, `review_queue_ref`, `action_packet_ref`, `owner_routing_ref`, and `dispatch_ref`, but not campaign or reporting
2. `scripts/omo_debt_registry.py` models the same gap in `DebtLedger`
3. `scripts/sync_omo_state.py` promotes `debt_registry_ref`, `debt_dashboard_ref`, and `debt_review_pack_ref` into `state/system.yaml`, but not reporting
4. the canonical verify flow does not validate registry-level refs, so a new `campaign_ref` or `reporting_ref` could silently point at a missing file
5. the canonical operator flow in `.omo/AGENT.md` documents `campaign` and `report`, but does not yet fold them into the refresh / sync cadence

That means the next missing layer is no longer a new reporting feature.

The real next gap is:

> campaign and reporting now exist as valid generated surfaces, but the control plane still cannot reliably discover, refresh, or validate them as first-class debt-governance entrypoints.

## 2. Goals

This design should:

1. expose campaign and reporting via canonical debt registry pointers
2. promote only the health-adjacent reporting pointer into `state/system.yaml`
3. make registry-level generated refs fail loudly if they point to missing artifacts
4. update the canonical refresh flow so campaign and reporting stay fresh after dispatch changes
5. hydrate the live `.omo/debt/campaign/*` and `.omo/debt/reporting/*` artifacts as part of landing the slice

## 3. Non-goals

This design does not:

1. change campaign or reporting packet schemas
2. change approval coverage or execution completion math
3. add cross-run history, burndown, or trend analytics
4. promote every debt surface into `state/system.yaml`
5. auto-regenerate campaign or reporting during `approve` or `revalidate`

## 4. Approaches considered

### A. Recommended: entrypoint exposure with hydration, refresh integration, and validation

Add `campaign_ref` and `reporting_ref` to the registry, promote only `debt_reporting_ref` into state, validate registry-level refs in the sync / verify chain, update the canonical refresh flow, and hydrate the live generated artifacts during rollout.

Pros:

- closes the discoverability gap without inventing new reporting semantics
- keeps SSOT discipline by validating the new pointers instead of trusting them
- preserves the distinction between operator coordination detail and higher-level health/progress pointers
- keeps scope narrow and directly useful

Cons:

- requires touching several existing governance seams together
- adds one more class of validation to the sync path

### B. Narrower: add the new refs only

Add registry/state pointers but do not change hydration, refresh flow, or validation.

Pros:

- very small diff
- fast to land

Cons:

- leaves dangling-ref risk undetected
- makes the new pointers stale immediately after future dispatch runs
- weakens the point of making them canonical entrypoints

### C. Wider: combine entrypoints and cross-run history

Expose the new surfaces and immediately add multi-run reporting history.

Pros:

- more visible management output
- avoids another future design pass

Cons:

- couples a low-risk discoverability fix to a much higher-risk analytics design
- cross-run semantics are still intentionally deferred
- violates the narrowest-high-value-next-step principle

## 5. Recommended design

Use **Approach A**.

The core decision is:

> the next increment should make campaign and reporting first-class debt entrypoints by adding registry refs, promoting only reporting into state, validating registry-level refs, folding campaign/report generation into the canonical refresh flow, and hydrating the live artifacts during rollout, while explicitly deferring cross-run historical reporting.

This sequencing is correct because:

1. campaign and reporting already exist and are tested
2. the missing value is control-plane discoverability and freshness, not more reporting math
3. reporting is health-adjacent enough for state promotion, while campaign remains operator-detail only
4. registry-level pointers are not trustworthy unless the sync path validates them

## 6. Architecture

### 6.1 Registry promotion

Extend `.omo/debt/registry.yaml` with:

1. `campaign_ref: .omo/debt/campaign/current.yaml`
2. `reporting_ref: .omo/debt/reporting/current.yaml`

Extend `DebtLedger` in `scripts/omo_debt_registry.py` with matching fields so the registry contract and the in-memory model stay aligned.

These remain canonical registry pointers, not writable truth.

### 6.2 State promotion rule

Make the selection rule explicit:

1. `state/system.yaml` should carry debt summary metrics and a small number of high-level navigational pointers
2. surfaces that primarily answer workspace health / progress questions are eligible for state promotion
3. surfaces that primarily answer operator execution-detail questions remain registry-only

Under that rule:

1. `debt_reporting_ref` should be promoted into `state/system.yaml`
2. `campaign_ref` should remain registry-only

Reasoning:

- reporting is the compact progress rollup that a higher-level control plane can consume directly
- campaign is still a detailed coordination surface analogous to `dispatch_ref`, which also remains outside state today

### 6.3 Registry-level ref validation

The sync path should validate debt registry refs that are expected to exist as generated surfaces.

Add a debt-specific validation step in `scripts/sync_omo_state.py` that checks the existence of:

1. `dashboard_ref`
2. `review_pack_ref`
3. `review_queue_ref`
4. `action_packet_ref`
5. `owner_routing_ref`
6. `dispatch_ref`
7. `campaign_ref`
8. `reporting_ref`

Behavior:

1. missing refs should produce divergence flags and detail artifacts, not silent success
2. the validation should treat missing files as control-plane drift, not as a normal empty state
3. the implementation should stay debt-specific rather than broadening `_dangling_reference_flags` to unrelated OMO registries

### 6.4 Refresh-flow integration

The canonical debt-governance operator flow should become:

1. `python3 scripts/omo_debt.py refresh --omo-dir .omo --now <ISO8601>`
2. `python3 scripts/omo_debt.py dispatch --omo-dir .omo --now <ISO8601>`
3. `python3 scripts/omo_debt.py campaign --omo-dir .omo`
4. `python3 scripts/omo_debt.py report --omo-dir .omo`
5. `python3 scripts/sync_omo_state.py --omo-dir .omo`
6. `bash bin/verify-omo.sh`

Design intent:

1. campaign and reporting remain explicit aggregate commands
2. they are refreshed after dispatch because dispatch selects the current surfaced run
3. sync and verify happen only after those latest generated surfaces exist

### 6.5 Rollout hydration

This slice must hydrate the live generated surfaces as part of landing the work.

Required rollout actions:

1. run `campaign --omo-dir .omo`
2. run `report --omo-dir .omo`
3. confirm `.omo/debt/campaign/current.yaml` exists
4. confirm `.omo/debt/reporting/current.yaml` exists
5. then write the new registry/state pointers

Without this step, the newly added canonical refs would immediately be dangling.

## 7. Error handling

The slice should fail loudly when:

1. a promoted debt registry ref points at a missing file
2. sync tries to publish `debt_reporting_ref` but the target file does not exist
3. the live rollout flow cannot hydrate campaign or reporting artifacts before updating refs

The slice should not reinterpret missing campaign/report artifacts as “not generated yet” once the refs are canonicalized. After this slice, missing files indicate drift.

## 8. Testing strategy

The implementation plan should cover at least:

1. `DebtLedger` loads `campaign_ref` and `reporting_ref`
2. `sync_omo_state.py` promotes `debt_reporting_ref` into `state/system.yaml`
3. sync produces divergence when a debt registry ref points to a missing file
4. `state/system.yaml` still does **not** receive `debt_campaign_ref`
5. `.omo/tests/test_omo_debt_cli.py` fixture registry string is updated for the new fields
6. `.omo/AGENT.md` documents the updated canonical refresh flow including `campaign` and `report`
7. live `.omo/debt/campaign/current.yaml` and `.omo/debt/reporting/current.yaml` are generated before the registry/state pointers are finalized
8. canonical `bash bin/verify-omo.sh` remains green

## 9. Success criteria

This slice is successful when:

1. higher-level control-plane readers can discover reporting from `state/system.yaml`
2. deeper debt readers can discover both campaign and reporting from `.omo/debt/registry.yaml`
3. missing campaign/reporting artifacts can no longer hide behind silent registry refs
4. the canonical operator flow keeps the newly exposed surfaces fresh after dispatch changes
5. the system remains explicitly single-run for reporting and does not accidentally drift into historical analytics
