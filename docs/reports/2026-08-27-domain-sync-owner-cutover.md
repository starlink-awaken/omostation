---
type: ephemeral
created: 2026-09-03
---

# Domain sync owner cutover evidence — 2026-08-27

## Result: PASS

- backup: `.omo/evidence/20260827T154707Z-governance-state-mutation-49292324/crontab-before.txt`
- backup SHA-256: `a070586211f8c525f1b7da0b4cc702e5ee6dad694c1182c6287f26c60f145f65`
- old `0 6 * * * ... domain-sync.py` count after cutover: 0;
- new accepted-release `documents-domain-index.py check` count: 1;
- unrelated lines: 108, byte-identical;
- after SHA-256: `d188e5a7946ab61979aaa6e86a51077ce04b31f86a1202fa1505850a8f1f41a3`;
- old `/usr/bin/python3` command exit: 1 (`dataclass(slots=True)` on Python 3.9);
- new `uv` accepted-release command exit: 0;
- Documents `DOMAIN-INDEX.md` was read only and not modified by the check;
- rollback: restore the verified backup after checking its SHA-256.

No other crontab entry, LaunchAgent, Scheduled skill, or Documents content was
changed.

## 2026-08-28 release-root reconciliation (T10-45)

The already-installed domain-index owner line was still running from
`accepted-20260827`. This reconciliation changed exactly that one active line
to clean `accepted-20260908`; it did not claim the original Documents
`domain-sync.py` migration as a new completion.

- preflight backup: `/Users/xiamingxing/.local/state/omostation/t10-45-crontab-backups/20260828T150659Z/crontab-before.txt`
- before SHA-256: `778c9b007575e2ef376c887dffa6fcf2cc7e80ba02678ebb515c79a7dd0c9d67`
- after SHA-256: `6d469c2429437a79a2add9db3df3248219365dff3f31094e2fdfd5084f08d7df`
- changed lines: exactly one `0 6` line; all unrelated crontab bytes were
  identical
- post-reconciliation `documents-domain-index.py check`: exit `0`
- legacy Documents domain-sync/domain-index process count at observation: `0`
- accepted release: `accepted-20260908`, root
  `c5187900d4ae77e16631c512571cdb82a35dcafb`
- rollback: `crontab /Users/xiamingxing/.local/state/omostation/t10-45-crontab-backups/20260828T150659Z/crontab-before.txt`

The older T10-28 cutover receipt remains a separate historical artifact and is
not replaced by this one-line release-root reconciliation.
