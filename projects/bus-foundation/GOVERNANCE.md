# bus-foundation Governance

> Release cadence, decision protocol, and how bus-foundation fits into the
> omostation 5+3+1 architecture.

## Relationship to omostation

bus-foundation is a **leaf package** — it has zero agora dependency and zero
intra-eCOS dependencies. It exists to give all omostation projects
(omo, metaos, runtime, aetherforge, kairon, llm-gateway, hermes-console,
cockpit, gbrain, ecos) a common event-bus vocabulary without taking on a
dependency on agora's I0 service mesh.

```
┌──────────────────────────────────────────────────────────┐
│  Consumer projects (omo, metaos, runtime, ...)           │
│  import from bus_foundation (zero agora dep)             │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  bus-foundation 0.1.0  (this package)                    │
│  5 backends + DLQ + Router + facade                     │
└──────────────────────┬───────────────────────────────────┘
                       │  (premium backends opt-in)
                       ▼
┌──────────────────────────────────────────────────────────┐
│  agora.bus.backends.*  (agora-specific)                  │
│  - Persistent EventBusBackend (agora-events.json)        │
│  - Global sse_manager SSEBackend                         │
└──────────────────────────────────────────────────────────┘
```

## Release cadence

| Frequency | Action |
|-----------|--------|
| Per-PR (CI) | All tests + ruff lint + format check must pass |
| Per-PR (CI) | `scripts/check-bus-hard-conditions.sh` (advisory) |
| Monthly | Re-evaluate 5 hard conditions; produce evidence in `.omo/_delivery/` |
| Quarterly | Minor version bump if there are 3+ merged features |
| Yearly | Major version review + deprecation of any 0.x APIs older than 18 months |

## Decision protocol

- **Patch (0.0.x)**: bug fixes, doc updates, no API surface change
  - 1 maintainer approval
  - Auto-mergeable
- **Minor (0.x.0)**: new backends, new helpers, deprecations
  - 2 maintainer approvals
  - 7-day comment window
- **Major (x.0.0)**: schema-breaking changes, removal of deprecated APIs
  - 2 maintainer approvals
  - ADR
  - 30-day deprecation window

See `OWNERS.md` for the current maintainer list.

## 5 hard conditions (re-evaluated monthly)

Per `docs/ADR-0008-bus-foundation-strategy.md`:

1. ≥3 projects use `from bus_foundation` (or `from agora.bus`) in production
2. bus-foundation has ≥180 days git history
3. bus-foundation CLAUDE.md documents owner
4. ≥1 eCOS-external project uses bus (GitHub issue/PR by non-contributor)
5. bus commit frequency ≥ 50% of agora main

Run `bash scripts/check-bus-hard-conditions.sh` from the bus-foundation
directory to re-evaluate.

## Release process

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` with the new section
3. Verify `uv run pytest -q` and `uv run ruff check src tests` pass
4. Commit with message: `chore: <version> release`
5. Tag locally: `git tag v<version> -m "<message>"`
6. (Push is manual — never auto-pushed)

## Compatibility promise

- `BusEnvelope` wire format (the JSON shape) is **frozen for 24 months** from
  0.1.0. Any change to a required field requires a major version bump and
  schema_version field bump on the wire.
- The Python `BusEnvelope` class is part of the public API and follows
  standard deprecation cycles (DeprecationWarning for 2 minor versions before
  removal).
