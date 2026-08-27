"""Best-First Tree Search — type definitions and factory functions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BFTSNode:
    """A single node in the BFTS tree.

    Each node represents a research sub-question at a given depth.
    """

    query: str
    depth: int
    parent: BFTSNode | None = None
    children: list[BFTSNode] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    score: float = 0.0
    status: str = "pending"  # pending | exploring | pruned | completed


def create_root(query: str) -> BFTSNode:
    """Create a root BFTS node at depth 0."""
    return BFTSNode(query=query, depth=0, status="exploring")


def create_child(parent: BFTSNode, query: str) -> BFTSNode:
    """Create a child node and link it to its parent."""
    node = BFTSNode(
        query=query,
        depth=parent.depth + 1,
        parent=parent,
        status="pending",
    )
    parent.children.append(node)
    return node


def collect_completed(node: BFTSNode) -> list[BFTSNode]:
    """Recursively collect all completed nodes from the tree."""
    result: list[BFTSNode] = []
    if node.status == "completed":
        result.append(node)
    for child in node.children:
        result.extend(collect_completed(child))
    return result


def count_nodes(node: BFTSNode) -> dict[str, int]:
    """Count nodes by status in the tree."""
    counts: dict[str, int] = {"total": 0, "pending": 0, "exploring": 0, "pruned": 0, "completed": 0}
    stack = [node]
    while stack:
        current = stack.pop()
        counts["total"] += 1
        counts[current.status] = counts.get(current.status, 0) + 1
        stack.extend(current.children)
    return counts
