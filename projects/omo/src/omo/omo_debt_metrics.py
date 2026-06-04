from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .omo_debt_registry import DebtItem


@dataclass(frozen=True)
class DebtMetrics:
    debt_health: float
    classification_entropy: float
    state_entropy: float
    pointer_entropy: float
    time_entropy: float
    backlog_pressure: float
    coupling_load: float
    debt_watchlist_count: int
    debt_gate_count: int
    watchlist_item_ids: tuple[str, ...]
    gate_item_ids: tuple[str, ...]
    closed_item_ids: tuple[str, ...]


def _resolve_ref_path(repo_root: Path, ref: str) -> Path:
    ref_path = Path(ref)
    if ref_path.is_absolute():
        return ref_path
    return repo_root / ref_path


def collect_stale_evidence_item_ids(
    items: tuple[DebtItem, ...], repo_root: Path | None = None
) -> set[str]:
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    stale_ids: set[str] = set()

    for item in items:
        if item.lifecycle_state == "closed":
            continue
        if not item.evidence_refs or not item.mitigation_refs:
            stale_ids.add(item.id)
            continue
        refs = tuple(
            _resolve_ref_path(repo_root, ref)
            for ref in (*item.evidence_refs, *item.mitigation_refs)
        )
        if any(not ref.exists() for ref in refs):
            stale_ids.add(item.id)
            continue
        if not item.last_reviewed_at:
            stale_ids.add(item.id)
            continue
        last_reviewed = datetime.fromisoformat(
            item.last_reviewed_at.replace("Z", "+00:00")
        )
        if any(
            datetime.fromtimestamp(ref.stat().st_mtime, tz=timezone.utc) > last_reviewed
            for ref in refs
        ):
            stale_ids.add(item.id)
    return stale_ids


def compute_debt_metrics(
    items: tuple[DebtItem, ...], now: str, repo_root: Path | None = None
) -> DebtMetrics:
    current = datetime.fromisoformat(now.replace("Z", "+00:00"))
    open_items = [item for item in items if item.lifecycle_state != "closed"]
    overdue = [
        item
        for item in open_items
        if item.next_review_at
        and datetime.fromisoformat(item.next_review_at.replace("Z", "+00:00")) < current
    ]
    vague = [item for item in open_items if item.dimension in {"other", "unknown"}]
    missing_pointers = [
        item
        for item in open_items
        if not item.owner
        or not item.evidence_refs
        or not item.last_reviewed_at
        or not item.next_review_at
    ]
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    stale_ids = collect_stale_evidence_item_ids(tuple(open_items), repo_root=repo_root)
    stale_evidence = [item for item in open_items if item.id in stale_ids]
    long_running = [
        item
        for item in open_items
        if item.lifecycle_state
        in {"classified", "scheduled", "in_progress", "mitigated"}
    ]
    watchlist = [item.id for item in open_items if item.gate_level == "watchlist"]
    gate = [item.id for item in open_items if item.gate_level == "gate"]
    denominator = max(len(open_items), 1)
    health = max(
        0.0,
        100.0
        - (12.5 * len(overdue))
        - (10.0 * len(gate))
        - (7.5 * len(missing_pointers))
        - (5.0 * len(stale_evidence)),
    )

    return DebtMetrics(
        debt_health=round(health, 2),
        classification_entropy=round(len(vague) / denominator, 2),
        state_entropy=round(len(long_running) / denominator, 2),
        pointer_entropy=round(
            (len(missing_pointers) + len(stale_evidence)) / denominator, 2
        ),
        time_entropy=round(len(overdue) / denominator, 2),
        backlog_pressure=round(sum(item.weight for item in open_items), 2),
        coupling_load=round(
            sum(len(item.affected_roots) for item in open_items) / denominator, 2
        ),
        debt_watchlist_count=len(watchlist),
        debt_gate_count=len(gate),
        watchlist_item_ids=tuple(watchlist),
        gate_item_ids=tuple(gate),
        closed_item_ids=tuple(
            item.id for item in items if item.lifecycle_state == "closed"
        ),
    )
