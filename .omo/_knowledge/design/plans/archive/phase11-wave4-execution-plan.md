# Phase 11 Wave 4 execution plan: Deep hardening + evolution alignment

> Packet: P11-W4-EVOLUTION-BRIDGE
> Status: completed
> Entry gate: Wave 3 closeout GO (user MVP demo passed + identity structured)

---

## 1. Goal

Production readiness start (v0.2 roadmap), deep hardening (Hermes/Minerva/KOS), and Phase 12 planning alignment.

---

## 2. Scope & deliverables

### G11.4.1 — v0.2 production readiness (INSIGHTS-AND-ROADMAP)

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T4.1 | Eliminate absolute path usage — all paths read from config/env | Path resolution module | `grep -r "/Users/" projects/` returns 0 meaningful hits |
| T4.2 | pip install verification — `pip install kairon` works | kairon pip package | `pip install kairon && python -c "import kairon"` works |
| T4.3 | KOS indexer hardening — ruff ≤200 + indexing stability | KOS indexer fix | `ruff check packages/kos/` ≤ 200 + indexer passes stress test |
| T4.4 | MCP FastMCP migration — agora/ontoderive/minerva adapters migrate to FastMCP | FastMCP adapters | All MCP tools run via FastMCP |

### G11.4.2 — Deep hardening

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T4.5 | Hermes broken link cleanup — fix or archive 179 broken links | Hermes audit report | Broken links ≤ 10 |
| T4.6 | Minerva temp file management — 109MB temp files automated cleanup | Temp file management script | Auto-cleanup cron/trigger deployed |
| T4.7 | KOS storage format calibration — align format with MetaType | KOS format ADR | KOS format documented + tests pass |
| T4.8 | Cross-repo governance enforcement — D4 standard execution | Governance check CI step | Cross-repo standards enforced in CI |

### G11.4.3 — Long-term evolution alignment

| # | Task | Deliverable | Verification |
|---|------|-------------|-------------|
| T4.9 | v0.3 interface contracting plan — `eidos/protocols/` module design | Protocol design ADR | ADR approved |
| T4.10 | Cross-project API contract pilot — 1-2 contract definitions + validation | Contract specs + validator | Contracts validate against implementations |
| T4.11 | Phase 12/13 pre-planning gate drafts — Phase 12 production-runtime gate plus Phase 13 metacognition boundary | `phase12-planning-gate.md` + `phase13-metacognition-preplanning.md` drafts | Drafts reviewed |

---

## 3. Exit gate checklist

- [ ] No absolute paths in production code
- [ ] `pip install kairon` works
- [ ] KOS ruff ≤200
- [ ] MCP tools running on FastMCP
- [ ] Hermes broken links ≤10
- [ ] Minerva temp file auto-cleanup active
- [ ] KOS storage format calibrated
- [ ] Cross-repo governance in CI
- [ ] v0.3 protocol design ADR
- [ ] API contract pilot with ≥1 validated contract
- [ ] Phase 12 planning gate draft registered in `plans/phase12-planning-gate.md`
- [ ] Phase 13 metacognition pre-planning boundary registered in `plans/phase13-metacognition-preplanning.md`
- [ ] Wave 4 closeout recorded in `summaries/phase11-wave4-closeout.md`
- [ ] Phase 11 retrospective recorded in `summaries/phase11-retrospective.md`
- [ ] system.yaml updated: `current_phase: 11, phase_status: completed`

---

## 4. Task mapping

```
P11-W4-EVOLUTION-BRIDGE:
  tasks:
    - T4.1 — Absolute path elimination
    - T4.2 — pip install verification
    - T4.3 — KOS indexer hardening
    - T4.4 — FastMCP migration
    - T4.5 — Hermes broken link cleanup
    - T4.6 — Minerva temp file management
    - T4.7 — KOS format calibration
    - T4.8 — Cross-repo governance CI
    - T4.9 — v0.3 protocol plan
    - T4.10 — API contract pilot
    - T4.11 — Phase 12/13 pre-planning gates
```

---

## 5. Progress snapshot

Current execution state after the first hardening tranche:

| Task | Status | Current judgment |
|---|---|---|
| T4.1 | completed | `rg -n '/Users/' projects --glob '**/*.{py,ts,tsx,js,jsx,go,java,sh}'` now returns no production-code matches |
| T4.2 | completed | Trusted publishing workflow shipped in `starlink-awaken/kairon`; TestPyPI publish succeeded, PyPI publish succeeded, and `pip install kairon==0.1.0 && python -c "import kairon"` is verified in clean environments |
| T4.3 | completed | Current KOS ruff debt is `78`, which satisfies the `<=200` threshold; indexer tests are green |
| T4.4 | completed | Agora, Minerva, and OntoDerive active MCP surfaces now run through FastMCP-backed implementations |
| T4.5 | completed | Current workspace-local Hermes bridge has `0` broken symlinks; historical 179-link debt is no longer live on the active surface |
| T4.6 | completed | Minerva now has both ephemeral `parse_to_text()` cleanup and an explicit `maintenance --action cleanup-temp` trigger for stale MinerU outputs |
| T4.7 | completed | KOS now has a centralized canonical MetaType registry/inference path; ingest + CLI are aligned |
| T4.8 | completed | Governance CI now enforces consistency/validation/tests as blocking checks |
| T4.9 | completed | `eidos.protocols` now carries an explicit serialized contract surface and v0.3 module direction |
| T4.10 | completed | First cross-package contract pilot landed: Eidos contract registry/validator + KOS consumer preflight |
| T4.11 | completed | Phase 12 and Phase 13 gate drafts already exist as current pre-planning artifacts |
