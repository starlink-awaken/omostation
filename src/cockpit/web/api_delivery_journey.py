"""Cockpit Web API — Engineering Delivery Golden Journey Endpoints.

Provides read-only projection of engineering tasks across the 7 golden stages:
intent, task, run, worktree, verification, pr, evidence.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Optional

try:
    from fastapi import APIRouter, HTTPException, Query
except ImportError:
    APIRouter = None  # type: ignore[assignment,misc]
    HTTPException = None  # type: ignore[assignment,misc]
    Query = None  # type: ignore[assignment,misc]

from cockpit.delivery_journey import (  # type: ignore[import-not-found]
    DeliveryJourneySnapshot,
    build_delivery_journey_projection,
)

router = APIRouter(prefix="/api/delivery-journey", tags=["delivery-journey"]) if APIRouter else None


def _get_workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


if router:

    @router.get("")
    @router.get("/")
    async def get_delivery_journey(
        fixture: str | None = Query(
            None, description="Optional safe fixture state: PENDING, RUNNING, VERIFIED, MERGED, UNAVAILABLE"
        ),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Get the current engineering delivery journey projection snapshot."""
        try:
            snapshot = build_delivery_journey_projection(
                root_dir=_get_workspace_root(),
                fixture_state=fixture,
            )
            return {
                "ok": snapshot.status != "unavailable",
                "status": snapshot.status,
                "journey": snapshot.to_dict(),
                "source": snapshot.source,
                "freshness": snapshot.freshness,
                "last_updated": snapshot.last_updated,
            }
        except Exception as e:
            now_iso = datetime.datetime.now(datetime.UTC).isoformat()
            return {
                "ok": False,
                "status": "unavailable",
                "error": str(e),
                "source": ["error-fallback"],
                "freshness": 0,
                "last_updated": now_iso,
                "journey": {
                    "id": "error-unavailable",
                    "title": "Projection Unavailable",
                    "status": "unavailable",
                    "source": [],
                    "freshness": 0,
                    "last_updated": now_iso,
                    "stages": {},
                },
            }

    @router.get("/current")
    async def get_current_delivery_journey(
        fixture: str | None = Query(None, description="Optional safe fixture state"),  # type: ignore[union-attr]
    ) -> dict[str, Any]:
        """Alias for retrieving the active/current delivery journey."""
        return await get_delivery_journey(fixture=fixture)
