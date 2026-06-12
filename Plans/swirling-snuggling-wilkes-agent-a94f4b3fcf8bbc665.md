# RED TEAM Attack Report: Unified Bus API Plan

> Target: Phase A (R57) 6-adapter wrapper + Phase B standalone split (R63+) + Phase C L0 protocol promotion (R70+)
> Grounded in: agora/event_bus.py, omo/omo_worker_dispatch.py, runtime/bus_consumer.py, agora/audit_subscriber.py, metaos/workflow.py, runtime/cron_service/scheduler.py, runtime/executor/message_bus.py
> Author: Red Team (16 attacks, 6 categories)

---

ATTACK 1 — The Retry Multiplication Bomb
Category: 6 (Technical Correctness)
Severity: CRITICAL
Scenario: agora EventBus already does 3x retry with 2^attempt backoff (event_bus.py:170-188). runtime/bus_consumer.py does its own 3x retry on top of that (bus_consumer.py:104-113). If the Unified Bus adapter preserves the underlying semantics of each transport, then for the omo:log_sync flow, a single failure now triggers 9 attempts (3 from EventBus HTTP callback + 3 from bus_consumer → gbrain + 3 implicit retries inside gbrain put). A flaky network produces exponential retry storm; a slow gbrain produces thundering herd against 127.0.0.1:7430.
Detection signal: 7430 endpoint latency > 5s; sqlite_bus_consumer.db retries column climbs to 3 within minutes of any network blip; omo worker dispatch stdout timeouts.
Mitigation candidate: Define a "retry ownership" rule — exactly one layer in the stack owns retries, others pass-through with no retry. Document this per transport.

---

ATTACK 2 — asyncio EventLoop + Threading Crash
Category: 6 (Technical Correctness)
Severity: CRITICAL
Scenario: runtime/cron_service/scheduler.py:245 uses `ThreadPoolExecutor(max_workers=4)` to run blocking scripts. metaos/workflow.py:217 wraps SEngine.process in `asyncio.to_thread`. agora/event_bus.py:145 does `asyncio.get_running_loop()` then `loop.create_task(self._deliver(event))` from a sync method. If a single unified Bus API is called from inside a cron thread (no running loop) the EventBus branch will silently drop delivery (event_bus.py:148-150). The unified adapter, by design, picks ONE delivery model — it cannot know the caller's context. We will either silently drop events OR break the loop, depending on implementation.
Detection signal: cron-fired events vanish from audit_log; zero delivery attempts logged in delivery task list; bug only manifests when called from non-async contexts.
Mitigation candidate: Make every adapter enforce a runtime check "is there a running loop? if not, schedule on default executor" — or refuse to call EventBus from sync contexts and require explicit "fire-and-forget" wrapper.

---

ATTACK 3 — Schema Versioning is Theatre Without Enforcement
Category: 6 (Technical Correctness)
Severity: HIGH
Scenario: The plan claims "schema versioning" as a Phase A deliverable. But the underlying producers (omo_worker_dispatch.py:264-303, bus_consumer.py, audit_subscriber.py) do not emit version fields, do not negotiate, and have no rejection logic. Worse, agora EventBus's JSON persistence (event_bus.py:124-131) writes a fixed schema: id/time/source/type/trace_id/payload. If you bolt a version envelope on top, every existing consumer (audit_subscriber, omo_sse_daemon, bus_consumer) parses the unversioned core. Schema versioning without protocol-level negotiation is documentation, not safety.
Detection signal: A v2 event is published; old consumer crashes on unknown payload field; v1 consumer silently ignores v2 enrichment. Bug reports filed as "intermittent consumer errors".
Mitigation candidate: Define a mandatory `schema_version` field at the wire level (not in the payload); ship a "schema registry" with a client-side rejector; fail closed during transition window.

---

ATTACK 4 — SSE Reconnect Storm Amplified by Adapter
Category: 6 (Technical Correctness)
Severity: HIGH
Scenario: bus_consumer.py:154 has a 5-second sleep on connection error (line 176, 179, 182). If agora restarts (Phase 27 saw restarts), 4 consumers (omo_sse_daemon, bus_consumer, metaos_workflow SSE, audit_subscriber) all reconnect at 5-second cadence. The Unified Bus SSE adapter "simplifying" the API will centralize this logic — but a single misconfigured backoff (e.g., 100ms instead of 5s) creates a hot-loop against agora. Centralized reconnect logic = centralized DoS amplifier.
Detection signal: agora CPU spikes to 100% during a single client crash; logs show thousands of GET /v1/events/stream per second; Open file descriptors exhausted.
Mitigation candidate: Enforce a minimum exponential backoff floor (e.g., 1s, 2s, 4s, 8s, capped at 60s) in the adapter itself, not configurable.

---

ATTACK 5 — SQLite DLQ as Hidden Single Point of Failure
Category: 6 (Technical Correctness)
Severity: HIGH
Scenario: bus_consumer.py:34-53 uses sqlite3 with default isolation, single connection, no WAL mode, no connection pool. At Phase 26 we observed >100 events/sec at peak. Under the unified DLQ, every adapter will write to the same SQLite file. WAL mode is not set, so concurrent INSERTs from cron adapter + sse adapter + tasksync adapter will block. With WAL: hundreds of writers, no pool, no tuning → "database is locked" errors cascade. Worse: the DLQ file lives in `~/.runtime/bus_consumer.db` (bus_consumer.py:19) — at `os.environ.get("HOME")` — meaning the DLQ is on the user's home volume, not even project-local, and is a single unbacked-up file.
Detection signal: sqlite3.OperationalError: database is locked in logs; events dropped silently after 3 retries; DLQ file grows unbounded with no GC.
Mitigation candidate: Switch to WAL mode + busy_timeout=5000; switch to a single-process DLQ writer (consumer-side); add DLQ file size cap + rotation.

---

ATTACK 6 — The 6-Adapter Abstraction Hides the Real Number
Category: 3 (8-Mechanism Assumption)
Severity: HIGH
Scenario: Plan claims 6 mechanisms. Code review shows the actual distinct mechanisms are MORE than 8: (1) asyncio direct call, (2) cron scheduler, (3) omo_daemon 30min loop, (4) omo_sse_daemon SSE, (5) MatrixScheduler 15s tick, (6) agora EventBus pubsub, (7) agora WSServer, (8) agora TaskSync SQLite, (9) agora audit_subscriber wildcard, (10) bus_consumer SSE→SQLite, (11) metaos Workflow DAG+SSE, (12) agora Pipeline, (13) MessageBus in-process, (14) Tri-Plane Bus HTTP push, (15) KEI sys.addaudithook. The "6 adapters" plan is already a 50%+ undercount. Wrapping 6 visible mechanisms while 9 invisible ones remain unwrapped creates a dual-tier system worse than what we have.
Detection signal: After Phase A ships, devs continue to use omo_daemon + audit_subscriber + TaskSync directly, citing "the unified bus doesn't cover this case". 6 new adapters solve 40% of the problem.
Mitigation candidate: Enumerate ALL async/event mechanisms via codebase grep + decision matrix BEFORE designing adapters. Probably need 12-15 adapters, not 6.

---

ATTACK 7 — The "5 Hard Conditions" Are Soft as Marshmallows
Category: 2 (Phase B Decision)
Severity: HIGH
Scenario: The 5 conditions for Phase B (3+ active users, 1+ external user, independent cadence, independent owner, 6+ months) are gamed from day one. "Active use" can be claimed by a single import statement. "External user" can be claimed by a single GitHub star. "Independent cadence" is satisfied if anyone — including the same engineer — cuts a release. "Independent owner" is satisfied by writing a new MAINTAINERS.md. "6+ months" can be backdated by an aggressive cut. Every condition is auditable, but audits happen AFTER the decision, not before. The conditions are not hard; they are advisory.
Detection signal: Phase B announced 8 months after Phase A with 2 of 5 conditions met; the 3 conditions claimed are all trivial. Decision goes unchallenged because no one wants to block.
Mitigation candidate: Make conditions quantitatively machine-checkable (e.g., "≥100 production calls/day for 30 consecutive days"); require external sign-off (not self-attestation) for "external user".

---

ATTACK 8 — "External User" Is a Fiction
Category: 2 (Phase B Decision)
Severity: MEDIUM
Scenario: The codebase is a single workspace with 9 sub-projects, all owned by the same team. There is no "external user" in any sense. The only way to satisfy "1+ external user" is to manufacture one (e.g., add a 10th project, OR release the package to a public registry, OR claim "we used it in a side project"). All three are definition gaming. Phase B should not be allowed to proceed on the basis of an artifactual external user.
Detection signal: At Phase B review, "external user" turns out to be the same author testing in a sandbox; or a fork that hasn't been touched in 9 months.
Mitigation candidate: Require "external user" = a GitHub issue filed by a non-contributor asking for help, OR a downstream commit referencing the package.

---

ATTACK 9 — 3 Weeks Is Fantasy Math
Category: 4 (Timeline)
Severity: HIGH
Scenario: Plan assumes 6 adapters × 50 lines + DLQ + schema + tests in 3 weeks for 1 senior + 1 mid-level. Realistic scope: 6 adapters × 200 lines (50 lines per adapter is fictional, real adapters need error handling, backoff, type coercion, schema validation) = 1200 lines; DLQ subsystem 400 lines (WAL mode, rotation, GC, query API); schema versioning 200 lines (negotiation, registry, validation); tests at 1.5x code = 2700 lines; integration tests across 4 projects = +500 lines; documentation = 300 lines. Total: ~4700 lines, not 300. At a realistic velocity of 200 lines/day (including tests, debug, review), that's 23 person-days, not 12. The 3-week estimate ignores ramp-up, code review latency, and the inevitable "Phase 0.5" (we need to refactor the underlying transport to be wrappable).
Detection signal: At end of week 2, only 2 of 6 adapters are merged; tests are stubbed; DLQ schema not finalized; "we need 2 more weeks" becomes the new baseline.
Mitigation candidate: Cut Phase A scope to 3 adapters (eventbus, messagebus, sse) + DLQ skeleton; defer the rest to Phase A.1.

---

ATTACK 10 — The "6 Months" Wait Is Unenforced
Category: 4 (Timeline)
  
Severity: MEDIUM
Scenario: Plan says "6+ months sustained use before Phase B". Who enforces? No one. The same team that wants the split will lobby for it after 4 months. The condition reads as advisory, not blocking. The pain might be acute at month 2 (a real agora bug is unfixable in 3 days instead of 3 hours), and the team will cite pain as reason to split immediately — defeating the "sustained" requirement.
Detection signal: Phase B proposal appears at month 4; "external user" condition reinterpreted generously; engineering leadership approves because they want the velocity win.
Mitigation candidate: Codify the 6-month wait as a technical blocker (e.g., git history check on the bus-foundation directory: must have ≥180 days of history) rather than a process rule.

---

ATTACK 11 — God Module Redux: The Unified API Becomes the New God
Category: 1 (Phase A)
Severity: CRITICAL
Scenario: This is the most dangerous attack. agora/server/mcp.py is already 1,757 lines and explicitly flagged as a God Module in the project's CLAUDE.md. Adding a "unified bus API" that wraps 6-15 mechanisms will, by definition, be the most-imported module in the entire system. It WILL become a god module. Every new feature will be added there. Every new transport will be added there. The "adapters" pattern promises to avoid this, but the interface contract alone will be 500+ lines; the dispatcher alone will be 300+; the DLQ integration alone will be 200+. By month 3, the bus/ subpackage is 2,500 lines and growing.
Detection signal: Bus API module LOC exceeds 1,000 within 8 weeks; bus/ subpackage is the top-imported module in every project; PRs touching bus/ require review from 3+ people.
Mitigation candidate: Apply the 1,000-line module rule at Phase A start, not as a debt item. Split interface/dispatcher/adapters into separate files from day 1.

---

ATTACK 12 — The Boundary Problem: "Process-internal" vs "Process-external"
Category: 1 (Phase A)
Severity: HIGH
Scenario: MessageBus (runtime/executor/message_bus.py:73-300) is process-internal, in-memory, with request/response correlation, FIFO history, and trace_id indexing. agora EventBus is process-external, JSON-persisted, fire-and-forget HTTP. These are FUNDAMENTALLY DIFFERENT transports with different semantics. An adapter that "unifies" them must either: (a) drop request/response correlation (breaking MessageBus users), (b) drop cross-process delivery (breaking EventBus users), or (c) implement both modes with a flag — defeating the purpose of unification. There is no clean abstraction here. The 50-line adapter estimate is impossible.
Detection signal: MessageBus users complain about missing reply correlation; EventBus users complain about dropped messages; the "unified" API has 2x the surface area of the underlying transports.
Mitigation candidate: Refuse to unify these two. Keep MessageBus as a separate interface; only unify the cross-process adapters (eventbus, cron, sse, ws, tasksync).

---

ATTACK 13 — Trace ID Propagation Will Be Silently Broken
Category: 1 (Phase A)
Severity: HIGH
Scenario: The 6 mechanisms each have different trace_id semantics. event_bus.py:128 has a `trace_id` field at the event envelope level. message_bus.py:43 has trace_id in AgentMessage. bus_consumer.py generates no trace_id. The unified API will need to define ONE trace_id model — but at least one of these mechanisms doesn't carry the field at the right level (e.g., cron jobs have no trace_id at all; their "trace" is the run_id). When the unified adapter is used, trace_id will either be invented (fake) or lost (silent). Cross-system debugging — already hard — will become impossible.
Detection signal: A workflow node's failure is unattributable; omo dispatch logs lack trace_id despite passing through the unified API; gbrain graph queries return disjointed subgraphs.
Mitigation candidate: Define a `TraceContext` object that propagates through ALL adapters, including cron (auto-generate from job_id + run_id).

---

ATTACK 14 — Team Resistance Will Sabotage Adoption
Category: 5 (Organizational)
Severity: MEDIUM
Scenario: Plan assumes omo/metaos/runtime teams will adopt the new API. But omo is the AUTHORITY on .omo/ — it sets patterns, not follows them. The bus_consumer.py:21 hardcodes AGORA_EVENTS_URL="http://127.0.0.1:7430/api/events" — a string constant. It would need to be rewritten to import from the unified bus. The omo team will see this as: "Why do I need to import 3 new modules to call agora? My urllib.request one-liner works fine." Similarly, metaos/workflow.py:256 hardcodes "http://127.0.0.1:8080/v1/events" — a different port (8080 vs 7430), suggesting the actual deployment has 2+ agora instances. The "unified API" doesn't unify the topology; it unifies the surface. Teams will resist.
Detection signal: After Phase A ships, <50% of producers migrate; omo continues to hardcode URLs; metaos ignores the unified bus; "adoption" is achieved by the agora team alone.
Mitigation candidate: Make migration a hard prerequisite for new features in omo/metaos; ship a deprecation timeline; reward migrations in the issue tracker.

---

ATTACK 15 — Schema Migrations Need a Backward-Compat Plan
Category: 6 (Technical Correctness)
Severity: HIGH
Scenario: Adding schema_version field to events means existing audit_subscriber (audit_subscriber.py:64-78) needs to handle v1 (no version field) and v2. Existing bus_consumer.py needs to handle both. Existing audit log SQLite DBs (agora-audit.db, bus_consumer.db) need migration. The "schema versioning" deliverable in Phase A is 5-10x the work the plan suggests, and it MUST be backward-compatible because we cannot stop 5 production daemons simultaneously.
Detection signal: Audit log starts missing events after deploy; bus_consumer.db rejects old events silently; deprecation warnings flood logs.
Mitigation candidate: Ship schema versioning as a separate phase (Phase A.0); require explicit version negotiation; do not "add version to events" without a written migration plan.

---

ATTACK 16 — The Phase C "L0 Protocol Promotion" Has No Enforcement
Category: 2 (Phase B Decision)
Severity: MEDIUM
Scenario: "De facto standard" is a claim, not a measurement. The team will claim de facto standard because the bus-foundation repo is the only one used internally. There is no external validation (no RFC, no IETF, no industry adoption). L0 protocol status in the eCOS architecture is a governance decision, not a popularity contest. By codifying "de facto standard" as the criterion, the plan is making a circular argument: we are the standard because we use it ourselves.
Detection signal: L0 protocol status granted; bus-foundation now in protocols/; but no actual external adoption; the "standard" is the team talking to itself.
Mitigation candidate: Replace "de facto standard" with measurable criteria: ≥2 distinct organizations use it, OR ≥1 industry conference talk, OR ≥1 academic citation.

---

SUMMARY — Triage

| Sev | Count | Attacks |
|-----|-------|---------|
| CRITICAL | 3 | #1, #2, #11 |
| HIGH | 9 | #3, #4, #5, #6, #7, #9, #12, #13, #15 |
| MEDIUM | 4 | #8, #10, #14, #16 |

TOP 3 RECOMMENDATIONS (P0 to act on before Phase A starts):
1. **Attack 11 first**: Enforce 1,000-line module rule at bus/ subpackage creation. Split interface/dispatcher/adapters into separate files. Refuse the god module.
2. **Attack 12 first**: Refuse to unify MessageBus and EventBus. Keep them as separate interfaces. The "unified bus" is a misnomer.
3. **Attack 6 first**: Enumerate ALL async/event mechanisms (likely 12-15, not 6) before writing a single adapter. A 50%-undercount is a fatal scope error.

The plan as written is shippable to a 1-month Phase A, NOT 3 weeks. Scope is at least 2x what is described. The "5 hard conditions" for Phase B are advisory, not enforced. The retry-multiplication bug (#1) and the God Module risk (#11) are the two issues most likely to cause production outages within 6 months of ship.

---

**Status**: Plan complete (16 attacks across 6 categories)
**Next**: User decides which attacks to mitigate pre-build vs accept as residual risk.
