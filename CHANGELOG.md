# Changelog

## 3.0.14 — 2026-08-14

- Documented backend adapter capability gaps (vision/embedding/rerank) across oMLX App, LM Studio, and Ollama in README, preserving the "read-only diagnostic" and "fail-closed" architectural boundaries without modifying existing single-node probes or introducing automatic remediation risks.

## 3.0.13 — 2026-08-14

- Added `omlxc nodes diagnose <node-id>` and its private read-only daemon API.
  It reports stable aggregate catalog outcomes without refreshing hardware or
  exposing node addresses, identities, or backend error text.

## 3.0.12 — 2026-08-14

- Added `omlxc nodes probe <node-id>` for an explicit, node-scoped catalog
  refresh. It refreshes only that node's configured backends and never starts
  inference or model lifecycle work.

## 3.0.11 — 2026-08-14

- Accept bounded composite OpenAI-compatible function descriptions up to
  128 KiB, so standard local coding-agent tool catalogs can reach routing while
  the existing 1 MiB request-body and 256-tool limits remain enforced.

## 3.0.10 — 2026-08-13

- Added the bounded `omlxc resolve` alias-inspection command and completed the
  current CLI/TUI readability improvements without changing model routing,
  node authorization, or daemon lifecycle behavior.

## 3.0.9 — 2026-08-13

- Accept bounded OpenAI-compatible function descriptions up to 16 KiB, covering
  current local coding-agent tool catalogs while retaining the 1 MiB request
  body and 256-tool limits.

## 3.0.8 — 2026-08-13

- Accept bounded OpenAI function-tool catalogs from local coding agents that
  expose more than 128 tools, while retaining a 256-tool request limit, strict
  tool schema validation, and the 1 MiB total request-body limit.

## 3.0.7 — 2026-08-13

- Accept the current Pi/oh-my-pi OpenAI Chat Completions request shape,
  including `max_completion_tokens`, bounded strict tool definitions,
  `parallel_tool_calls`, and the optional non-persistence hint.
- Preserve the existing internal generation budget, tool bounds, and
  fail-closed routing behavior while adding this wire compatibility.

## 3.0.6 — 2026-08-13

- Preserve the legacy 32K input context contract during JSON migration instead
  of confusing per-model output `max_tokens` with a placement context limit.
- Honor explicit legacy context-window fields when present while retaining
  `max_tokens` solely as a model generation parameter.

## 3.0.5 — 2026-08-13

- Added bounded OpenAI function-tool definitions, tool selection, assistant
  tool calls, tool-result messages, and streaming tool-call deltas across the
  private daemon and all three backend adapters.
- Raised only the chat aggregate text budget for real coding-agent system
  prompts while retaining the global 1 MiB request-body limit and routing by
  an estimated context-token budget.

## 3.0.4 — 2026-08-13

- Emit a terminal OpenAI-compatible SSE choice with a non-empty
  `finish_reason` before the unique `[DONE]` sentinel so strict local agent
  clients can complete streamed sessions deterministically.
- Preserve terminal reasons such as `length` when backends send them in an
  empty delta frame before usage and `[DONE]`.

## 3.0.3 — 2026-08-13

- Added deterministic human status summaries, safe actionable typed errors, and
  a bounded read-only guide workflow while explicitly preserving JSON/NDJSON and
  risk-gate contracts.

## 3.0.2 — 2026-08-12

- Persist accepted terminal request metrics on a bounded daemon-owned interval while
  preserving the existing shielded final flush on shutdown.
- Keep transient metric flush failures fail-safe and visible without stopping inference.

## 3.0.1 — 2026-08-12

- Increased the bounded daemon startup budget to accommodate a normal five-second
  production discovery pass while retaining timeout cleanup for hung lifespans.

## 3.0.0 — 2026-08-12

- Added the private, installable Python package skeleton.
- Added `omlxc` and explicit `omlxcd` placeholder console scripts.
- Preserved the 32-test `bin/omlx` legacy characterization baseline.
- Added strict, immutable domain models, fail-closed state transitions, the
  backend adapter protocol, and stable structured error/exit-code mapping.
- Added TOML configuration schema v1 with deterministic precedence and
  Keychain-reference-only credentials.
- Added dry-run legacy JSON migration plus confirmed `0600` atomic writes,
  private snapshots, and failure recovery.
- Added a reusable typed backend-adapter contract and the asynchronous oMLX App
  adapter for capability/readiness discovery, model lifecycle and tuning, chat,
  vision, embeddings, replay-safe SSE streaming, and recursive redaction.
- Added the LM Studio / LM Link adapter: direct OpenAI-compatible HTTP inference,
  three-state inventory merged with `lms ps --json`, and hardened argv-only SSH
  lifecycle control for macOS and Windows with strict known-host verification.
- Added the native Ollama HTTP adapter with strict version and model identity
  discovery, three-state residency, bounded `keep_alive` lifecycle control,
  thinking-safe chat and vision, current batch embeddings, and replay-safe
  incremental NDJSON streaming.
- Added fail-closed Tailscale identity discovery and pure HTTP/SSH endpoint
  authorization backed by an explicit strong-identity allowlist, plus a shared
  bounded subprocess primitive used by both Tailscale and LM Studio control.
- Added the Task 5 runtime foundation: a private, versioned, single-writer
  SQLite store with durable Job/event recovery and idempotent metric retention;
  independent bounded AnyIO event subscriptions; fail-closed health freshness,
  transport circuits and adaptive probe timing; and policy-driven placement
  reconciliation with memory admission, keyed single-flight and explicit loop
  lifecycle management.
- Hardened the Task 5 runtime with cancellation-safe metric draining and writer
  shutdown, atomic Job cancellation, verified v1 schema invariants, typed route
  audit/config revision repositories, conflict-safe durable events, bounded
  placement-operation phases, and shared explicit/reconcile coordination.
- Strengthened Task 5 recovery invariants with full SQLite column/index/foreign-key
  and constraint validation, canonical persisted UTC/JSON checks, content-free read
  conversion failures, complete Job cancellation semantics, cancellation-shielded
  circuit leases, safe reconciliation error reporting, verified config fingerprints,
  and explicit async-context ownership for SQLite task cleanup.
- Added the Task 6 local inference data plane: deterministic local-only placement
  filtering/scoring for four route profiles, hierarchical bounded concurrency,
  Task 5 single-flight load verification, backend-model translation, deadline-aware
  chat/vision/embedding/rerank execution, replay-safe streaming failover, and
  content-free route audit and metric persistence.
- Added the Task 7 private daemon surface: versioned control envelopes and durable
  Job endpoints, OpenAI-compatible chat/SSE/embedding plus rerank, replay-to-live
  NDJSON events, a restart-safe `0600` Unix socket server, ordered runtime lifecycle,
  and pure private launchd plist planning with atomic snapshots.
- Wired `omlxcd` to the production Task 5/6 runtime with durable restart recovery,
  bounded request bodies and shutdown, and typed fail-closed stream errors.
- Added bounded, failure-isolated backend discovery that refreshes production
  placement readiness while retaining fail-closed local security authorization.
- Added the Task 8 typed UDS client with strict envelope/request identity and
  bounded incremental NDJSON decoding; completed the Typer command tree with
  versioned JSON/NDJSON, stable exits, TTY-aware behavior, and R1/R2 gates; and
  added the eight-page Textual compute cockpit with keyboard navigation, confirmed
  mutations, incremental events, explicit STALE recovery, and narrow-screen mode.
- Wired the macOS user LaunchAgent lifecycle into the CLI with bounded argv-only
  `launchctl`, R2 confirmation, rollback-safe install, recoverable uninstall, and
  stable typed failures; added a no-write `doctor --direct` path.
- Added schema-v1 Tailscale executable/TTL and strong per-node allowlists, automatic
  production adapter construction with authorization-before-discovery, and LM
  Studio remote-control factory wiring. Windows subprocess output now decodes
  bounded UTF-8/UTF-16 and rejects CLIXML or invalid bytes without leaking them.
- Made daemon, CLI socket discovery, and direct diagnostics load the platform
  default configuration file when it exists.
