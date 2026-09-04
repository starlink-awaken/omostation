---
lifecycle: history
owner: family-hub
created: 2026-08-30
last_updated: 2026-08-31
title: Family dashboard Workspace owner migration Phase A evidence
type: doc
bet_id: BET-Y1Q3-T10-111
---

# Family dashboard Workspace owner migration Phase A evidence

## Verdict

The family-hub child repository and Workspace root main now prove the Phase A
engineering owner. Child and root PRs merged, the root gitlink equals child
main, and current root main replay passed.

This is source ownership, privacy-safe reproduction, and boundary proof. It is
not live runtime relocation, Cockpit cutover, old-app retirement, or user-value
proof.

## Authority

- Accepted specification:
  `docs/superpowers/specs/2026-08-31-family-dashboard-owner-migration-phase-a-design.md`,
  SHA-256 `d833693de0a212a8a00e7ab6974c8511817291bd8254c609191c71884f4e186b`.
- Implementation plan:
  `docs/superpowers/plans/2026-08-31-family-dashboard-owner-migration-phase-a.md`,
  root-main SHA-256
  `8d15cf73804ac3ae887ee006572bd3db20df19785a48d18ef472f54dd31b19f4`.
- Initial child PR: `starlink-awaken/omostation-family-hub#3`, merged at
  `8037f79cb8d9ca1aae06d8b2d2fdb29db81ac310`.
- Receipt-provenance follow-up: `starlink-awaken/omostation-family-hub#4`,
  merged at authoritative child main
  `244ac31ea983328b9c4ec05c6b935bd9af2908a8`.
- Root PR: `starlink-awaken/omostation#2787`, merged.
- Root merge commit:
  `9a4caa312b7dc0230ff7ff178b4f0e994913a244`.
- Root provenance follow-up: `starlink-awaken/omostation#2796`; this unique PR
  advances only the family-hub gitlink from `8037f79c` to `244ac31e`.
- Child PR and post-merge CI both passed root lint, root build, Python,
  dashboard, and dashboard-e2e. The post-merge run is `33339335063`.
- Fresh child-main replay used an independent depth-one clone at the exact
  initial child main commit; the provenance follow-up was replayed by child
  main CI and the existing governed attempt03 clone.

## Import evidence

The source plan selected 265 canonical files and excluded 38,819
runtime/private/forbidden nodes. Twenty selected text files required
deterministic private-token substitution. No token or replacement value is
stored in the committed receipts.

- Initial full source: 39,084 nodes, 731,772,859 bytes,
  fingerprint
  `7fae629fb54f4907dd500ef3d66547a2e97d047f3298faf707859d98b778e170`.
- Selected source: 265 files, 865,326 target bytes, fingerprint
  `e6224315fe799d5a53dcdeecaf90292096a73202e1aa5d8a7452ec79ac178259`.
- Source receipt v2 SHA-256:
  `b310f1d3845b7f896cd89a8f03a1ece9b7c94e69576a16abe3df786203786f2e`.
- Target receipt v2 SHA-256:
  `c330991e7e5425c677575bbe1cc7c41cca628d4b0d4e51b576bdf963e569d524`.
- The source receipt binds redacted authority refs
  `documents://family-dashboard-app` and
  `repo://family-hub/apps/dashboard`; only path digests are stored, never the
  raw Documents authority path.
- The target receipt binds the exact source-receipt digest, expected imported
  target fingerprint
  `b750dbf7403934d9b215b81d476d74e1f71b2c554f59a53530ef03f797daf2d4`,
  observed adapted-target fingerprint
  `beb03026824f60b8324f52b3eb42d91b5b65429fa2af76af6e2d95e34f9d674f`,
  verification mode `adapted-target`, and `excluded_source_drift=true`.
- The two receipt files are excluded only from the product target fingerprint
  to prevent self-reference; their schemas, identities, digests, mode, drift,
  and fingerprints are validated separately and fail closed.
- Final private-token scan: zero matches outside ignored runtime products.
- Tracked forbidden class scan: zero paths.
- Tracked symlink scan: zero paths.
- Absolute user path, private-key, access-key, and token-pattern scan: zero
  matches outside immutable receipt hashes.

## Source drift adjudication

The selected 265-file fingerprint remains exactly equal to the initial receipt.
No selected source, household content, or source path was moved or rewritten.

The full-tree fingerprint changed to
`fca89835d5680475d3001932127dc18e2fdbfa59713af8f8648b1820a0851e8d`
and bytes changed from 731,772,859 to 731,772,857. Read-only investigation
isolated the change to one explicitly excluded generated cache:
`node_modules/.vite/vitest/da39a3ee5e6b4b0d3255bfef95601890afd80709/results.json`.
It was rewritten when the inherited six-failure legacy test baseline was
reproduced in the source application. The node count remained 39,084.

This cache-only drift is reported, not hidden. The adapted verification mode
therefore returns `excluded_source_drift=true` while still proving selected
source equality, original-path presence, target no-follow safety, and zero
private-token matches. Phase A does not claim bit-identical preservation of
reproducible source caches.

## Boundary evidence

- `FAMILY_DOCUMENTS_ROOT` is required, absolute, and read-only.
- `FAMILY_DASHBOARD_STATE_ROOT` is required, outside Documents, and rejects
  lexical and symlink escapes.
- No `process.cwd()/..`, `FAMILY_SSOT_ROOT`, direct `app-data`, or direct
  `data-manifest` runtime path remains.
- File save, SSOT backup, vaccine update, milestone update, and the legacy
  shell backup fail closed with `DOCUMENTS_WRITE_DISABLED`.
- Task, generated data, manifest, index, embedding, cache, and audit paths are
  under explicit Workspace state.
- Deployment configuration mounts Documents `:ro` and state `:rw`; it contains
  no legacy SSOT root or `data-manifest` copy.

## Verification matrix

- Importer focused tests: 22 passed; Ruff and format checks passed.
- Child Python/FastMCP replay after provenance repair: 68 passed.
- Existing Vite root: lint passed; production build passed.
- Dashboard unit replay: 77 passed.
- Dashboard TypeScript: zero errors.
- Dashboard lint: exit 0, zero errors; inherited warnings remain non-blocking.
- Synthetic Next production build: 43 routes generated without live household
  data or tracked build drift.
- Playwright: 20 passed, including authentication, representative pages, and
  disabled write APIs.
- Docker Compose syntax: passed with explicit read-only Documents and writable
  state inputs.
- Adapted import verification: `status=verified`, selected fingerprint equal,
  v2 receipts equal, observed target fingerprint equal, and
  `excluded_source_drift=true` as adjudicated above.
- Child post-merge CI run `33339335063`: all five jobs passed.
- Root worktree `--require-main` reachability: 14 of 14 gitlinks passed; the
  family-hub worktree and proposed gitlink both resolve to `244ac31e` on child
  `origin/main`.
- Root pre-push GaC local gate: 56 checks executed, all green.
- Root BET verifier: all six registered command groups exited zero, including
  57 blocking GaC checks.

## Completion axes after root merge

- Engineering child and root authority: `VERIFIED`.
- Phase A operational delivery (CI, synthetic E2E, receipts, mainline replay):
  `PROVEN`.
- Live operational/runtime state: `NOT_PROVEN`.
- Cockpit/consumer cutover: `NOT_PROVEN`.
- Old Documents app retirement: `NOT_PROVEN`.
- Principal-bound value: `NOT_PROVEN`.
- Documents-wide physical purity: `NOT_PROVEN`.

The `family-dashboard-app` migration family remains `pending`.
