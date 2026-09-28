---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
type: ssot
last-reviewed: 2026-08-29
title: OMO validator canonical UTC helper export
created: 2026-08-29
last_updated: 2026-09-03
bet_id: BET-Y1Q3-T10-54
---
# OMO validator canonical UTC helper export

## Intent

Restore the canonical `_utc_now` helper export required by the extracted
engineering-delivery consumer projection and shadow modules after the SRP
module split.

## Constraints

- Keep one timestamp implementation and reuse the existing UTC format.
- Change only the OMO child implementation and its focused regression test.
- Do not alter root governance, runtime state, service configuration, or the
  existing gitlink until the child fix is verified.

## Acceptance

- `engineering_delivery_consumer_projection` imports successfully.
- The focused consumer test suite collects and passes.
- The root pointer is updated only to the verified child main commit.
