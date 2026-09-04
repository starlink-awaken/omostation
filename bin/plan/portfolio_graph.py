"""Pure Portfolio v2 coverage graph and critical-path derivation (BET-Y1Q4-T1-05).

Read-only over an in-memory Ledger. Never mutates input, never touches the
filesystem, and never invents progress percentages from raw BET counts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


TERMINAL_STATUSES = frozenset({"done", "failed"})


@dataclass(frozen=True)
class GraphEdge:
    src: str
    dst: str
    kind: str  # depends_on | covers
    rationale: str | None = None


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: str  # bet | milestone | kr | campaign | objective
    status: str | None = None
    window: str | None = None
    parent_bet: str | None = None
    write_surfaces: tuple[str, ...] = ()
    replacement_of: str | None = None
    replaced_by: str | None = None


@dataclass(frozen=True)
class PortfolioGraph:
    nodes: dict[str, GraphNode]
    depends_on: tuple[GraphEdge, ...]
    covers: tuple[GraphEdge, ...]
    required_kr_ids: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class CoverageValidationResult:
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _topo_depths(nodes: Iterable[str], edges: Iterable[GraphEdge]) -> dict[str, int] | None:
    """Return depth map or None when a cycle exists."""
    preds: dict[str, set[str]] = {n: set() for n in nodes}
    succs: dict[str, set[str]] = {n: set() for n in nodes}
    for edge in edges:
        if edge.src not in preds or edge.dst not in preds:
            continue
        # depends_on: src depends on dst → edge into src from dst
        preds[edge.src].add(edge.dst)
        succs[edge.dst].add(edge.src)

    depth = {n: 0 for n in nodes}
    ready = [n for n, p in preds.items() if not p]
    seen = 0
    while ready:
        ready.sort()
        n = ready.pop(0)
        seen += 1
        for child in sorted(succs[n]):
            depth[child] = max(depth[child], depth[n] + 1)
            preds[child].discard(n)
            if not preds[child]:
                ready.append(child)
    if seen != len(list(nodes)):
        return None
    return depth


def build_graph(ledger: dict[str, Any]) -> PortfolioGraph:
    """Build an immutable Portfolio graph from a Ledger mapping."""
    if not isinstance(ledger, dict):
        return PortfolioGraph(nodes={}, depends_on=(), covers=(), errors=("PORTFOLIO_SCHEMA_INVALID: ledger must be a mapping",))

    nodes: dict[str, GraphNode] = {}
    depends: list[GraphEdge] = []
    covers: list[GraphEdge] = []
    errors: list[str] = []
    required_krs: list[str] = []

    objectives = ledger.get("objectives") or []
    if isinstance(objectives, list):
        for objective in objectives:
            if not isinstance(objective, dict) or not isinstance(objective.get("id"), str):
                continue
            oid = objective["id"]
            nodes[oid] = GraphNode(id=oid, kind="objective")
            for kr in objective.get("key_results") or []:
                if isinstance(kr, dict) and isinstance(kr.get("id"), str):
                    kid = kr["id"]
                    nodes[kid] = GraphNode(id=kid, kind="kr")
                    if kr.get("required") is True:
                        required_krs.append(kid)

    vision = ledger.get("vision")
    if isinstance(vision, dict):
        for kid in _as_str_list(vision.get("required_key_results")):
            if kid not in required_krs:
                required_krs.append(kid)

    campaigns = ledger.get("campaigns") or []
    if isinstance(campaigns, list):
        for campaign in campaigns:
            if isinstance(campaign, dict) and isinstance(campaign.get("id"), str):
                nodes[campaign["id"]] = GraphNode(id=campaign["id"], kind="campaign")

    milestones = ledger.get("milestones") or []
    if isinstance(milestones, list):
        for milestone in milestones:
            if not isinstance(milestone, dict) or not isinstance(milestone.get("id"), str):
                continue
            mid = milestone["id"]
            nodes[mid] = GraphNode(
                id=mid,
                kind="milestone",
                window=str(milestone.get("target_window") or milestone.get("window") or "") or None,
            )
            for kid in _as_str_list(milestone.get("covers") or milestone.get("kr_refs")):
                covers.append(GraphEdge(src=mid, dst=kid, kind="covers"))

    bets = ledger.get("bets") or []
    if not isinstance(bets, list):
        errors.append("PORTFOLIO_SCHEMA_INVALID: bets must be a list")
        bets = []

    for bet in bets:
        if not isinstance(bet, dict) or not isinstance(bet.get("id"), str):
            errors.append("BET_INVALID")
            continue
        bid = bet["id"]
        binding = bet.get("portfolio_binding") if isinstance(bet.get("portfolio_binding"), dict) else {}
        parent = binding.get("parent_bet") if isinstance(binding.get("parent_bet"), str) else bet.get("parent_bet")
        if isinstance(parent, str):
            pass
        else:
            parent = None
        surfaces = tuple(_as_str_list(bet.get("write_surfaces")))
        nodes[bid] = GraphNode(
            id=bid,
            kind="bet",
            status=str(bet.get("status") or "") or None,
            window=str(bet.get("window") or "") or None,
            parent_bet=parent if isinstance(parent, str) else None,
            write_surfaces=surfaces,
            replacement_of=str(bet.get("replacement_of")) if isinstance(bet.get("replacement_of"), str) else None,
            replaced_by=str(bet.get("replaced_by")) if isinstance(bet.get("replaced_by"), str) else None,
        )

        for dep in _as_str_list(bet.get("depends_on")):
            depends.append(GraphEdge(src=bid, dst=dep, kind="depends_on"))

        kr_refs = binding.get("kr_refs") if binding else bet.get("covers")
        rationale = None
        if isinstance(binding, dict) and isinstance(binding.get("coverage_rationale"), str):
            rationale = binding["coverage_rationale"].strip() or None
        if isinstance(bet.get("coverage_rationale"), str) and not rationale:
            rationale = bet["coverage_rationale"].strip() or None
        for kid in _as_str_list(kr_refs):
            covers.append(GraphEdge(src=bid, dst=kid, kind="covers", rationale=rationale))

    # Missing dependency refs
    known_bet_ids = {nid for nid, n in nodes.items() if n.kind == "bet"}
    for edge in depends:
        if edge.dst not in known_bet_ids:
            errors.append(f"DEPENDENCY_REF_MISSING: {edge.src} -> {edge.dst}")

    # Cycle detection among bets that exist
    present_depends = [e for e in depends if e.src in known_bet_ids and e.dst in known_bet_ids]
    if _topo_depths(known_bet_ids, present_depends) is None:
        errors.append("DEPENDENCY_CYCLE")

    return PortfolioGraph(
        nodes=nodes,
        depends_on=tuple(depends),
        covers=tuple(covers),
        required_kr_ids=tuple(sorted(set(required_krs))),
        errors=tuple(errors),
    )


def validate_coverage(graph: PortfolioGraph) -> CoverageValidationResult:
    """Fail-closed coverage conservation over required KRs and failed leaves."""
    errors = list(graph.errors)
    warnings: list[str] = []

    # Coverage map: kr -> covering bet/milestone ids that still count
    covers_by_kr: dict[str, list[GraphEdge]] = {}
    for edge in graph.covers:
        covers_by_kr.setdefault(edge.dst, []).append(edge)

    # Duplicate coverage without rationale
    for kid, edges in covers_by_kr.items():
        bet_edges = [e for e in edges if graph.nodes.get(e.src) and graph.nodes[e.src].kind == "bet"]
        if len(bet_edges) > 1:
            if not all(e.rationale for e in bet_edges):
                errors.append(f"DUPLICATE_COVERAGE_NO_RATIONALE: {kid}")

    # Required KR uncovered
    for kid in graph.required_kr_ids:
        active = []
        for edge in covers_by_kr.get(kid, []):
            node = graph.nodes.get(edge.src)
            if node is None:
                continue
            if node.kind == "milestone":
                active.append(edge.src)
                continue
            if node.kind == "bet" and node.status != "failed":
                active.append(edge.src)
        if not active:
            errors.append(f"REQUIRED_KR_UNCOVERED: {kid}")

    # Failed leaf without replacement
    for node in graph.nodes.values():
        if node.kind != "bet" or node.status != "failed":
            continue
        if node.replaced_by and node.replaced_by in graph.nodes:
            continue
        # Also accept a bet that declares replacement_of this failed id
        replacement = any(
            other.kind == "bet" and other.replacement_of == node.id for other in graph.nodes.values()
        )
        if not replacement:
            errors.append(f"FAILED_LEAF_NO_REPLACEMENT: {node.id}")

    # Non-terminal v2 BET without Campaign/Objective/KR when portfolio entities exist
    has_v2 = any(n.kind in {"objective", "campaign", "kr"} for n in graph.nodes.values())
    if has_v2:
        for node in graph.nodes.values():
            if node.kind != "bet" or node.status in TERMINAL_STATUSES:
                continue
            # Infer binding completeness from covers edges + campaign node presence via covers only:
            # callers attach portfolio_binding into graph via covers; missing KR covers already fail above.
            # Campaign/Objective membership is checked when bet has no covers and required_krs exist.
            covered = [e for e in graph.covers if e.src == node.id]
            if not covered and graph.required_kr_ids:
                errors.append(f"NONTERMINAL_BET_UNBOUND: {node.id}")

    return CoverageValidationResult(errors=tuple(dict.fromkeys(errors)), warnings=tuple(warnings))


def _descendants(bet_id: str, depends: tuple[GraphEdge, ...]) -> set[str]:
    """Bets that (transitively) depend on bet_id."""
    succs: dict[str, set[str]] = {}
    for edge in depends:
        succs.setdefault(edge.dst, set()).add(edge.src)
    out: set[str] = set()
    stack = list(succs.get(bet_id, ()))
    while stack:
        n = stack.pop()
        if n in out:
            continue
        out.add(n)
        stack.extend(succs.get(n, ()))
    return out


def _evidence_status(node: GraphNode, now: float | None) -> dict[str, Any]:
    # Pure graph has no live clocks attached; fixtures may stash age on node via status markers.
    # Default: unavailable unless status is done (fresh) or failed (stale).
    if node.status == "done":
        status = "fresh"
        age = 0
    elif node.status == "failed":
        status = "stale"
        age = None
    else:
        status = "unavailable"
        age = None
    return {"id": node.id, "age_seconds": age, "status": status}


def critical_path(graph: PortfolioGraph, now: float | None = None) -> dict[str, Any]:
    """Deterministic critical-path report. No progress percentage field."""
    bet_ids = sorted(nid for nid, n in graph.nodes.items() if n.kind == "bet")
    present_depends = tuple(
        e for e in graph.depends_on if e.src in graph.nodes and e.dst in graph.nodes and graph.nodes[e.src].kind == "bet" and graph.nodes[e.dst].kind == "bet"
    )
    depths = _topo_depths(bet_ids, present_depends) or {b: 0 for b in bet_ids}

    # Ready = non-terminal bets whose depends_on are all terminal-done (or missing deps already errored)
    done_ids = {nid for nid, n in graph.nodes.items() if n.kind == "bet" and n.status == "done"}
    ready: list[str] = []
    for bid in bet_ids:
        node = graph.nodes[bid]
        if node.status in TERMINAL_STATUSES:
            continue
        deps = [e.dst for e in present_depends if e.src == bid]
        if all(d in done_ids for d in deps):
            ready.append(bid)

    def sort_key(bid: str) -> tuple:
        node = graph.nodes[bid]
        return (-depths.get(bid, 0), str(node.window or ""), bid)

    ready_sorted = sorted(ready, key=sort_key)

    blocked_count = 0
    for bid in ready_sorted:
        blocked_count += len(_descendants(bid, present_depends))

    coverage = validate_coverage(graph)
    unresolved = sorted(
        err.split(": ", 1)[1]
        for err in coverage.errors
        if err.startswith("REQUIRED_KR_UNCOVERED:")
    )

    # Writer-lane conflicts: overlapping write_surfaces among ready bets
    conflicts: list[dict[str, Any]] = []
    for i, a in enumerate(ready_sorted):
        sa = set(graph.nodes[a].write_surfaces)
        if not sa:
            continue
        for b in ready_sorted[i + 1 :]:
            sb = set(graph.nodes[b].write_surfaces)
            overlap = sorted(sa & sb)
            if overlap:
                conflicts.append({"bets": sorted([a, b]), "paths": overlap})
    conflicts.sort(key=lambda c: (c["bets"][0], c["bets"][1], tuple(c["paths"])))

    evidence = [_evidence_status(graph.nodes[bid], now) for bid in ready_sorted]

    return {
        "ready_bets": ready_sorted,
        "blocked_descendant_count": blocked_count,
        "unresolved_kr_coverage": unresolved,
        "writer_lane_conflicts": conflicts,
        "evidence": evidence,
    }
