# Submodule Health Report

> Generated: 2026-09-07
> BET: BET-Y1Q4-T10-129
> Total: 16 submodules

## Summary

| Metric | Value |
|--------|-------|
| Total submodules | 16 |
| All consistent | ✅ |
| Drifted pointers | 0 |
| Dirty working trees | 0 |
| Total remote branches | 52 |
| Total tags | 299 |

## Per-Submodule Detail

| Submodule | SHA (head 12) | Remote Branches | Tags | Status |
|-----------|---------------|-----------------|------|--------|
| projects/runtime | `2394f2fe7c1f` | 2 | 1 | ✅ healthy |
| projects/metaos | `c9a182fe1fa2` | 2 | 0 | ✅ healthy |
| projects/l4-kernel | `73dc2890cc3c` | 2 | 4 | ✅ healthy |
| projects/ecos | `f7492e3d9343` | 4 | 21 | ✅ healthy |
| projects/agora | `69fd27db4812` | 5 | 23 | ✅ healthy |
| projects/cockpit | `047306097e8b` | 6 | 40 | ✅ healthy |
| projects/family-hub | `66dc665a811e` | 2 | 28 | ✅ healthy |
| projects/model-driven | `578e90fe4558` | 2 | 0 | ✅ healthy |
| projects/knowledge/gbrain | `e92622701c54` | 3 | 0 | ✅ healthy |
| projects/omo | `7f3a44d795e7` | 5 | 78 | ✅ healthy |
| projects/aetherforge | `b9df96b75ef1` | 2 | 15 | ✅ healthy |
| projects/bus-foundation | `7f5e1922feb5` | 3 | 0 | ✅ healthy |
| projects/observability | `6b40fb4b7da7` | 2 | 0 | ✅ healthy |
| projects/omlxc | `a2fbbb2894a3` | 5 | 83 | ✅ healthy |
| projects/cockpit-ui | `4ea841781988` | 2 | 6 | ✅ healthy |
| projects/knowledge/kairon | `ba47f30c730d` | 6 | 0 | ✅ healthy |

## Recent Activity (top 3 commits per submodule)

### projects/runtime
- `2394f2fe` docs(README): add doc-ssot contract with dynamic data references
- `6d54066d` docs(registry): remove hardcoded test count, reference actual output
- `2ef40e5a` fix(doc-index): STRAT-P81 SSOT 补 last-reviewed

### projects/omo
- `7f3a44d7` fix(lint): correct contradictory path success message
- `da99b360` feat(T10-126): zero-lock readonly probe + WAL concurrency hardening
- `c6ee00f3` feat(resident): sema_crystallizer — correction-threshold crystallization

### projects/agora
- `69fd27db` feat(T6-21): BOS Documents read-only facade
- `ee7ddbf8` feat(tools_bos): voice.py — pluggable ASR + polish + 3-way sorting
- `f6882039` feat(tools_bos): mail.py — bos://inbox/mail/draft 3-tier reply

### projects/cockpit
- `04730609` merge: 485dd02 (fail-loud) into c7aad0b (helper) — 采用授权助手实现
- `c7aad0b3` fix(voice-memo): .mkdir() → omo_io.ensure_parent_dir 授权助手
- `485dd02d` fix(voice-memo): replace defensive .mkdir() with fail-loud existence check

### projects/ecos
- `f7492e3d` feat(mof): L4 hardening — id 契约修复 + schema 保留名 alias
- `884e2d1e` feat(hooks): pre-commit L4 projection bridge drift checks
- `76673af4` fix(mof-scan): VALID_STATUSES + L4 KO lifecycle states

## Tools

| Tool | Purpose | Usage |
|------|---------|-------|
| `check-submodule-consistency.py --fail-on-drift` | CI gate: detect pointer drift | `python3 bin/gac/check-submodule-consistency.py --fail-on-drift` |
| `branch-ttl-gate.py --submodules` | Scan stale branches across all repos | `python3 bin/gac/branch-ttl-gate.py --submodules --dry-run` |
| `docs/submodule-health.md` | This report | Regenerate via health report script |
