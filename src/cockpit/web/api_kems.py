"""KEMS workbench API: read-only status and evidence-bound OMO task drafts."""

from __future__ import annotations

import math
import os
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
        "capabilities": ["ocr_review", "graph_review", "evaluation", "omo_task_draft"],
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
