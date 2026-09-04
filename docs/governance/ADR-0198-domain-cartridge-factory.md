---
lifecycle: entry
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0198: Domain Cartridge Factory & Vertical Governance Packages

## Status
Accepted

## Context
Vertical domains (e.g. Healthcare Information Technology, Tech Transfer Commercialization) possess unique schema standards, Policy-as-Code constraints, and SOP workflows. Distributing and managing these assets ad-hoc creates fragmentation and drift across projects.

## Decision
1. Introduce `DomainCartridgeManager` in `ecos.ssot.compiler.domain_cartridge`.
2. Standardize Domain Cartridge format containing:
   - `manifest`: Metadata, Author, Domain identifier, Version.
   - `policies`: Domain-specific Policy-as-Code rules (`E-POL-WJ-*`, `E-POL-TF-*`).
   - `sops`: Operational standard Markdown templates.
3. Provide built-in official cartridges:
   - `cartridge-weijian-v1` (卫健委信息化全周期治理卡带)
   - `cartridge-transfer-v1` (国转中心科技成果转化合规卡带)
4. Expose via CLI `ecos-constraint cartridge list/export/validate` and FastMCP `runtime_cartridge_list`/`runtime_cartridge_inspect`.

## Consequences
- Enables modular, plug-and-play expansion into any vertical long-tail domain.
- Guarantees verifiable schema and rule compliance across domain boundaries.
