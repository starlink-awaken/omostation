# runtime

🌐 [简体中文](README.zh.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributing](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security](https://img.shields.io/badge/security-policy-blue.svg)](SECURITY.md)
[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-package%20manager-purple.svg)](https://docs.astral.sh/uv/)

    > L1 · 服务生命周期、调度、健康监控与 KEI 沙箱
    > Metadata SSOT: [`../../docs/project-registry.yaml`](../../docs/project-registry.yaml)

    ## What It Owns

    服务生命周期、调度、健康监控与 KEI 沙箱.

    ## Installation

```bash
# Clone the workspace recursively
git clone --recursive https://github.com/starlink-awaken/omostation.git
cd omostation/projects/runtime

# Install dependencies with uv
uv sync
```

Requires Python 3.13+ (see `pyproject.toml`).

## Quick Start

    ```bash
    uv sync
uv run pytest "tests/" -q
make fmt
make sync-state
    ```

## KEMS Production Gate

Run the read-only production preflight before enabling the KEMS production
lane. It emits metadata and counts only; it never prints private source text
or sends a dispatch request:

```bash
export BOS_REACHBRIDGE_ENDPOINT="https://<enterprise-endpoint>/dispatch"
export BOS_REACHBRIDGE_TOKEN="<secret-from-the-runtime-secret-store>"
export KEMS_EVALUATION_MANIFEST="/secure/kems/evaluation-manifest.json"
export KEMS_MODEL_ACCEPTANCE_REPORT="/secure/kems/model-acceptance.json"
export KEMS_OMO_TASK_ID="<approved-task-id>"
python scripts/kems_production_preflight.py --production
```

Generate the manifest-bound model report with the Kairon evaluator before the
preflight:

```bash
python projects/kairon/scripts/kems_evaluate_model_candidate.py \
  --input /secure/kems/redacted-forecast-cases.json \
  --evaluation-manifest "$KEMS_EVALUATION_MANIFEST" \
  --candidate-model-id "candidate-v1" \
  --output "$KEMS_MODEL_ACCEPTANCE_REPORT"
```

The command exits non-zero until the enterprise endpoint, token, adjudicated
redacted evaluation manifest, a `shadow_pass` candidate-model report bound to
that manifest's dataset identity and SHA-256, controlled source inventory, and
approved OMO task are all present. The model report must retain
`promotion=blocked_until_omo_approval`; this preflight never grants promotion.
Local Hermes is intentionally not accepted by `--production`.

After the enterprise gateway returns its safe dispatch result, record the
receipt without copying response content or credentials:

```bash
python scripts/kems_dispatch_receipt.py \
  --manifest /secure/kems/reachbridge-manifest.json \
  --response /secure/kems/dispatch-response.json \
  --output /secure/kems/receipts/dispatch.json \
  --production
```

The receipt stores only the run ID, dispatch ID, manifest SHA-256, document
count, transport, status, and timestamp. It rejects local Hermes receipts in
production mode and requires the gateway response to confirm both identity and
manifest integrity.

After the dispatch, close the production evidence bundle only when the same
run's preflight evidence, redacted manifest, and HTTP receipt agree on run ID,
document inventory, manifest SHA-256, dispatch ID, and accepted transport:

```bash
python scripts/kems_production_closeout.py \
  --preflight-evidence /secure/kems/production-preflight.json \
  --manifest /secure/kems/reachbridge-manifest.json \
  --receipt /secure/kems/receipts/dispatch.json \
  --output /secure/kems/receipts/production-closeout.json
```

The closeout emits only redacted metadata and exits non-zero when any gate is
missing, failed, mismatched, or backed by a non-HTTP receipt.

For the cross-team evidence contract and release responsibilities, see
[`docs/KEMS-PRODUCTION-HANDOFF.md`](docs/KEMS-PRODUCTION-HANDOFF.md).

    ## Key Surfaces

    - `src/runtime/matrix.py`
- `src/runtime/scheduler.py`
- `src/runtime/kei.py`
- `src/runtime/cron_service/`
- `src/runtime/mcp_server.py`

    ## Documentation

    - Developer guide: [`AGENTS.md`](AGENTS.md)
    - AI context loader: [`CLAUDE.md`](CLAUDE.md) when present
    - Workspace architecture: [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md)
    - Layer placement: [`../../LAYER-INDEX.md`](../../LAYER-INDEX.md)

    ## SSOT Rules

    Runtime facts, counts, ports, health, and generated inventories are intentionally not maintained here. Use the workspace registries and project source as the truth.
## Project Governance

- [Maintainers](MAINTAINERS.md)
- [Acknowledgments](ACKNOWLEDGMENTS.md)

- [Development](docs/DEVELOPMENT.md)
- [Release Process](RELEASE.md)

- [Governance](GOVERNANCE.md)
- [Support](SUPPORT.md)

- [Contributing](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Contributors](CONTRIBUTORS.md)
## Getting Help

- [FAQ](docs/FAQ.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [API / Usage Reference](docs/API.md)
- [Architecture Overview](docs/ARCHITECTURE.md)