# Governance — bus-foundation

> R75 update. Originally written R66. Updated after R73/R74/R75.

## Mission

bus-foundation is the shared event/transport layer for omostation. It
provides a unified pub/sub/cron/scheduling API across 8 backends. It
exists so omostation projects don't reinvent the wheel for "how do
I send an event from one place to another."

## What bus-foundation is NOT

- **NOT** a high-throughput message broker. For that, use Kafka/NATS
  (see `PersistentBusBackend` docstring).
- **NOT** a workflow engine. For that, use metaos (separate project).
- **NOT** a service mesh. For that, use agora's gateway (separate
  project; `agora.bus` keeps a premium `EventBusBackend` wrapper
  around `agora.core.event_bus`).
- **NOT** a phase-driven project. Per R72 decision, **Phase C is
  closed (Path C: Defer Indefinitely)**. All future work is normal
  feature work, no Phase D governance gate.

## Maintenance principles

1. **Zero `from agora` imports** in `src/bus_foundation/`. bus-foundation
   must remain a pure standalone package that can be consumed by
   any project, including those that don't use agora.
2. **Single file < 500 LOC**. We had a God Module scare in agora
   (`server/mcp.py` 1757 lines). Don't repeat that mistake here.
3. **No retry at backend**. RETRY-OWNERSHIP.md says: each event
   chain has exactly one layer that retries; bus-foundation backends
   are not that layer (router + DLQ are).
4. **Public API stable**. Breaking changes go through an ADR.
   Last ADR: ADR-0002 (R72) for the no-L0-promotion decision.
5. **TDD preferred**. New backends ship with tests. Bug fixes ship
   with regression tests.
6. **`match_pattern` is the only way to do pattern matching.** All
   backends delegate to it (R74 dedup).

## Review checklist (for PRs)

Before approving a PR, verify:

- [ ] No `from agora` imports in `src/bus_foundation/`
- [ ] No new `from typing` import of `Callable`/`Iterable`/`Iterator` etc. (use `collections.abc`)
- [ ] No `for attempt in range(3)` patterns (no retry at backend)
- [ ] If adding a new backend: 4+ tests, exported from
      `src/bus_foundation/backends/__init__.py`
- [ ] If changing public API: ADR filed
- [ ] Single file < 500 LOC
- [ ] `ruff check src/ tests/` returns 0 errors

## Release cadence

- **Major (x.0.0)**: never (frozen public API)
- **Minor (0.x.0)**: never (frozen public API, no breaking changes)
- **Patch (0.1.x)**: as needed for bug fixes
- **Pre-1.0.0**: any feature is a patch, not a minor

We are at 0.1.0 since R66 (2027-04-12). The 0.x.y line is the
frozen public API; we don't go to 1.0.0 unless there's a structural
change (which ADR-0002 explicitly says we don't plan).

## Dependencies

- **Runtime**: pydantic (≥2), Python 3.13+
- **Dev**: pytest, ruff
- **Optional**: none (no opt-in "premium" backends in bus-foundation;
  the premium backends stay in agora)

## When to update this file

Update GOVERNANCE.md when:
- A new ADR changes the maintenance principles
- A new backend changes the dependency story
- A decision is made about future direction (e.g., "Phase C
  re-opens", "0.x.y → 1.0.0", etc.)
- A maintenance principle is added or removed

Do NOT update GOVERNANCE.md for:
- Routine bug fixes (CHANGELOG.md is enough)
- New backends (CHANGELOG.md is enough)
- New tests (CHANGELOG.md is enough)

## Ownership

- **Primary owner**: 夏 (Xia Mingxing)
- **Maintainers**: see `OWNERS.md` for current list and decision protocol
- **Bus architect**: §"agora team" (per ADR-0008 §"Consequences")

## Decision log (governance-relevant only)

| Date | Decision | Source |
|------|----------|--------|
| 2027-04-12 | Initial release 0.1.0 | R66 close |
| 2027-09-12 | Phase C closed (Path C: Defer) | R72 retro |
| 2026-06-13 | 4/5 LOW fixes applied; 1 deferred (UP035) | R74 |
| 2026-06-13 | 5 backends delegate to `match_pattern` | R74 simplify |
| 2026-06-13 | ruff auto-fix; collections.abc enforced | R75 |
