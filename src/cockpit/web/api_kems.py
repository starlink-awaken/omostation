"""KEMS workbench API: read-only status and evidence-bound OMO task drafts."""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from cockpit.web.api_tasks_data import WORKSPACE_DIR

router = APIRouter()

_RISK_TO_LEVEL = {"low": "L0", "medium": "L1", "high": "L2"}
_PRIVATE_FIELDS = {"body", "content", "ocr_text", "raw_text", "text"}


def _ocr_symbols():
    try:
        from kos.kems import OCRPageQuality, OCRQualityStore, assess_ocr_quality
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="KOS OCR quality store is unavailable") from exc
    return OCRPageQuality, OCRQualityStore, assess_ocr_quality


def _ocr_store():
    _, store_type, _ = _ocr_symbols()
    path = Path(os.environ.get("KEMS_OCR_DB", str(Path.home() / ".kems" / "ocr-quality.sqlite")))
    return store_type(path)


def _graph_store():
    try:
        from kos.kems import GraphStore
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="KOS graph store is unavailable") from exc
    path = Path(os.environ.get("KEMS_GRAPH_DB", str(Path.home() / ".kems" / "graph.sqlite")))
    return GraphStore(path)


def _forecast_symbols():
    try:
        from kos.kems import (
            ForecastStore,
            build_moving_average_shadow_forecast,
            evaluate_shadow_forecast,
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="KOS forecast store is unavailable") from exc
    path = Path(os.environ.get("KEMS_FORECAST_DB", str(Path.home() / ".kems" / "forecast.sqlite")))
    return ForecastStore(path), build_moving_average_shadow_forecast, evaluate_shadow_forecast


def _evaluation_symbols():
    try:
        from kos.kems import EvaluationManifest, EvaluationSample, EvaluationStore, evaluate_field_mapping
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="KOS evaluation store is unavailable") from exc
    path = Path(os.environ.get("KEMS_EVALUATION_DB", str(Path.home() / ".kems" / "evaluation.sqlite")))
    return EvaluationManifest, EvaluationSample, EvaluationStore(path), evaluate_field_mapping


def _adjudication_store():
    try:
        from kos.kems import AdjudicationStore
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="KOS adjudication store is unavailable") from exc
    path = Path(os.environ.get("KEMS_ADJUDICATION_DB", str(Path.home() / ".kems" / "adjudication.sqlite")))
    return AdjudicationStore(path)


def _model_acceptance_symbols():
    try:
        from kos.kems import ModelAcceptanceStore, ModelInputError, evaluate_candidate
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="KOS model acceptance store is unavailable") from exc
    path = Path(os.environ.get("KEMS_MODEL_ACCEPTANCE_DB", str(Path.home() / ".kems" / "model-acceptance.sqlite")))
    return ModelAcceptanceStore(path), ModelInputError, evaluate_candidate


def _reject_private_fields(value: object) -> None:
    if isinstance(value, dict):
        leaked = _PRIVATE_FIELDS.intersection(value)
        if leaked:
            raise HTTPException(status_code=422, detail="raw OCR content is not accepted by the KEMS API")
        for child in value.values():
            _reject_private_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private_fields(child)


@router.get("/api/kems/status")
async def kems_status() -> dict[str, Any]:
    """Expose capabilities without reading or returning private source content."""
    return {
        "status": "ready",
        "mode": "review_only",
        "capabilities": ["ocr_review", "graph_review", "evaluation", "model_acceptance", "omo_task_draft"],
        "dispatch": "omo_only",
    }


@router.post("/api/kems/tasks/draft")
async def create_kems_task_draft(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="KEMS task draft must be an object")

    required = ("task_id", "source_run_id", "title", "owner", "due_at", "evidence_refs", "acceptance_criteria")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing KEMS fields: {', '.join(missing)}")
    evidence_refs = body["evidence_refs"]
    if not isinstance(evidence_refs, list) or not all(isinstance(item, str) and item.strip() for item in evidence_refs):
        raise HTTPException(status_code=422, detail="evidence_refs must be a non-empty string list")

    risk = str(body.get("risk_level") or "medium")
    if risk not in _RISK_TO_LEVEL:
        raise HTTPException(status_code=422, detail="risk_level must be low, medium, or high")
    task_id = str(body["task_id"])
    source_run_id = str(body["source_run_id"])
    payload = {
        "id": task_id,
        "title": str(body["title"]),
        "description": str(body["acceptance_criteria"]),
        "status": "candidate",
        "task_type": "kems_evidence_action",
        "risk_level": _RISK_TO_LEVEL[risk],
        "allowed_operation_level": _RISK_TO_LEVEL[risk],
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": list(body.get("graph_refs") or []),
        "handoff_refs": [],
        "source_docs": evidence_refs,
        "entry_gate": ["evidence_bound", "human_review_required"],
        "evidence_required": evidence_refs,
        "test_plan": [str(body["acceptance_criteria"])],
        "deliverables": [str(body["acceptance_criteria"])],
        "human_approval_required": risk != "low",
        "depends_on": [],
        "context_uri": f"bos://kems/task/{task_id}",
        "metadata": {
            "source_run_id": source_run_id,
            "proposed_owner": str(body["owner"]),
            "due_at": str(body["due_at"]),
            "priority": str(body.get("priority") or "P2"),
            "created_via": "cockpit.kems",
        },
    }
    try:
        from omo.omo_ingress_kems import create_kems_planned_task

        created = create_kems_planned_task(
            WORKSPACE_DIR / ".omo",
            task_payload=payload,
            source_ref=f"kems:{source_run_id}:{task_id}",
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO KEMS ingress is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "id": task_id,
        "status": created.get("status", "candidate"),
        "created": True,
        "review_required": True,
        "source": "omo_kems_ingress",
        "evidence_count": len(evidence_refs),
    }


@router.post("/api/kems/tasks/{task_id}/dispatch")
async def dispatch_kems_task(task_id: str, request: Request) -> dict[str, Any]:
    """Dispatch an OMO-approved active task through the official OMO broker."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="KEMS dispatch must be an object")
    _reject_private_fields(body)
    required = ("worker_id", "allowed_write_paths")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing dispatch fields: {', '.join(missing)}")
    allowed_paths = body["allowed_write_paths"]
    if not isinstance(allowed_paths, list) or not all(isinstance(path, str) and path.strip() for path in allowed_paths):
        raise HTTPException(status_code=422, detail="allowed_write_paths must be a non-empty string list")
    try:
        from omo.omo_worker_dispatch import dispatch_task

        result = dispatch_task(
            WORKSPACE_DIR,
            task_id,
            str(body["worker_id"]),
            allowed_paths,
            launch=bool(body.get("launch", False)),
            transport=str(body.get("transport", "cli_prompt")),
            prior_evidence=[str(item) for item in body.get("prior_evidence", [])],
            prompt_addendum=[str(item) for item in body.get("prompt_addendum", [])],
            omo_dir=body.get("omo_dir", ".omo"),
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="OMO dispatch broker is unavailable") from exc
    except (KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"task_id": task_id, "status": "dispatched", "dispatch": result, "authority": "omo"}


@router.post("/api/kems/ocr/reports")
async def register_ocr_quality_report(request: Request) -> dict[str, Any]:
    """Register OCR metrics and route non-passing reports to human review."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="OCR quality report must be an object")
    _reject_private_fields(body)
    required = ("run_id", "document_id", "source_sha256", "engine", "model_version", "page_metrics")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing OCR fields: {', '.join(missing)}")
    if not isinstance(body["page_metrics"], list) or not body["page_metrics"]:
        raise HTTPException(status_code=422, detail="page_metrics must be a non-empty list")
    try:
        page_type, _, assess = _ocr_symbols()
        pages = tuple(page_type(**page) for page in body["page_metrics"])
        report = assess(
            run_id=str(body["run_id"]),
            document_id=str(body["document_id"]),
            engine=str(body["engine"]),
            model_version=str(body["model_version"]),
            page_metrics=pages,
            cer=body.get("cer"),
            field_accuracy=body.get("field_accuracy"),
            table_cell_f1=body.get("table_cell_f1"),
            evidence_refs=tuple(body.get("evidence_refs") or ()),
        )
        persisted = _ocr_store().record_report(report, source_sha256=str(body["source_sha256"]))
    except HTTPException:
        raise
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="OCR quality persistence is unavailable") from exc
    return {
        "run_id": report.run_id,
        "status": report.status,
        "review_required": report.needs_human_review,
        "admitted": report.status == "pass",
        "persisted": persisted,
        "report": report.to_dict(),
    }


@router.get("/api/kems/ocr/review-queue")
async def get_ocr_review_queue(limit: int = Query(100, ge=1, le=1000)) -> dict[str, Any]:
    try:
        items = _ocr_store().review_queue(limit=limit)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"items": items, "count": len(items), "mode": "review_only"}


@router.get("/api/kems/ocr/runs/{run_id}")
async def get_ocr_run(run_id: str) -> dict[str, Any]:
    try:
        result = _ocr_store().get_report(run_id)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="OCR run not found")
    result["admitted"] = result["quality_status"] == "pass"
    return result


@router.post("/api/kems/ocr/runs/{run_id}/correction")
async def record_ocr_correction(run_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="OCR correction must be an object")
    _reject_private_fields(body)
    required = ("corrected_sha256", "correction_ref", "annotator")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing correction fields: {', '.join(missing)}")
    try:
        correction_id = _ocr_store().record_correction(
            run_id,
            corrected_sha256=str(body["corrected_sha256"]),
            correction_ref=str(body["correction_ref"]),
            annotator=str(body["annotator"]),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"run_id": run_id, "correction_id": correction_id, "review_status": "corrected"}


@router.get("/api/kems/graph/entities")
async def search_kems_entities(
    q: str = Query(..., min_length=1), limit: int = Query(50, ge=1, le=500)
) -> dict[str, Any]:
    try:
        items = _graph_store().search_entities(q, limit=limit)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"items": items, "count": len(items), "mode": "review_only"}


@router.get("/api/kems/graph/entities/{entity_id}/neighbors")
async def get_kems_entity_neighbors(entity_id: str, limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    try:
        items = _graph_store().neighbors(entity_id, limit=limit)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"entity_id": entity_id, "items": items, "count": len(items), "mode": "review_only"}


@router.post("/api/kems/graph/entities/{entity_id}/review")
async def review_kems_entity(entity_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="graph review must be an object")
    _reject_private_fields(body)
    required = ("decision", "reviewer", "reason", "decision_id")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing graph review fields: {', '.join(missing)}")
    try:
        _graph_store().review_entity(
            entity_id=entity_id,
            decision=str(body["decision"]),
            reviewer=str(body["reviewer"]),
            reason=str(body["reason"]),
            decision_id=str(body["decision_id"]),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"entity_id": entity_id, "decision": body["decision"], "persisted": True}


@router.post("/api/kems/graph/runs/{run_id}/rollback")
async def rollback_kems_graph_run(run_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="graph rollback must be an object")
    required = ("reviewer", "reason", "decision_id")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing rollback fields: {', '.join(missing)}")
    try:
        counts = _graph_store().rollback_run(
            run_id, reviewer=str(body["reviewer"]), reason=str(body["reason"]), decision_id=str(body["decision_id"])
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"run_id": run_id, "rolled_back": True, "counts": counts}


@router.post("/api/kems/forecast/shadow")
async def create_kems_shadow_forecast(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="forecast request must be an object")
    _reject_private_fields(body)
    required = ("forecast_id", "series_id", "source_run_id", "values", "horizon")
    missing = [field for field in required if body.get(field) in (None, "", [])]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing forecast fields: {', '.join(missing)}")
    values = body["values"]
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values)
    ):
        raise HTTPException(status_code=422, detail="values must be a finite numeric list")
    try:
        store, builder, _ = _forecast_symbols()
        forecast = builder(
            tuple(float(value) for value in values),
            series_id=str(body["series_id"]),
            source_run_id=str(body["source_run_id"]),
            horizon=int(body["horizon"]),
            window=int(body.get("window", 3)),
        )
        persisted = store.record_forecast(str(body["forecast_id"]), forecast)
    except (OSError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"forecast_id": body["forecast_id"], "persisted": persisted, "forecast": forecast.to_dict()}


@router.get("/api/kems/forecast/{forecast_id}")
async def get_kems_shadow_forecast(forecast_id: str) -> dict[str, Any]:
    try:
        result = _forecast_symbols()[0].get_forecast(forecast_id)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="forecast not found")
    return result


@router.post("/api/kems/forecast/{forecast_id}/evaluation")
async def evaluate_kems_shadow_forecast(forecast_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict) or not body.get("evaluation_id") or not isinstance(body.get("actual"), list):
        raise HTTPException(status_code=422, detail="evaluation_id and actual are required")
    _reject_private_fields(body)
    actual = body["actual"]
    if not actual or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in actual):
        raise HTTPException(status_code=422, detail="actual must be a finite numeric list")
    try:
        store, _, evaluator = _forecast_symbols()
        saved = store.get_forecast(forecast_id)
        if saved is None:
            raise KeyError(forecast_id)
        evaluation = evaluator(
            model_id=str(saved["model_id"]),
            predictions=tuple(float(value) for value in saved["predictions"]),
            actual=tuple(float(value) for value in actual),
            baseline_value=float(saved["baseline_value"]),
        )
        persisted = store.record_evaluation(str(body["evaluation_id"]), forecast_id, evaluation)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"forecast not found: {exc.args[0]}") from exc
    except (OSError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"forecast_id": forecast_id, "persisted": persisted, "evaluation": evaluation.to_dict()}


@router.post("/api/kems/evaluations/manifests")
async def register_kems_evaluation_manifest(request: Request) -> dict[str, Any]:
    """Register an adjudicated, redaction-verified evaluation manifest."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="evaluation manifest must be an object")
    _reject_private_fields(body)
    required = ("dataset_id", "dataset_version", "samples")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing evaluation fields: {', '.join(missing)}")
    if body.get("redaction_status", "verified") != "verified":
        raise HTTPException(status_code=422, detail="evaluation manifest must be redaction-verified")
    raw_samples = body["samples"]
    if not isinstance(raw_samples, list) or not raw_samples:
        raise HTTPException(status_code=422, detail="samples must be a non-empty list")
    try:
        manifest_type, sample_type, store, _ = _evaluation_symbols()
        samples = []
        for index, sample in enumerate(raw_samples, 1):
            if not isinstance(sample, dict):
                raise ValueError(f"sample {index} must be an object")
            if sample.get("annotation_status") != "adjudicated":
                raise ValueError(f"sample {index} must be adjudicated")
            labels = sample.get("labels")
            if not isinstance(labels, dict) or not labels:
                raise ValueError(f"sample {index} labels must be a non-empty object")
            samples.append(
                sample_type(
                    sample_id=str(sample.get("sample_id", "")),
                    source_sha256=str(sample.get("source_sha256", "")),
                    source_ref=str(sample.get("source_ref", "")),
                    scenario_id=str(sample.get("scenario_id", "")),
                    split=str(sample.get("split", "test")),
                    annotation_status="adjudicated",
                    labels=labels,
                    annotation_version=str(sample.get("annotation_version", "")),
                )
            )
        manifest = manifest_type(
            schema_version="kems.evaluation-manifest.v1",
            dataset_id=str(body["dataset_id"]),
            dataset_version=str(body["dataset_version"]),
            redaction_status="verified",
            samples=tuple(samples),
        )
        persisted = store.register_manifest(manifest)
    except HTTPException:
        raise
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="evaluation persistence is unavailable") from exc
    return {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "sample_count": len(manifest.samples),
        "persisted": persisted,
        "redaction_status": manifest.redaction_status,
    }


@router.post("/api/kems/evaluations/runs/{run_id}")
async def record_kems_evaluation_run(run_id: str, request: Request) -> dict[str, Any]:
    """Record an exact-match baseline run against a registered dataset."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="evaluation run must be an object")
    _reject_private_fields(body)
    required = ("dataset_id", "dataset_version", "model_id", "expected", "actual")
    missing = [field for field in required if field not in body or body[field] in (None, "")]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing evaluation run fields: {', '.join(missing)}")
    if not isinstance(body["expected"], dict) or not isinstance(body["actual"], dict):
        raise HTTPException(status_code=422, detail="expected and actual must be objects")
    try:
        _, _, store, evaluator = _evaluation_symbols()
        dataset_id = str(body["dataset_id"])
        dataset_version = str(body["dataset_version"])
        if store.sample_count(dataset_id, dataset_version) == 0:
            raise KeyError(f"unknown dataset: {dataset_id}@{dataset_version}")
        evaluation = evaluator(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            model_id=str(body["model_id"]),
            expected=body["expected"],
            actual=body["actual"],
        )
        store.record_run(run_id, evaluation)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="evaluation persistence is unavailable") from exc
    return {"run_id": run_id, "persisted": True, "evaluation": evaluation.to_dict()}


@router.get("/api/kems/evaluations/runs/{run_id}")
async def get_kems_evaluation_run(run_id: str) -> dict[str, Any]:
    try:
        result = _evaluation_symbols()[2].get_run(run_id)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="evaluation persistence is unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return result


@router.post("/api/kems/models/candidates/{candidate_model_id}/evaluation")
async def evaluate_kems_candidate_model(candidate_model_id: str, request: Request) -> dict[str, Any]:
    """Evaluate and persist numeric, redacted candidate-model evidence."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="model evaluation request must be an object")
    _reject_private_fields(body)
    required = (
        "run_id",
        "cases",
        "dataset_id",
        "dataset_version",
        "evaluation_manifest_sha256",
        "dataset_sample_count",
    )
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing model evaluation fields: {', '.join(missing)}")
    if not isinstance(body["cases"], list):
        raise HTTPException(status_code=422, detail="cases must be a list")
    if not all(isinstance(body[field], str) and body[field].strip() for field in ("dataset_id", "dataset_version")):
        raise HTTPException(status_code=422, detail="dataset identity is required")
    if not isinstance(body["evaluation_manifest_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", body["evaluation_manifest_sha256"]
    ):
        raise HTTPException(status_code=422, detail="evaluation_manifest_sha256 must be a SHA-256")
    if (
        isinstance(body["dataset_sample_count"], bool)
        or not isinstance(body["dataset_sample_count"], int)
        or body["dataset_sample_count"] <= 0
    ):
        raise HTTPException(status_code=422, detail="dataset_sample_count must be positive")
    try:
        store, input_error, evaluator = _model_acceptance_symbols()
    except HTTPException:
        raise
    try:
        evaluation = evaluator(
            body["cases"],
            candidate_model_id=candidate_model_id,
            baseline_model_id=str(body.get("baseline_model_id") or "naive-last-v1"),
            min_cases=int(body.get("min_cases", 1)),
            min_relative_improvement=float(body.get("min_relative_improvement", 0.0)),
            dataset_id=body["dataset_id"].strip(),
            dataset_version=body["dataset_version"].strip(),
            evaluation_manifest_sha256=body["evaluation_manifest_sha256"],
            dataset_sample_count=body["dataset_sample_count"],
        )
        store.record(str(body["run_id"]), evaluation)
    except input_error as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="model acceptance persistence is unavailable") from exc
    return {"run_id": str(body["run_id"]), "persisted": True, "evaluation": evaluation}


@router.get("/api/kems/models/evaluations/{run_id}")
async def get_kems_model_evaluation(run_id: str) -> dict[str, Any]:
    try:
        result = _model_acceptance_symbols()[0].get(run_id)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="model acceptance persistence is unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="model evaluation run not found")
    return result


@router.post("/api/kems/adjudication/queue")
async def import_kems_adjudication_queue(request: Request) -> dict[str, Any]:
    """Import only redacted queue metadata into the persistent adjudication store."""
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise HTTPException(status_code=422, detail="items must be a list")
    _reject_private_fields(body)
    try:
        inserted = _adjudication_store().ingest_queue(body["items"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="adjudication persistence is unavailable") from exc
    return {"inserted": inserted, "count": len(body["items"]), "mode": "review_only"}


@router.get("/api/kems/adjudication/queue")
async def get_kems_adjudication_queue(
    status: str | None = Query(None), limit: int = Query(100, ge=1, le=1000)
) -> dict[str, Any]:
    try:
        items = _adjudication_store().list_items(status=status, limit=limit)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"items": items, "count": len(items), "mode": "review_only"}


@router.post("/api/kems/adjudication/{sample_id}/claim")
async def claim_kems_adjudication(sample_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict) or not body.get("annotator"):
        raise HTTPException(status_code=422, detail="annotator is required")
    _reject_private_fields(body)
    try:
        item = _adjudication_store().claim(sample_id, annotator=str(body["annotator"]))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"sample not found: {exc.args[0]}") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"item": item, "status": item["annotation_status"]}


@router.post("/api/kems/adjudication/{sample_id}/adjudicate")
async def adjudicate_kems_sample(sample_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict) or not isinstance(body.get("labels"), dict):
        raise HTTPException(status_code=422, detail="labels must be an object")
    _reject_private_fields(body)
    required = ("annotation_version", "annotator")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing adjudication fields: {', '.join(missing)}")
    try:
        item = _adjudication_store().adjudicate(
            sample_id,
            labels=body["labels"],
            annotation_version=str(body["annotation_version"]),
            annotator=str(body["annotator"]),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"sample not found: {exc.args[0]}") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"item": item, "status": item["annotation_status"]}


@router.post("/api/kems/adjudication/manifest")
async def build_kems_adjudicated_manifest(request: Request) -> dict[str, Any]:
    """Materialize a manifest only from persisted, adjudicated queue records."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="manifest request must be an object")
    _reject_private_fields(body)
    required = ("dataset_id", "dataset_version")
    missing = [field for field in required if not body.get(field)]
    if missing:
        raise HTTPException(status_code=422, detail=f"missing manifest fields: {', '.join(missing)}")
    try:
        manifest_type, sample_type, evaluation_store, _ = _evaluation_symbols()
        rows = _adjudication_store().adjudicated_items()
        if not rows:
            raise ValueError("no adjudicated samples are available")
        samples = tuple(
            sample_type(
                sample_id=str(row["sample_id"]),
                source_sha256=str(row["source_sha256"]),
                source_ref=str(row["source_ref"]),
                scenario_id=str(row["scenario_id"]),
                split=str(row["split"]),
                annotation_status="adjudicated",
                labels=row["labels"],
                annotation_version=str(row["annotation_version"]),
            )
            for row in rows
        )
        manifest = manifest_type(
            schema_version="kems.evaluation-manifest.v1",
            dataset_id=str(body["dataset_id"]),
            dataset_version=str(body["dataset_version"]),
            redaction_status="verified",
            samples=samples,
        )
        persisted = evaluation_store.register_manifest(manifest)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail="evaluation persistence is unavailable") from exc
    return {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "sample_count": len(manifest.samples),
        "persisted": persisted,
        "redaction_status": manifest.redaction_status,
    }
