# Closeout — 2026-07-15 macOS host ACL apply

## Concurrent sessions (left alone)

| Session | PR | Note |
|---------|-----|------|
| `work/docs-update` | #380 OPEN | dirty local docs; do not clobber |
| `work/probe-seek-tail` | #382 OPEN | runtime probe seek; do not clobber |

## Host apply (ops)

```text
target: /Users/xiamingxing/Workspace
cmd: OMO_OS_ACL=1 omo-acl-ops-window.sh --apply --yes --acl
applied_ok: 6
applied_fail: 1 (group omo-writers missing UUID)
ACE: user:xiamingxing on .omo/state, _control, _delivery
```

## Landed

- ADR-0207 evidence
- runbook §6 updated with apply results

## Residual

Create `omo-writers` group when multi-user ACE is needed.
