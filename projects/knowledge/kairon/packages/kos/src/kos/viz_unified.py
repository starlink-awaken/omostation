#!/usr/bin/env python3
# ruff: noqa
"""G4: 统一可视化接口 — 聚合 kos graph (ontology 关系) + eidos viz (类/本体/状态/管线).

场景覆盖审计 G4 缺口实现 (可视化统一前端).
现状: kos graph (Mermaid LR 关系图) + eidos viz (Mermaid TD 类图/本体/状态/管线), 分散无统一入口.
本模块: 统一可视化 render 接口 (按类型路由 kos graph / eidos viz), 输出统一 Mermaid 格式.
"""

from __future__ import annotations

from typing import Any

VIZ_TYPES = ("ontology", "class", "state", "pipeline", "memory")


def render_unified(viz_type: str, **kwargs: Any) -> str:
    """统一可视化 render — 按 viz_type 路由到 kos graph 或 eidos viz.

    Args:
        viz_type: ontology (kos graph 关系) / class / state / pipeline / memory (eidos viz).
        **kwargs: 传给底层 renderer (entity_type 等).

    Returns:
        Mermaid 文本.
    """
    if viz_type == "ontology":
        from kos.ontology.ops import graph

        result = graph(kwargs.get("entity_type"))
        return result.get("graph", "")
    elif viz_type in ("class", "state", "pipeline"):
        from eidos.viz import render  # type: ignore[import-untyped]

        # eidos renderer 是对象级 (需 class_name/fields/state_data 等参数), 非系统级无参.
        # G4 半成品: 系统全景需数据获取层补全; 无数据时返回 help 不 crash.
        safe = {k: v for k, v in kwargs.items() if k != "entity_type"}
        try:
            return render(viz_type, **safe)
        except TypeError:
            return (
                f"%% {viz_type} viz 是对象级渲染, 需数据参数 (如 class_name+fields). "
                f"直接调 eidos.viz.render('{viz_type}', ...). 系统全景待数据获取层补全 (G4 TODO)."
            )
    elif viz_type == "memory":
        from eidos.viz import render_ontology_graph  # type: ignore[import-untyped]

        safe = {k: v for k, v in kwargs.items() if k != "entity_type"}
        try:
            return render_ontology_graph(**safe)
        except TypeError:
            return "%% memory viz 需 nodes+edges 数据参数. 系统全景待数据获取层补全 (G4 TODO)."
    return f"%% Unknown viz_type: {viz_type}. Supported: {VIZ_TYPES}"


def list_viz_types() -> list[str]:
    """列出支持的 viz_type."""
    return list(VIZ_TYPES)


def render_all(entity_type: str | None = None) -> dict[str, str]:
    """渲染所有 viz_type (全景可视化, 供 cockpit UI 一次性获取).

    Returns:
        Dict viz_type → Mermaid 文本 (失败的标 render failed).
    """
    result: dict[str, str] = {}
    for vt in VIZ_TYPES:
        try:
            if vt == "ontology":
                result[vt] = render_unified("ontology", entity_type=entity_type)
            else:
                result[vt] = render_unified(vt)
        except Exception as e:
            result[vt] = f"%% render failed: {e}"
    return result


def main() -> None:
    """CLI: kos viz-unified — 列支持的 viz_type."""
    print(f"Supported viz types: {list_viz_types()}")


if __name__ == "__main__":
    main()
