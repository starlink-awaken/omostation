#!/usr/bin/env python3
"""Scene Card Connector — 真实输入接入引擎.

The connector provides automated import from real-world sources:
- Email (IMAP/MBOX file import)
- OA notifications (file-based import)
- Cron-style periodic intake

This is the Week 4 M4 deliverable for real input access.

SSOT:  ecos/src/ecos/ssot/registry/scene-cards.yaml
Engine: bin/ssot/scene-card-connector.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class ConnectorRun:
    run_id: str = ""
    source: str = ""
    started_at: str = ""
    completed_at: str = ""
    items_found: int = 0
    items_imported: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ConnectorConfig:
    source: str = "manual"
    scene_id: str = ""
    journey_id: str = ""
    interval_minutes: int = 60
    enabled: bool = True
    last_run: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _load_engine(workspace_root: Path, filename: str, name: str):
    path = workspace_root / "bin" / "ssot" / filename
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"{filename} is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_inbox(workspace_root: Path):
    return _load_engine(workspace_root, "scene-card-decision-inbox.py", "connector_inbox")


def _load_intake(workspace_root: Path):
    return _load_engine(workspace_root, "scene-card-intake-pipeline.py", "connector_intake")


# ── Connector storage ──


def _connector_path(workspace_root: Path) -> Path:
    p = workspace_root / ".omo" / "_connector"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _runs_path(workspace_root: Path) -> Path:
    p = _connector_path(workspace_root) / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _config_path(workspace_root: Path) -> Path:
    return _connector_path(workspace_root) / "configs.json"


def save_run(workspace_root: Path, run: ConnectorRun) -> None:
    p = _runs_path(workspace_root) / f"{run.run_id}.json"
    p.write_text(json.dumps(asdict(run), indent=2, ensure_ascii=False))


def list_runs(workspace_root: Path, limit: int = 20) -> list[ConnectorRun]:
    runs = []
    for f in sorted(_runs_path(workspace_root).glob("run-*.json"), reverse=True)[:limit]:
        data = json.loads(f.read_text())
        runs.append(ConnectorRun(**data))
    return runs


def load_configs(workspace_root: Path) -> list[ConnectorConfig]:
    p = _config_path(workspace_root)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [ConnectorConfig(**c) for c in data.get("configs", [])]


def save_configs(workspace_root: Path, configs: list[ConnectorConfig]) -> None:
    p = _config_path(workspace_root)
    p.write_text(json.dumps({"configs": [asdict(c) for c in configs]}, indent=2, ensure_ascii=False))


# ── Source-specific importers ──


def _import_mbox(workspace_root: Path, mbox_path: Path, scene_id: str, journey_id: str | None = None) -> ConnectorRun:
    """Import emails from an mbox file."""
    run_id = _new_id("run")
    run = ConnectorRun(run_id=run_id, source="email", started_at=_now_iso())
    intake = _load_intake(workspace_root)
    inbox = _load_inbox(workspace_root)

    if not mbox_path.exists():
        run.errors.append(f"File not found: {mbox_path}")
        run.completed_at = _now_iso()
        save_run(workspace_root, run)
        return run

    try:
        import mailbox
        mbox = mailbox.mbox(str(mbox_path))
        run.items_found = len(mbox)

        for i, msg in enumerate(mbox):
            if i >= 50:  # Limit per run
                break
            try:
                subject = str(msg.get("subject", "(no subject)"))
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

                content = f"Subject: {subject}\n\n{body[:2000]}"
                result = intake.intake(
                    workspace_root, source="email", raw_content=content,
                    scene_id=scene_id, journey_id=journey_id,
                )
                if result.ok:
                    run.items_imported += 1
                else:
                    run.errors.append(f"Item {i}: {result.error}")
            except Exception as e:
                run.errors.append(f"Item {i}: {str(e)}")

        mbox.close()
    except ImportError:
        run.errors.append("mailbox module not available (Python standard library)")
    except Exception as e:
        run.errors.append(f"MBOX import error: {str(e)}")

    run.completed_at = _now_iso()
    save_run(workspace_root, run)
    return run


def _import_directory(workspace_root: Path, source_dir: Path, scene_id: str, journey_id: str | None = None) -> ConnectorRun:
    """Import files from a directory."""
    run_id = _new_id("run")
    run = ConnectorRun(run_id=run_id, source="file", started_at=_now_iso())
    intake = _load_intake(workspace_root)

    if not source_dir.exists():
        run.errors.append(f"Directory not found: {source_dir}")
        run.completed_at = _now_iso()
        save_run(workspace_root, run)
        return run

    files = sorted(source_dir.glob("*"))
    run.items_found = len(files)

    for f in files:
        if not f.is_file():
            continue
        if f.suffix in (".pyc", ".pyo", ".DS_Store"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            result = intake.intake(
                workspace_root, source="file", raw_content=content[:2000],
                scene_id=scene_id, journey_id=journey_id, filename=f.name,
            )
            if result.ok:
                run.items_imported += 1
            else:
                run.errors.append(f"File {f.name}: {result.error}")
        except Exception as e:
            run.errors.append(f"File {f.name}: {str(e)}")

    run.completed_at = _now_iso()
    save_run(workspace_root, run)
    return run


def _import_jsonl(workspace_root: Path, jsonl_path: Path, scene_id: str, journey_id: str | None = None) -> ConnectorRun:
    """Import items from a JSONL file (each line is a JSON object with source/content)."""
    run_id = _new_id("run")
    run = ConnectorRun(run_id=run_id, source="batch", started_at=_now_iso())
    intake = _load_intake(workspace_root)

    if not jsonl_path.exists():
        run.errors.append(f"File not found: {jsonl_path}")
        run.completed_at = _now_iso()
        save_run(workspace_root, run)
        return run

    lines = jsonl_path.read_text().strip().split("\n")
    run.items_found = len(lines)

    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            result = intake.intake(
                workspace_root,
                source=item.get("source", "manual"),
                raw_content=item.get("content", ""),
                scene_id=scene_id,
                journey_id=journey_id,
                filename=item.get("filename", ""),
            )
            if result.ok:
                run.items_imported += 1
            else:
                run.errors.append(f"Line: {result.error}")
        except Exception as e:
            run.errors.append(f"JSON parse error: {str(e)}")

    run.completed_at = _now_iso()
    save_run(workspace_root, run)
    return run


# ── Public API ──


def run_connector(
    workspace_root: Path,
    source: str,
    scene_id: str,
    source_path: str = "",
    journey_id: str | None = None,
) -> ConnectorRun:
    """Run a connector for a specific source.

    Args:
        source: Source type (email, file, jsonl, manual)
        scene_id: Target scene ID
        source_path: Path to source (mbox file, directory, jsonl file)
        journey_id: Optional journey ID

    Returns:
        ConnectorRun with results.
    """
    source_path_obj = Path(source_path) if source_path else workspace_root

    if source == "email":
        return _import_mbox(workspace_root, source_path_obj, scene_id, journey_id)
    elif source == "file":
        return _import_directory(workspace_root, source_path_obj, scene_id, journey_id)
    elif source == "jsonl":
        return _import_jsonl(workspace_root, source_path_obj, scene_id, journey_id)
    else:
        run = ConnectorRun(
            run_id=_new_id("run"), source=source,
            started_at=_now_iso(), completed_at=_now_iso(),
            errors=[f"Unknown source: {source}"],
        )
        save_run(workspace_root, run)
        return run


def get_connector_stats(workspace_root: Path) -> dict[str, Any]:
    """Get connector statistics."""
    runs = list_runs(workspace_root, limit=100)

    total_runs = len(runs)
    total_found = sum(r.items_found for r in runs)
    total_imported = sum(r.items_imported for r in runs)
    total_errors = sum(len(r.errors) for r in runs)

    # Group by source
    by_source: dict[str, dict[str, int]] = {}
    for r in runs:
        if r.source not in by_source:
            by_source[r.source] = {"runs": 0, "found": 0, "imported": 0, "errors": 0}
        by_source[r.source]["runs"] += 1
        by_source[r.source]["found"] += r.items_found
        by_source[r.source]["imported"] += r.items_imported
        by_source[r.source]["errors"] += len(r.errors)

    return {
        "total_runs": total_runs,
        "total_found": total_found,
        "total_imported": total_imported,
        "total_errors": total_errors,
        "by_source": by_source,
        "last_run": runs[0].completed_at if runs else None,
    }
