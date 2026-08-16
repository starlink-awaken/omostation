"""Eidos visualization — render ontology structures as Mermaid diagrams.

Zero external dependencies. Output is Mermaid markdown text.
"""

from __future__ import annotations

from typing import Any


def escape(s: str) -> str:
    """Escape special chars for Mermaid node labels."""
    return s.replace('"', "'").replace("\n", " ")


def render_class_diagram(
    class_name: str,
    fields: list[dict[str, str]],
) -> str:
    """Render a class diagram for a Schema or type definition.

    Args:
        class_name: The class/type name
        fields: List of {name, type, description} dicts

    Returns:
        Mermaid classDiagram text
    """
    lines = ["classDiagram"]
    lines.append(f"  class {escape(class_name)} {{")

    for f in fields:
        ftype = f.get("type", "str")
        fname = f.get("name", "?")
        desc = f.get("description", "")
        if desc:
            lines.append(f"    +{escape(ftype)} {escape(fname)}  // {escape(desc)}")
        else:
            lines.append(f"    +{escape(ftype)} {escape(fname)}")

    lines.append("  }")
    return "\n".join(lines)


def render_ontology_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    title: str = "",
) -> str:
    """Render an ontology as a directed graph.

    Args:
        nodes: List of {id, label, type} dicts
        edges: List of {source, target, label} dicts
        title: Optional graph title

    Returns:
        Mermaid graph TD text
    """
    lines = ["graph TD"]

    # Add nodes
    for n in nodes:
        nid = escape(n.get("id", "?"))
        label = escape(n.get("label", nid))
        ntype = n.get("type", "")
        if ntype:
            label = f"{ntype}: {label}"
        lines.append(f'  {nid}["{label}"]')

    # Add edges
    for e in edges:
        src = escape(e.get("source", "?"))
        tgt = escape(e.get("target", "?"))
        label = escape(e.get("label", ""))
        if label:
            lines.append(f"  {src} -->|{label}| {tgt}")
        else:
            lines.append(f"  {src} --> {tgt}")

    return "\n".join(lines)


def render_state_diagram(
    states: list[str],
    transitions: list[dict[str, str]],
    initial: str = "",
) -> str:
    """Render a state machine as a state diagram.

    Args:
        states: List of state names
        transitions: List of {from, to, trigger} dicts
        initial: Optional initial state marker

    Returns:
        Mermaid stateDiagram text
    """
    lines = ["stateDiagram-v2"]

    if initial and initial in states:
        lines.append(f"  [*] --> {escape(initial)}")

    for t in transitions:
        f = escape(t.get("from", ""))
        to = escape(t.get("to", ""))
        trigger = escape(t.get("trigger", ""))
        if trigger:
            lines.append(f"  {f} --> {to} : {trigger}")
        else:
            lines.append(f"  {f} --> {to}")

    return "\n".join(lines)


def render_pipeline(
    steps: list[dict[str, str]],
) -> str:
    """Render a pipeline as a flow chart.

    Args:
        steps: List of {name, description} dicts in order

    Returns:
        Mermaid flowchart LR text
    """
    lines = ["flowchart LR"]

    for i, step in enumerate(steps):
        node_id = f"S{i}"
        name = escape(step.get("name", f"Step {i}"))
        desc = escape(step.get("description", ""))
        if desc:
            lines.append(f'  {node_id}["{name}: {desc}"]')
        else:
            lines.append(f'  {node_id}["{name}"]')

    # Wire them up
    for i in range(len(steps) - 1):
        lines.append(f"  S{i} --> S{i + 1}")

    return "\n".join(lines)


FORMATS: dict[str, Any] = {
    "class": render_class_diagram,
    "graph": render_ontology_graph,
    "state": render_state_diagram,
    "pipeline": render_pipeline,
}


def render(viz_type: str, **kwargs: Any) -> str:
    """Convenience wrapper — render any diagram by type.

    Args:
        viz_type: "class" | "graph" | "state" | "pipeline"
        **kwargs: Passed to the specific render function

    Returns:
        Mermaid markdown string
    """
    func = FORMATS.get(viz_type)
    if not func:
        raise ValueError(f"Unknown viz type: {viz_type}. Use: {list(FORMATS.keys())}")
    result = func(**kwargs)
    return f"```mermaid\n{result}\n```"
