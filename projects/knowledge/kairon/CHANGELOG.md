---
title: CHANGELOG
type: doc
---

# Changelog

## Unreleased

### OntoDerive

- Restored the validation and evolution engines required by the pipeline after cleanup removed their modules.
- Expanded batch item and result models to match validation-step consumers while preserving compatibility fields.
- Preserved `SKIPPED` for items without alignment reports instead of overwriting it with `COMPLETED`.
- Added focused validation and adjacent governance regression coverage, with documented hard-timeout commands to prevent test-runner hangs from blocking delivery.

## [0.1.0] - 2026-06-04

### Governance & Tooling
- ruff lint: 627 → 0 errors across 25 packages
- LLM abstraction: unified 4 implementations into llm-gateway
- CI: extended to full package test suite
- Agora: restructured 110 root files into core/auth/mcp/extensions
- Eidos/engine-core/agent-runtime: root file restructuring
- 14/14 architecture debts resolved

### Documentation
- README.md for all 25 packages
- CLAUDE.md + AGENTS.md for AI agent documentation
- API reference documentation generated
- ADR directory established (ADR-001, ADR-002)
- Architecture audit and governance plan updated

### Packages
- agora: MCP gateway, service registry, circuit breaker
- eidos: schema validation, memory management
- kos: knowledge search, ontology engine
- minerva: deep research pipeline, LLM integration
- cron-service: task scheduling
- core-models: data models (dependency root)
- shared-lib: shared utilities (120+ modules)
- llm-gateway: unified LLM provider abstraction
- agent-runtime: agent execution engine
- forge: tool registry, digital asset management
- codeanalyze: code analysis, AST parsing
- ontoderive: ontology derivation engine
- sophia: symbolic paradigm engine
- iris: external connector hub
- kronos: knowledge ingestion pipeline
