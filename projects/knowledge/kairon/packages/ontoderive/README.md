---
title: README
type: doc
---

# ontoderive

Ontology derivation package for the Kairon monorepo.

It contains the OntoDerive engines, CLI, MCP server, and pipeline steps used by higher-level knowledge workflows.

## Entry points

```bash
uv run ontoderive --help
uv run python -m ontoderive.mcp_server
```

The external mesh route remains `bos://analysis/ontoderive/derive` through Agora. Internal pipeline consumers import the package directly.

## Validation and evolution pipeline

`validation_steps.py` exposes four pipeline steps:

- `ValidateStep`: verifies one alignment report with `MetaValidateEngine`.
- `BatchValidateStep`: verifies batch items sequentially or with a bounded thread pool.
- `EvolveStep`: generates update suggestions with `MetaEvolveEngine`.
- `BatchEvolveStep`: generates suggestions for batch items sequentially or in parallel.

Batch items carry their own `status`, `result`, and `error`. Items without an alignment report remain `SKIPPED`; they must not be counted as completed. `BatchResult` preserves both the compatibility fields used by existing callers and the aggregate fields emitted by validation steps.

## OntoDerive MCP tools

The `ontoderive.mcp_server` exposes five FastMCP tools:

- `derive`: forward derivation (facts → inferences → conclusions).
- `trace`: follow the inference path of an entity id.
- `validate`: check whether a data set conforms to the OntoDerive type system.
- `list_entities`: enumerate the meta-types and sub-types known to the type system.
- `pipeline_status`: report which engine modules are importable and whether the optional LLM is configured.

The `ontoderive.toolforge.mcp_server` exposes three additional FastMCP tools for thinking-tool selection:

- `toolforge_match`: grouped matches across the six thinking-tool categories.
- `toolforge_select`: cross-category top-N tool list.
- `toolforge_guide`: render the OntoDerive inference guide markdown.

All eight tools are also registered with the Agora mesh via `bos://analysis/ontoderive/{derive,validate,explain,audit,fact-check,align}` and `bos://analysis/ontoderive/toolforge/{match,select,guide}`. The six `analysis/ontoderive/{derive,validate,explain,audit,fact-check,align}` URIs route to the same engine via two ingresses (CLI and POC), which is why each appears twice; `toolforge/{match,select,guide}` are new in this revision.

## Verification

Run the focused regression suite with a hard timeout from the Kairon root:

```bash
python3 -c 'import subprocess; subprocess.run(["uv", "run", "pytest", "packages/ontoderive/tests/test_validation_steps.py", "packages/ontoderive/tests/test_governance_steps.py", "packages/ontoderive/tests/test_toolforge_mcp.py", "-q", "--tb=short"], check=True, timeout=40)'
```

For broader adjacent coverage:

```bash
python3 -c 'import subprocess; subprocess.run(["uv", "run", "pytest", "packages/ontoderive/tests/test_mcp_server.py", "packages/ontoderive/tests/test_toolforge_mcp.py", "packages/ontoderive/tests/test_toolforge.py", "packages/ontoderive/tests/test_validation_steps.py", "packages/ontoderive/tests/test_governance_steps.py", "-q", "--tb=short"], check=True, timeout=45)'
```
