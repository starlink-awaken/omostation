---
schema_version: report/v1
lifecycle: history
type: implementation-evidence
owner: governance-team
created: 2026-08-28
last_updated: 2026-08-28
bet_id: BET-Y1Q3-T10-46
---

# Installed owner release-root convergence

## Scope

This run changed only the release-root token on active cron lines that already
invoke Workspace owner/preflight entrypoints. Cadence, command arguments,
redirections, Documents inputs, and all unrelated crontab bytes were preserved.
The change does not complete the semantic migration BETs T10-28 through T10-34.

## Inventory and mutation

The preflight inventory contained 14 active owner/preflight lines:

- lines 2, 69, 71, 73, 75, 77, 78, 79, 82, 84, 85, 87, 95, and 110;
- 3 already pointed to `accepted-20260908`;
- 11 were changed from their prior accepted release root to
  `accepted-20260908`.

Before SHA-256:
`6d469c2429437a79a2add9db3df3248219365dff3f31094e2fdfd5084f08d7df`

After SHA-256:
`b8ed0e984123cfd217d72162b038ba1b4af5622eb242354b216516529c73de56`

The before/after snapshots and inventory are retained at:
`/Users/xiamingxing/.local/state/omostation/t10-46-crontab-backups/20260828T152926Z/`.
The bytewise comparison reports exactly 11 changed lines and all unrelated
lines identical.

## Postflight

The clean target release is `accepted-20260908`, root
`c5187900d4ae77e16631c512571cdb82a35dcafb`.

| Owner/preflight | Exit | Result |
| --- | ---: | --- |
| consumer audit | 0 | 191 consumers, unmatched 0, forbidden executors 0 |
| freshness | 1 | 12 missing review metadata, no execution error |
| OCR | 1 | source missing, engine ready, no execution |
| bridge | 0 | ready |
| convergence | 1 | findings, no execution error |
| signals | 0 | ok |
| controller | 1 | findings, no execution error |
| daily health | 1 | findings, no execution error |
| KOS | 1 | findings, no execution error |

All direct script help checks passed. No legacy Documents executor process was
observed. Rollback is restoring the exact preflight crontab snapshot.

## Boundary

This proves release-root convergence for installed owner/preflight entries. It
does not prove personal value, semantic parity of each family, or completion of
the original Documents migration BETs.
