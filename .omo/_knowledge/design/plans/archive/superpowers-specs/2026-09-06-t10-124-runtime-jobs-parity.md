---
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q4-T10-124
title: "Runtime Jobs Parity & Cadence"
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-06
date: 2026-09-06
---
# Runtime Jobs Parity & Cadence

## Problem
`documents_domain_jobs.py` lacks a validator branch for `runtime-learning` owner jobs.
The two learning jobs (`documents-learning-decay`, `documents-learning-orphans`) fall through
to the manifest validator which rejects their `evidence_relative_path` / `evidence_schema` fields.
The domain project check returns 10 errors on these 2 jobs.

## Scope

### 1. Schema validation fix (documents_domain_jobs.py)
- Add `_RUNTIME_LEARNING_FIELDS` constant defining accepted fields for `runtime-learning` jobs
- Add `_validate_runtime_learning_job()` function accepting `evidence_relative_path`, `evidence_schema`
- Add branch in `validate_runtime_jobs()`: when `owner == "runtime-learning"` → call new validator
- Ensure backward compatibility: existing manifest/facts/sanyi/model-freshness/controller branches unchanged

### 2. Automation cadence (7 manual jobs)
- Enumerate all 7 manual runtime_jobs from the project registry
- Generate a launchd plist template for each job with appropriate schedule
- Add `--dry-run` mode to preview scheduling without installing
- Add `--install` mode to write plists to ~/Library/LaunchAgents/
- Evidence output: structured JSON to each job's evidence_path

### 3. Test coverage
- Unit test: validate_runtime_learning_job accepts valid learning job dicts
- Unit test: validate_runtime_learning_job rejects invalid fields
- Unit test: domain project check passes with learning jobs

## Non-goals
- Modifying the actual runtime-learning daemon logic
- Adding an 8th runtime job
- Modifying the Documents physical directory

## Verification
- `uv run pytest tests/test_documents_domain_project_check.py -q` → exit 0
- `uv run --with pyyaml python bin/gac/documents-domain-project-check.py --domain-registry /Users/xiamingxing/Documents/@公共/_control/L4-DOMAIN-REGISTRY.yaml --project-registry .omo/_truth/registry/documents-domain-projects.yaml --json` → ok=true
- `make gac-local-gate` → exit 0
