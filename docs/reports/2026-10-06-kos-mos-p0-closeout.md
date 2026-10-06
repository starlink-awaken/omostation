---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-06
type: report
---

# BET-Y2Q4-T3-04 closeout receipt (2026-10-06)

Completion evidence receipt for BET-Y2Q4-T3-04 (KOS/MOS P0 four fixes).

## Delivery

- **kairon PR #97** — `fix(kos,mos): default-deny SQL authorizer, CJK intent routing, raw-body FTS, live-backend truth`, merged 2026-10-06T03:43:07Z by **squash** as `35f2ab778053e7e125fca779aba7b696661ae9c4` (kairon main).
- **omostation PR #4653** — `fix(gac,omo): KOS/MOS P0 four fixes with spec BET-Y2Q4-T3-04 + follow-up BET-Y2Q4-T10-231` (+ gitlink re-point commit `bf2fbdac1`), merged 2026-10-06T03:50:27Z by **squash** as `b26697f8a544d1e8cc7c5adb554541237b14abf3` (omostation main).
- Root gitlink now points at `35f2ab77` (kairon main tip).

## Verification (real)

- MOS suite: **93 passed**.
- KOS suite: **574 passed / 3 failed / 13 skipped** — the 3 failures are pre-existing and unrelated (verified identical on the untouched baseline): `test_check_orphan_entities` (alerts.py NameError), `test_find_path`, `test_evolve` (`no such column: predicate`).
- `make gac-local-gate`: **PASS** (65 checks; 1 SOFT WARN = test-mcp-kos DB soft-skip).
- `bet-ledger lint`: **OK (527 bets, 16 tracks)**.
- `doc-ssot-lint --json`: 0 findings.
- `bin/ssot/test-mcp-kos.py`: default-deny authorizer subtest PASS; protocol checks exit 78 without runtime `data/kos/`.
- Root PR #4653 CI: all required checks PASS, including `governance-verify`/`guard` after the gitlink re-point (`submodule-reachability`).

## D3 deviation + the gitlink hazard (Q3 lessons)

- **D3 deviation**: `bin/ssot/test-mcp-kos.py` was delivered without a workflow claim because the follow-up BET (T10-231) could not acquire the shared `root-gate` lock while the base run was active. Human-approved; recorded in `.omo/_knowledge/retros/BET-Y2Q4-T3-04.md`; T10-231 claims it retroactively at its own closeout.
- **gitlink hazard**: GitHub squash/rebase rewrites child-commit SHAs, so a parent gitlink pinned at the pre-merge child SHA becomes dangling; `bin/ssot/submodule-reachability-gate.py` only accepts ancestry from the submodule's `refs/remotes/origin/main`. Verified: `merge-base --is-ancestor 86c485c9 origin/main` exited **1** after the squash; re-pointed the root gitlink to `35f2ab77` (commit `bf2fbdac1`), after which root CI passed. New repo lesson: submodule PRs must plan for a parent gitlink re-point whenever the merge method rewrites the SHA.