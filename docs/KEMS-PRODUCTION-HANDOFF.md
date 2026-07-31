# KEMS Production Handoff

This runbook is the handoff contract for moving KEMS from integration
pre-production to an approved production-equivalent dispatch. It does not
authorize production by itself. The machine gates remain fail-closed, and no
fixture, synthetic label, local Hermes result, or copied secret is acceptable
as production evidence.

## Evidence Bundle

Use a protected temporary directory such as `/secure/kems/`. The directory may
contain redacted metadata only:

```text
/secure/kems/
  evaluation-manifest.json
  model-acceptance.json
  reachbridge-manifest.json
  preflight/production-preflight.json
  receipts/dispatch.json
  receipts/production-closeout.json
```

The endpoint and token are injected by the credential manager at process
startup. They must not be written to this directory, a manifest, a receipt,
the OMO task, a log, or a screenshot.

## Current Checkpoint

As of 2026-08-01, the engineering path is integrated and fail-closed, but the
release bundle is not yet production-ready:

- The real redacted queue contains 5 samples in
  `/Users/xiamingxing/.kems/adjudication.sqlite`; all 5 are `pending`, with no
  independent annotations and no adjudication decision.
- Cockpit reads that persistent store successfully:
  `GET /api/kems/adjudication/queue?limit=100` returns HTTP 200 and `count=5`.
- Manifest creation is correctly blocked:
  `POST /api/kems/adjudication/manifest` returns HTTP 422 because no sample is
  adjudicated. Do not create a fixture manifest to bypass this gate.
- The latest production preflight evidence is
  `/Users/xiamingxing/Documents/@公共/_runtime/evidence/production-preflight-latest-20260801.json`.
  Source inventory passes with 5 sources; ReachBridge endpoint/token,
  evaluation manifest, model acceptance report, and approved OMO task are
  still missing.

The next executable sequence is: two named annotators independently claim and
submit all 5 records, a third named adjudicator resolves every conflict, the
manifest builder creates the immutable evaluation manifest, the evaluator
produces a manifest-bound shadow report, and only then do the credential
administrator and OMO approver supply the remaining production inputs. The
release reviewer reruns preflight before any dispatch. Until that sequence is
complete, the only valid state is `integration pre-production / blocked`.

## Ownership And Deliverables

| Owner | Must provide | Machine acceptance |
| --- | --- | --- |
| Source custodian | Frozen source inventory and redacted references | Preflight source inventory is non-empty and hashes are stable |
| Two business annotators plus adjudicator | Independently submitted labels and a conflict decision for every real sample | Every manifest sample is `adjudicated` and has `annotation_version` |
| Model evaluator | Manifest-bound shadow acceptance report | `shadow_pass`, threshold satisfied, `promotion=blocked_until_omo_approval` |
| OMO approver | Approved task and independent approval artifact | `approval_status=granted`, scope `task.promote_apply`, matching task ref |
| Credential administrator | Short-lived endpoint and token through the secret manager | HTTP endpoint, token, and non-local transport pass preflight |
| Release reviewer | HTTP dispatch receipt and closeout result | Same run, inventory, manifest SHA, dispatch ID, and accepted HTTP transport |

The release reviewer is the final evidence owner. No single upstream owner may
self-approve the complete bundle.

## Handoff Sequence

### 1. Freeze and redact

Freeze the source inventory and give annotators only `vault://redacted/`
references. The annotation input must contain metadata and labels, never raw
mail, SMS, OA, or OCR text. Reject any record containing keys such as `body`,
`content`, `text`, `raw_text`, or `ocr_text`.

### 2. Adjudicate the real samples

The two annotators claim separate seats and submit independently. A third
person adjudicates conflicts. The input to the manifest builder must contain,
for every sample:

```json
{
  "sample_id": "<stable-id>",
  "source_sha256": "<64 lowercase hex characters>",
  "source_ref": "vault://redacted/<opaque-ref>",
  "scenario_id": "<scenario>",
  "split": "test",
  "annotation_status": "adjudicated",
  "annotation_version": "<immutable-version>",
  "labels": {"<approved-field>": "<approved-value>"}
}
```

Build the manifest with the Kairon manifest builder and record its dataset ID,
version, sample count, and SHA-256 in the release ticket. The manifest builder
and preflight both reject raw-content fields.

```bash
python "<workspace>/projects/kairon/scripts/kems_build_eval_manifest.py" \
  --input "/secure/kems/adjudicated.jsonl" \
  --output "/secure/kems/evaluation-manifest.json" \
  --dataset-id "<dataset-id>" \
  --dataset-version "<dataset-version>"
```

### 3. Run shadow evaluation

Run the candidate predictor against the real, redacted manifest. The report
must bind `dataset_id`, `dataset_version`, `dataset_sample_count`, and
`evaluation_manifest_sha256`. A passing report remains promotion-blocked until
the OMO approval exists; a model report never grants approval on its own.

```bash
python "<workspace>/projects/kairon/scripts/kems_predict_candidate.py" \
  --input "/secure/kems/redacted-cases.json" \
  --output "/secure/kems/model-acceptance.json" \
  --candidate-model-id "<candidate-model-id>" \
  --strategy moving-average \
  --window 3 \
  --evaluation-manifest "/secure/kems/evaluation-manifest.json"
```

### 4. Approve the OMO task

Create the task through the normal OMO lifecycle:

```text
planned -> active -> approved
```

The task must reference an independent approval artifact with:

```yaml
approval_status: granted
approval_scope: task.promote_apply
refs:
  task_ref: .omo/tasks/<state>/<task-id>.yaml
```

The task state, worker, allowed write paths, approval reference, and evidence
references must remain auditable. Cockpit must not directly rewrite task state.

### 5. Inject credentials and run the sole preflight

The credential administrator injects values only in the process environment:

```bash
export BOS_REACHBRIDGE_ENDPOINT="https://<enterprise-endpoint>/dispatch"
export BOS_REACHBRIDGE_TOKEN="<short-lived-secret>"
export KEMS_EVALUATION_MANIFEST="/secure/kems/evaluation-manifest.json"
export KEMS_MODEL_ACCEPTANCE_REPORT="/secure/kems/model-acceptance.json"
export KEMS_OMO_TASK_ID="<approved-task-id>"

python scripts/kems_production_preflight.py \
  --docs-root "<controlled-docs-root>" \
  --evaluation-manifest "$KEMS_EVALUATION_MANIFEST" \
  --model-acceptance "$KEMS_MODEL_ACCEPTANCE_REPORT" \
  --omo-root "<workspace>/.omo" \
  --task-id "$KEMS_OMO_TASK_ID" \
  --evidence-output "/secure/kems/preflight/production-preflight.json" \
  --production
```

Proceed only when the result is `status=ready` and every check is true. Keep
the evidence file even when the result is `blocked`.

### 6. Dispatch once and close the bundle

Use only the governed runner or the ReachBridge wrapper with the production
preflight. Record the redacted HTTP response using
`kems_dispatch_receipt.py`, then bind the three final artifacts:

```bash
python scripts/kems_production_closeout.py \
  --preflight-evidence "/secure/kems/preflight/production-preflight.json" \
  --manifest "/secure/kems/reachbridge-manifest.json" \
  --receipt "/secure/kems/receipts/dispatch.json" \
  --output "/secure/kems/receipts/production-closeout.json"
```

Closeout must succeed before anyone enables production action permissions. It
recomputes the manifest digest and compares the preflight source inventory to
the dispatched manifest. It also requires the receipt to be HTTP and accepted.

## Stop Conditions

Stop and retain the evidence if any of the following occurs:

- a source or annotation record contains raw private content;
- either annotator did not submit independently, or adjudication is missing;
- the model report is not bound to the exact manifest;
- the OMO task or approval artifact is missing, mismatched, or ungranted;
- endpoint, token, or transport is missing or uses local Hermes;
- the receipt run ID, inventory, manifest SHA, dispatch ID, count, or status differs;
- preflight or closeout exits non-zero.

The only valid state after a stop is `integration pre-production / blocked`.

## Sign-Off Record

The release ticket must link, without embedding private content or secrets:

1. dataset ID/version and evaluation manifest SHA-256;
2. candidate model ID and model acceptance SHA-256;
3. OMO task ID, approval reference, and approval SHA-256;
4. preflight evidence path and SHA-256;
5. dispatch receipt and production closeout paths and SHA-256;
6. names or auditable identities of the two annotators, adjudicator, OMO approver, credential administrator, and release reviewer.

Only the release reviewer may mark the bundle ready for a separately approved
production action window.