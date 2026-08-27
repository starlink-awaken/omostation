from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from cockpit.adapters.governance import _utils
from cockpit.adapters.governance_context import resolve_workspace_root


def _workspace_state(workspace_root: Path) -> dict[str, Any]:
    system_path = workspace_root / ".omo" / "state" / "system.yaml"
    goals_path = workspace_root / ".omo" / "_truth" / "goals" / "current.yaml"
    system: dict[str, Any] = {}
    goals: dict[str, Any] = {}
    errors: list[str] = []

    try:
        import yaml

        loaded = yaml.safe_load(system_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("system state must be a mapping")
        system = loaded
    except Exception as exc:
        errors.append(f"system: {exc}")

    try:
        import yaml

        documents = list(yaml.safe_load_all(goals_path.read_text(encoding="utf-8")))
        for document in documents:
            if isinstance(document, dict):
                goals.update(document)
        if not goals:
            raise ValueError("goals state must contain a mapping")
    except Exception as exc:
        errors.append(f"goals: {exc}")

    active_goals = []
    for goal in goals.get("goals") or []:
        if not isinstance(goal, dict) or goal.get("status") not in {"active", "in_progress"}:
            continue
        active_goals.append({key: goal[key] for key in ("id", "title", "desc", "status", "progress") if key in goal})
    theme = goals.get("theme") or system.get("next_milestone")
    if not theme and active_goals:
        theme = active_goals[0].get("title") or active_goals[0].get("desc")

    if system and goals:
        status = "ok"
    elif system or goals:
        status = "degraded"
    else:
        status = "unavailable"
    return {
        "status": status,
        "available": bool(system or goals),
        "phase": system.get("current_phase"),
        "phase_status": system.get("phase_status"),
        "theme": theme,
        "current_wave": goals.get("current_wave") or system.get("current_wave"),
        "active_goals": active_goals,
        "sources": {"system": str(system_path), "goals": str(goals_path)},
        "errors": errors,
    }


def _omo_workdir(workspace_root: Path) -> Path | None:
    candidates = [
        workspace_root / "projects" / "omo",
        Path(__file__).resolve().parents[3].parent / "omo",
    ]
    return next((path for path in candidates if path.is_dir()), None)


def _run_omo(
    arguments: list[str],
    *,
    workspace_root: str | Path | None = None,
    timeout: float = 20,
) -> subprocess.CompletedProcess[str]:
    root = resolve_workspace_root(workspace_root)
    cwd = _omo_workdir(root)
    return subprocess.run(
        [sys.executable, "-m", "omo.omo_cards", *arguments],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
        timeout=timeout,
    )


_CARD_LINE = re.compile(r"^\[(P[0-3])\]\s+(\S+)\s{2,}(\S+)\s{2,}(\S+)\s{2,}(.*?)\s*$")


def _parse_cards(output: str) -> list[dict[str, str]]:
    items = []
    for line in output.splitlines():
        match = _CARD_LINE.match(line)
        if not match:
            continue
        priority, card_id, status, domain, title = match.groups()
        items.append(
            {
                "id": card_id,
                "priority": priority,
                "status": status,
                "domain": domain,
                "title": title,
            }
        )
    return items


def cards_status(
    *,
    workspace_root: str | Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    from cockpit.adapters.governance_context import _run_omo

    try:
        result = _run_omo(["list", "--limit", str(limit)], workspace_root=workspace_root)
    except Exception as exc:
        return {
            "schema": "cockpit.cards.v1",
            "status": "unavailable",
            "available": False,
            "owner": "omo",
            "returncode": 127,
            "total": 0,
            "items": [],
            "error": str(exc),
        }

    items = _parse_cards(result.stdout)
    total_match = re.search(r"(?m)^(\d+) cards\s*$", result.stdout)
    total = int(total_match.group(1)) if total_match else len(items)
    owner_error = result.stderr.strip()
    if result.returncode != 0:
        status = "unavailable"
        available = False
    elif items or "(no cards)" in result.stdout or not result.stdout.strip():
        status = "ok"
        available = True
    else:
        status = "degraded"
        available = True
        owner_error = owner_error or "OMO output could not be normalized"
    envelope = {
        "schema": "cockpit.cards.v1",
        "status": status,
        "available": available,
        "owner": "omo",
        "returncode": result.returncode,
        "total": total,
        "items": items,
        "raw": result.stdout,
    }
    if owner_error:
        envelope["error"] = owner_error
    return envelope


def _violation_lines(output: str) -> list[str]:
    ignored_prefixes = ("📋 Constraint Check Results", "──")
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip()
        and not line.strip().startswith(ignored_prefixes)
        and not line.strip().endswith("violation(s) ──")
        and line.strip() != "✅ All checks passed."
    ]


def cards_check(
    card_id: str = "",
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    from cockpit.adapters.governance_context import _run_omo

    try:
        result = _run_omo(["check"], workspace_root=workspace_root)
    except Exception as exc:
        return {
            "schema": "cockpit.cards-check.v1",
            "status": "unavailable",
            "available": False,
            "owner": "omo",
            "scope": "all",
            "requested_card_id": card_id,
            "compliant": False,
            "returncode": 127,
            "violations": [],
            "error": str(exc),
        }

    compliant = result.returncode == 0
    return {
        "schema": "cockpit.cards-check.v1",
        "status": "ok" if compliant else "violations",
        "available": True,
        "owner": "omo",
        "scope": "all",
        "requested_card_id": card_id,
        "compliant": compliant,
        "returncode": result.returncode,
        "violations": [] if compliant else _violation_lines(result.stdout),
        "raw": result.stdout,
        "stderr": result.stderr,
    }


def workspace_context(*, workspace_root: str | Path | None = None) -> dict[str, Any]:
    root = resolve_workspace_root(workspace_root)
    workspace = _workspace_state(root)
    from cockpit.adapters.governance_context import cards_status, domains_list

    domain_result = domains_list()
    card_result = cards_status(workspace_root=root)
    cards = card_result.get("items") or []
    p0 = [card for card in cards if card.get("priority") == "P0"]
    statuses = (workspace["status"], domain_result["status"], card_result["status"])
    available = any((workspace["available"], domain_result["available"], card_result["available"]))
    return {
        "schema": "cockpit.governance-context.v1",
        "status": "ok" if all(status == "ok" for status in statuses) else "degraded",
        "available": available,
        "workspace_root": str(root),
        "phase": workspace["phase"],
        "phase_status": workspace["phase_status"],
        "theme": workspace["theme"],
        "current_wave": workspace["current_wave"],
        "active_goals": workspace["active_goals"],
        "domains": domain_result["domains"],
        "domain_summary": {
            "total": domain_result["total"],
            "existing": sum(1 for domain in domain_result["domains"] if domain["exists"]),
        },
        "cards_summary": {
            "status": card_result["status"],
            "active": len(cards),
            "total": card_result.get("total", len(cards)),
            "p0_open": len(p0),
            "p0_titles": [card.get("title", "") for card in p0],
        },
        "sources": {
            "workspace": workspace,
            "domains": {
                key: domain_result[key] for key in ("status", "available", "owner", "source") if key in domain_result
            },
            "cards": {
                key: card_result[key]
                for key in ("status", "available", "owner", "returncode", "error")
                if key in card_result
            },
        },
    }


def _module_status(module_name: str, owner: str) -> dict[str, Any]:
    try:
        available = importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError):
        available = False
    return {"owner": owner, "status": "ok" if available else "unavailable", "available": available}


def _content_status(documents_root: Path) -> dict[str, Any]:
    return {
        "owner": "l4-kernel",
        "status": "not_run",
        "available": False,
        "root": str(documents_root),
        "reason": "full Documents content audit is on-demand; run cockpit kems scan",
    }


def kems_status(
    *,
    workspace_root: str | Path | None = None,
    documents_root: str | Path | None = None,
) -> dict[str, Any]:
    root = _utils._documents_root(documents_root)
    from cockpit.adapters.governance_context import domains_list

    domains = domains_list(documents_root=root)
    content = _content_status(root)
    owners = {
        "omo": _module_status("omo", "omo"),
        "kairon": _module_status("kairon_observability", "kairon"),
    }
    statuses = [domains["status"], content["status"], *(item["status"] for item in owners.values())]
    return {
        "schema": "cockpit.kems-status.v1",
        "status": "ok" if all(status == "ok" for status in statuses) else "degraded",
        "available": bool(domains["available"] or content["available"]),
        "workspace_root": str(resolve_workspace_root(workspace_root)),
        "documents_root": str(root),
        "domains": {
            "status": domains["status"],
            "available": domains["available"],
            "total": domains["total"],
            "source": domains["source"],
        },
        "content_audit": content,
        "owners": owners,
    }
