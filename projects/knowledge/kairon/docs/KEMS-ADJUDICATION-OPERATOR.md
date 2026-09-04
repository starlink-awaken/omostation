---
title: KEMS-ADJUDICATION-OPERATOR
type: doc
---

# KEMS Adjudication Operator Runbook

This runbook describes the controlled path from a redacted source queue to a
release-ready evaluation manifest. It is intentionally limited to metadata and
labels. Source bodies, OCR text, tokens, and connector payloads must remain
outside the queue database and all evidence files.

## Roles

| Role | Allowed action |
| --- | --- |
| Annotator A/B | Claim one of two independent slots and submit one label set |
| Adjudicator | Resolve the two submitted label sets; must be independent |
| Release operator | Build the manifest, run model evaluation, and collect evidence |

The persistent store enforces the role boundaries. A label submission without a
claim, a third claim, a duplicate submission, or an adjudication by either
annotator fails closed.

## Queue Preparation

Sync the controlled source inventory into the persistent queue. The operation is
idempotent. A changed SHA-256 for an existing `source_ref` is rejected instead
of silently creating a new version.

```bash
KAIRON_ROOT="/path/to/kairon"
DB="$HOME/.kems/adjudication.sqlite"
PYTHONPATH="$KAIRON_ROOT/packages/kos/src" \
  uv run --project "$KAIRON_ROOT" python \
  "$KAIRON_ROOT/scripts/kems_sync_adjudication_queue.py" \
  --database "$DB" \
  --evidence-output "/path/to/evidence/kems-adjudication-queue.jsonl"
```

For the first low-risk Workflow Mesh sample stream, export the OMO-owned
`engineering-delivery-review-queue/v1` projection after human review and convert
only reviewed rows into a separate redacted queue. Pending machine submissions
and unreviewed rows are rejected or ignored; this step does not treat a receipt
or an `adopted` decision as a gold label.

```bash
PYTHONPATH="$KAIRON_ROOT/packages/kos/src" \
  uv run --project "$KAIRON_ROOT" python \
  "$KAIRON_ROOT/scripts/kems_sync_engineering_delivery_queue.py" \
  --input "/path/to/evidence/engineering-delivery-review-queue.json" \
  --database "$DB" \
  --evidence-output "/path/to/evidence/engineering-delivery-adjudication.jsonl" \
  --split shadow
```

This queue uses scenario `engineering-delivery-review-v1` and exposes only
stable WorkflowRun, receipt, scene-binding, lead-time and evidence-count hashes
through the redacted source reference. The queue is still pending until two
independent annotators submit the `delivery_quality`, `evidence_sufficiency`,
`workflow_alignment`, and `requires_follow_up` labels and an independent
adjudicator records the final decision.

## Persistence Health And Recovery

Before creating a manifest or running shadow evaluation, inspect every KEMS
SQLite store used by the run. The command reports integrity, foreign-key
violations, table counts, and file permissions only; it does not read source
content.

```bash
PYTHONPATH="$KAIRON_ROOT/packages/kos/src" \
  uv run --project "$KAIRON_ROOT" python \
  "$KAIRON_ROOT/scripts/kems_health_check.py" \
  --database adjudication="$DB" \
  --database ocr="$HOME/.kems/ocr.sqlite" \
  --database model_acceptance="$HOME/.kems/model-acceptance.sqlite"
```

Create a verified private backup before maintenance or migration:

```bash
PYTHONPATH="$KAIRON_ROOT/packages/kos/src" \
  uv run --project "$KAIRON_ROOT" python \
  "$KAIRON_ROOT/scripts/kems_backup.py" \
  --source "$DB" \
  --destination "/path/to/backup/adjudication.sqlite"
```

Restore only after stopping writers. Existing destinations are protected by
default; `--force` is required to replace one. Run the health check again after
restoration and stop if the result is not `healthy`. A restored queue does not
authorize a manifest, prediction, WorkflowRun mutation, or OMO dispatch.

Inspect the queue without opening source content:

```bash
PYTHONPATH="$KAIRON_ROOT/packages/kos/src" \
  uv run --project "$KAIRON_ROOT" python \
  "$KAIRON_ROOT/scripts/kems_adjudication_cli.py" \
  --database "$DB" list --status pending
```

## Two-Person Adjudication

The `labels-file` must be a JSON object matching the versioned scenario schema.
For `private-source-review-v1`, the required fields are:

```text
source_kind, document_type, actionability, priority,
has_deadline, has_owner, requires_omo_task
```

Do not add free-form notes or any key named `body`, `content`, `ocr_text`,
`raw_text`, or `text`. The store rejects those keys recursively.

```bash
CLI="$KAIRON_ROOT/scripts/kems_adjudication_cli.py"
VERSION="private-source-review-v1.0"

uv run --project "$KAIRON_ROOT" python "$CLI" --database "$DB" \
  claim --sample-id "$SAMPLE_ID" --annotator "$ANNOTATOR_A"
uv run --project "$KAIRON_ROOT" python "$CLI" --database "$DB" \
  annotate --sample-id "$SAMPLE_ID" --annotator "$ANNOTATOR_A" \
  --annotation-version "$VERSION" --labels-file "$LABELS_A_JSON"

uv run --project "$KAIRON_ROOT" python "$CLI" --database "$DB" \
  claim --sample-id "$SAMPLE_ID" --annotator "$ANNOTATOR_B"
uv run --project "$KAIRON_ROOT" python "$CLI" --database "$DB" \
  annotate --sample-id "$SAMPLE_ID" --annotator "$ANNOTATOR_B" \
  --annotation-version "$VERSION" --labels-file "$LABELS_B_JSON"

uv run --project "$KAIRON_ROOT" python "$CLI" --database "$DB" \
  adjudicate --sample-id "$SAMPLE_ID" --adjudicator "$ADJUDICATOR" \
  --annotation-version "$VERSION" --labels-file "$FINAL_LABELS_JSON"
```

A sample is eligible for the evaluation manifest only after its status is
`adjudicated`. Never use a fixture or a synthetic label to unblock this step.

## Evaluation Evidence

Build the manifest directly from the SQLite store. The command fails when there
are no adjudicated samples and writes a redaction-verified manifest containing
the dataset identity, sample count, source hashes, redacted references, labels,
and annotation version.

```bash
PYTHONPATH="$KAIRON_ROOT/packages/kos/src" \
  uv run --project "$KAIRON_ROOT" python \
  "$KAIRON_ROOT/scripts/kems_build_eval_manifest.py" \
  --database "$DB" --output "$KEMS_EVALUATION_MANIFEST" \
  --dataset-id kems-real --dataset-version "$KEMS_DATASET_VERSION"
```

The candidate model report must bind all of the following to that exact
manifest: `dataset_id`, `dataset_version`, `dataset_sample_count`, and
`evaluation_manifest_sha256`. A successful shadow report remains
`promotion=blocked_until_omo_approval`.

For the complete candidate-model path, use the unified command below. It runs
the redacted predictor, validates and hashes the manifest, records the report
in the acceptance store, and writes the canonical JSON consumed by Runtime
preflight. Re-running the same `run_id` is idempotent.

```bash
PYTHONPATH="$KAIRON_ROOT/packages/kos/src" \
  uv run --project "$KAIRON_ROOT" python \
  "$KAIRON_ROOT/scripts/kems_evaluate_and_record_model.py" \
  --input "$KEMS_REDACTED_CASES" \
  --evaluation-manifest "$KEMS_EVALUATION_MANIFEST" \
  --output "$KEMS_MODEL_ACCEPTANCE_REPORT" \
  --run-id "$KEMS_MODEL_RUN_ID" \
  --database "$HOME/.kems/model-acceptance.sqlite" \
  --candidate-model-id moving-average-v1 \
  --strategy moving-average --window 3
```

The command fails closed when the manifest is missing, empty, or not
`redaction_status=verified`. It never grants promotion; OMO approval remains a
separate required artifact.

## Release Gates

The operator must retain these artifacts together:

1. Queue evidence with source hashes and redacted references.
2. Evaluation manifest with `redaction_status=verified` and only adjudicated samples.
3. Candidate model acceptance report with `status=shadow_pass` and exact manifest binding.
4. OMO approval artifact with `approval_status=granted` and
   `approval_scope=task.promote_apply`.
5. Runtime production-preflight evidence and the HTTP dispatch receipt.

The production preflight is the only release decision point. Missing endpoint,
token, manifest, model acceptance, or approved OMO task must produce
`status=blocked` and no network dispatch. A local Hermes result is not a
production receipt.

## Incident Handling

- If source content appears in a labels file or evidence file, stop, quarantine
  the artifact, and do not copy it into the database.
- If a source hash changes, preserve the old queue record and create a reviewed
  source version through the controlled sync process; never edit the database by
  hand.
- If annotations conflict, use a new independent adjudicator. Do not overwrite
  either annotation.
- If any preflight check is blocked, retain the JSON evidence and stop the
  release sequence.
