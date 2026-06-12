# Owners — bus-foundation

This file lists the maintainers responsible for the bus-foundation package.
Per ADR-0008.1, the bus-foundation release cadence is owned by these
maintainers; they have final say on:
- Schema-breaking changes to `BusEnvelope` (must bump `schema_version`)
- Adding/removing backends
- DLQ schema migrations
- Release tags (0.x.y)

## Maintainers

- **夏 (Xia Mingxing)** — primary, original author of the bus unification plan
- **omostation bus-foundation team** — release sign-off (2-reviewer rule for major bumps)

## Decision protocol

- **Patch (0.0.x)**: 1 maintainer approval
- **Minor (0.x.0)**: 2 maintainer approvals + 7-day comment window
- **Major (x.0.0)**: 2 maintainer approvals + ADR + 30-day deprecation window

## Where to file issues

- Bug reports / feature requests: omostation main repo
  (`/Users/xiamingxing/Workspace/projects/omostation/.omo/_delivery/` or
  GitHub equivalent)
- Security issues: contact maintainers directly (do not file public)

## Release cadence

See `GOVERNANCE.md` for the bus-foundation release process and the
`scripts/check-bus-hard-conditions.sh` script for the 5 hard conditions
re-evaluation criteria (R66-R69, then monthly thereafter).
