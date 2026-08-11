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
