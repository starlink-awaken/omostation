# Changelog

## 3.0.0a1 — 2026-08-11

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
