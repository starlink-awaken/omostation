---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0194 — Scheme C 5c setfacl 细粒度设计（design-only）

- **Status**: ACCEPTED (design scope — **no host ACL mutation in this ADR**)
- **Date**: 2026-07-15
- **Owner**: governance-team

## Context

ADR-0189 L2 applies **chmod-only** (strip other-write / 0777). Multi-agent
hosts often need **named-user / named-group** grants (broker vs agents) that
chmod cannot express. Linux `setfacl` / macOS `chmod +a` differ.

## Decision (design freeze)

### D1 — Platform matrix

| Platform | Mechanism | Priority |
|----------|-----------|----------|
| Linux | POSIX ACL `setfacl -m u:…:rwx` | P0 when `OMO_OS_ACL=1` |
| macOS | `chmod +a "user allow …"` | P1 (optional; many agents use default umask) |
| Windows | out of scope | — |

### D2 — Subject → ACE (access control entry)

| Subject | Identity source | ACE on `.omo/state` `_control` |
|---------|-----------------|--------------------------------|
| omo broker | process owner of `omo` CLI / launchd label | `rwx` |
| agent-workflow / GaC | group `omo-writers` (operator-created) | `rwx` on `_delivery` only |
| everyone else | — | no write (`---`) |

`.omo/_truth/` remains **git-owned** — no runtime ACE grant for agents.

### D3 — Apply pipeline (future implement PR)

```
omo acl plan          # already: chmod plan (0189)
omo acl plan --acl    # NEW: emit setfacl/chmod+a script (dry-run text)
OMO_OS_ACL=1 omo acl apply --yes --acl   # NEW: execute ACE script
```

Constraints:

1. Still requires `OMO_OS_ACL=1` + `--yes`
2. `--acl` never runs without prior `plan --acl` review in ops runbooks
3. CI never enables `OMO_OS_ACL`
4. Missing `setfacl` binary → WARN + chmod-only fallback

### D4 — Profile extension (future)

`etc/omo-path-acl.yaml`:

```yaml
acl:
  enabled: false
  group: omo-writers
  entries:
    - path: .omo/state
      users: ["$BROKER_USER"]
      groups: []
      mask: rwx
    - path: .omo/_delivery
      groups: ["omo-writers"]
      mask: rwx
```

### D5 — Non-goals of this ADR

- No setfacl execution on merge
- No launchd user creation
- No recursive ACL on entire monorepo

## Acceptance for design

- Subjects + platform matrix + CLI flags documented
- Implement PR must cite this ADR and ship `plan --acl` before `apply --acl`

## References

- ADR-0186, ADR-0187, ADR-0189
- `docs/METAOS-ECOS-SCHEME-C.md` Phase 5c
