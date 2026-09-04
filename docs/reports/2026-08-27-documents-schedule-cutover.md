---
type: ephemeral
created: 2026-09-03
---

# Documents schedule cutover evidence — 2026-08-27

This report records the attempted exact two-line host schedule cutover from
`BET-Y1Q3-T10-26`.

## Preflight and cutover result: PASS

- Backup: `.omo/evidence/20260827T150405Z-governance-state-mutation-d404236e/crontab-before.txt`
- Backup SHA-256: `8641487a179f0cd299bf532b7c4bfd9ae6e8a651d93623f18c93be44f936db3c`
- Old daily `25 6` line count: 1
- Old Monday `35 6` line count: 1
- Accepted-release consumer owner smoke: exit 1 with schema
  `documents.consumer-audit.v1`, 191 active consumers / 12 unmatched findings.
- Accepted-release freshness owner smoke: exit 1 with schema
  `documents.freshness-audit.v1`, 12 missing metadata findings.
- Both exits are truthful findings, not entrypoint/import failures.

The exact candidate was installed through `crontab -`. Post-install verification:

- old daily and Monday entries: 0 each;
- new Workspace owner entries: 1 each;
- unrelated crontab lines: 107, byte-identical;
- after SHA-256: `a070586211f8c525f1b7da0b4cc702e5ee6dad694c1182c6287f26c60f145f65`;
- no LaunchAgent or Documents content was changed;
- post-cutover consumer audit observes 189 active consumers, reflecting the two
  removed Documents cron consumers.

Rollback reference: restore
`.omo/evidence/20260827T152904Z-governance-state-mutation-dd693732/crontab-before.txt`
after verifying its SHA-256 above.

## 2026-08-28 accepted-release reconciliation

The host already contained the two Workspace owner lines from the earlier
cutover, but they still pointed to the older `accepted-20260827` release. This
run performed a second, exact two-line reconciliation to the clean
`accepted-20260908` release; no other crontab line changed.

- preflight backup: `/Users/xiamingxing/.local/state/omostation/t10-26-crontab-backups/20260828T143633Z/crontab-before.txt`
- before SHA-256: `2e78e757f48e778deab409b03018e2b66bd98a290658ca9fbc55964ef6da3196`
- after SHA-256: `778c9b007575e2ef376c887dffa6fcf2cc7e80ba02678ebb515c79a7dd0c9d67`
- changed lines: exactly the daily `06:25` and Monday `06:35` owner lines;
  unrelated lines were byte-identical
- post-cutover consumer smoke: exit `0`, 191 consumers, unmatched `0`,
  forbidden executors `0`
- post-cutover freshness smoke: exit `1`, 12 missing review metadata, no
  execution error
- legacy target processes: absent at observation time
- rollback: `crontab /Users/xiamingxing/.local/state/omostation/t10-26-crontab-backups/20260828T143633Z/crontab-before.txt`

The original 2026-08-27 pre-cutover backup referenced above is not present in
the current filesystem. This proves the current release-root update and
rollback, but does not retroactively prove the original Documents-to-Workspace
replacement receipt; that historical gap remains explicitly unproven.

## Remaining boundary

The shared Workspace checkout remains dirty and old, but the installed schedule
uses the versioned accepted release, so the two migrated jobs no longer execute
Documents code. The other seven active Documents execution families remain
unchanged and require separate parity waves.
