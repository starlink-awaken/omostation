---
type: ssot
last-reviewed: 2026-08-26
owner: governance-team
---

# Cockpit API / Usage Reference

> Quick reference for using **Cockpit** programmatically and from the command line.

## Command Line

- `uv run python -m cockpit` — CLI
- `uv run python src/cockpit/dashboard_server.py` — dashboard

## Programmatic API

Import `cockpit.cli` or use the MCP server for programmatic access.

### Engineering-delivery shadow review

- `GET /api/workflow-mesh/engineering-delivery/review-queue` requires a configured API key with `read` or `engineering-review` scope.
- `POST /api/workflow-mesh/engineering-delivery/review` requires the explicit `engineering-review` scope; the generic `admin` scope is intentionally insufficient.
- The POST body accepts only `workflow_run_id`, `delivery_id`, `decision`, and `evidence_refs`. Cockpit derives the reviewer identity and review time; clients must not send `actor_ref` or `reviewed_at`.
- Configure a 32+ character `COCKPIT_ENGINEERING_REVIEW_SIGNING_KEY` with the same value in Cockpit and OMO. This signs the normalized workflow, candidate receipt, and review binding; it does not change the scene's `shadow` tier or its `value_indicator_policy=false` isolation.

Use `X-Api-Key` or `Authorization: Bearer` with a credential declared in `config/api_keys.yaml`; see `config/api_keys.yaml.example`.

```bash
curl -H "X-Api-Key: ${COCKPIT_REVIEW_API_KEY}" \
  "http://127.0.0.1:8090/api/workflow-mesh/engineering-delivery/review-queue"

curl -X POST -H "X-Api-Key: ${COCKPIT_REVIEW_API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"workflow_run_id":"<run-id>","delivery_id":"<receipt-id>","decision":"adopted","evidence_refs":["evidence://human-review/<id>"]}' \
  "http://127.0.0.1:8090/api/workflow-mesh/engineering-delivery/review"
```

## Configuration

- Stack: python
- Dependencies: see [`../pyproject.toml`](../pyproject.toml) (Python) or [`../package.json`](../package.json) (TypeScript).
- Environment variables and ports: see workspace `protocols/port-registry.yaml` and root `.env.example`.

## Tests

See [`../README.md`](../README.md) for the test command.
