---
lifecycle: history
owner: governance-team
created: 2026-08-30
last_updated: 2026-08-30
title: T10-109 L4 machine-log classification delivery report
type: doc
---

# T10-109 L4 machine-log classification delivery report

## Outcome

The canonical L4 content-plane classifier now exposes mutable machine-generated
`.log` output as the existing `cache/L4-CONTENT-009` issue only in approved
operational contexts. Archive authority remains ahead of the new predicate,
arbitrary logs remain content, and regular-file and safe-symlink branches share
the same private helper.

This is a detection delivery. It performs no physical cleanup and does not make
Documents pure. The two retired runner logs remain in Documents for the
separate reversible T10-110 quarantine.

## Authoritative merges

- Accepted design/BET bootstrap: root PR #2767, merge
  `72fe0bf401ee4c7ebc1337893b5b8deb014a7258`.
- L4 implementation: child PR #11, merge
  `97a3b34b92744c0efee8a1fa8b8b7c4716646e39`.
- Root pointer and implementation plan: root PR #2768, merge
  `b267b2b65ab9b280702fe069c77241800036f986`.
- Root gitlink advanced from
  `d1a18dce0be4dacd3d99f535423a8e3c1e9985f5` to the exact child-main merge
  `97a3b34b92744c0efee8a1fa8b8b7c4716646e39`.

The child feature tree and child squash-main tree were both
`812d9afad598c94a6d361b8c3a5a7dacd058b4eb`. The root implementation branch and
root squash-main tree were both `73949a76277fed63fe3a21b75c11643be721c756`.
These equalities prove content equivalence in addition to merge ancestry.

## TDD evidence

Before production edits, three selected tests failed for the intended missing
behavior:

- an operational `_generated` log classified as `projection` instead of
  `cache`;
- an immediate `_inbox` runner-log symlink classified as `content` instead of
  `cache`;
- the CLI audit returned exit `0` instead of a cache violation.

Valid and invalid archive characterization tests passed before implementation.
The minimal production change added one path-only predicate and two calls after
archive resolution. The initial GREEN run exposed a test-fixture artifact:
L4's autouse fixture writes `l4_domain_paths.toml` at `tmp_path`. The CLI test
was corrected to audit a dedicated child root; its strict cache-only assertion
was not weakened.

## Verification

Fresh child and root-main verification included:

- focused content-plane and CLI tests;
- the complete L4 test suite;
- Ruff lint across `src/` and `tests/`;
- Ruff format for the changed production and CLI-test files;
- child Linux, macOS, lint, and domain-health CI;
- root doc SSOT, SSOT guardian, GaC, gitlink fast-forward/reachability, required
  PR checks, and root-main replay.

Two broad child test files already fail whole-file Ruff format on child main.
The baseline was replayed through stdin and returned nonzero for both files;
T10-109 did not reformat unrelated historical lines. Ruff lint remained green.
The full suite emits inherited deprecation/resource warnings but exits zero.

The root implementation PR completed with 22 successful checks, zero failures,
zero pending checks, and three conditionally skipped checks. Child PR #11
completed all four child checks successfully.

## Live read-only canary

The root-main implementation classified both actual paths as
`cache/L4-CONTENT-009`:

- `/Users/xiamingxing/Documents/_inbox/hourly_runner.log`
- `/Users/xiamingxing/Documents/_inbox/hourly_runner_err.log`

Both files were zero bytes. Before and after classification, the first retained
inode `230378223` and `mtime_ns=1786088763481467585`; the second retained inode
`230378225` and `mtime_ns=1786088763489466150`. Size, mtime, and inode equality
prove the canary did not replace, truncate, move, or write either path.

## Wider Documents boundary

A stable read-only full-tree snapshot taken during T10-108 still reported
73,211 violations: 36,855 cache, 31,448 invalid archive, and 4,907 runtime.
Most are registered family debt or archive-contract drift, not a reason to
weaken classification. T10-109 intentionally increases truthfulness by exposing
machine logs; it does not reduce that wider inventory.

The two runner logs are now visible to governance but remain physically present.
Large `family-dashboard-app`, learning external-tool, Zotero, career archive,
and other pending families remain outside this BET.

## Rollback

Code rollback is the child-main revert of PR #11 followed by a root gitlink
advance to that reverted child-main commit. No Documents or host rollback is
needed because T10-109 performed no external mutation. Do not reset the root
gitlink to an unreviewed or branch-only SHA.

## Verdict

- Engineering: `VERIFIED`.
- Operational classifier behavior: `PROVEN` by real read-only mainline replay.
- Physical runner-log cleanup: `NOT_PROVEN` and assigned to T10-110.
- Principal-bound user value: `NOT_PROVEN`.
- Documents-wide physical purity: `NOT_PROVEN`.
