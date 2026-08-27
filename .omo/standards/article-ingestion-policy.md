---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Article ingestion policy

> Status: active
> Phase: 12

---

## Scope

Phase 12 allows only policy definition and five structured samples. Bulk ingestion, auto-summary at scale, and article knowledge graph expansion are Phase 14 work.

## Admission rules

- Source must be identified by title, URL or local ref, publisher, and retrieval date.
- Copyright and retention notes are required before storage.
- Quality score must be at least 70 for relevance, originality, and depth.
- Summaries must be paraphrased unless the source explicitly permits longer quotation.
- Samples must carry tags and a retention class.

## Required sample fields

| Field | Rule |
|-------|------|
| `id` | Stable sample id |
| `title` | Source title |
| `source_ref` | URL or local reference |
| `retrieved_at` | ISO date |
| `quality_score` | Integer 0-100 |
| `retention` | `reference`, `short_term`, or `discard` |
| `summary` | Short paraphrase |
| `tags` | Discovery tags |
