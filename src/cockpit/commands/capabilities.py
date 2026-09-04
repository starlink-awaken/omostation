"""cockpit capabilities — 统一能力发现入口 (Agent 感知 9.5/10)。

聚合 CLI 命令 / BOS 服务 / 场景卡 / Journey / 治理工具 到单一发现面，
支持自然语言搜索和任务推荐，输出 JSON 供 Agent 消费。
"""

from __future__ import annotations

import json
import logging
import re
from argparse import Namespace
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_WORKSPACE = Path(__file__).resolve().parents[5]  # commands → cockpit → src → cockpit(proj) → projects → workspace


# ---------------------------------------------------------------------------
# 数据源采集
# ---------------------------------------------------------------------------


def _collect_cli_commands() -> list[dict[str, str]]:
    """从 help_map.GROUPS 采集 CLI 命令清单。"""
    try:
        from cockpit.commands.help_map import GROUPS
    except Exception:
        return []
    items: list[dict[str, str]] = []
    for group_name, _color, rows in GROUPS:
        for row in rows:
            items.append({
                "name": row.name,
                "description": row.blurb,
                "example": row.example,
                "source": "cli",
                "group": group_name,
            })
    return items


def _collect_bos_services() -> list[dict[str, str]]:
    """从 BOS 注册表采集服务清单。"""
    registry = _WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"
    if not registry.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(registry.read_text(encoding="utf-8"))
    except Exception:
        return []
    items: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return items
    for domain, services in data.items():
        if not isinstance(services, list):
            continue
        for svc in services:
            if not isinstance(svc, dict):
                continue
            uri = svc.get("uri", "")
            items.append({
                "name": uri,
                "description": svc.get("description", ""),
                "example": uri,
                "source": "bos",
                "group": f"bos://{domain}/",
                "transport": svc.get("transport", ""),
            })
    return items


def _collect_scene_cards() -> list[dict[str, str]]:
    """从 docs/scene-cards/ 采集场景卡 (支持多文档 YAML)。"""
    cards_dir = _WORKSPACE / "docs" / "scene-cards"
    if not cards_dir.exists():
        return []
    items: list[dict[str, str]] = []
    for f in sorted(cards_dir.glob("*.yaml")):
        try:
            import yaml
            text = f.read_text(encoding="utf-8")
            docs = list(yaml.safe_load_all(text))
            # 找到包含 scene_id 的文档, 否则用第一个
            data = next((d for d in docs if isinstance(d, dict) and "scene_id" in d), docs[0] if docs else None)
        except Exception as exc:
            logging.debug("Skip malformed scene-card %s: %s", f.name, exc)
            continue
        if not isinstance(data, dict):
            continue
        lifecycle = data.get("lifecycle", data.get("status", "unknown"))
        items.append({
            "name": data.get("scene_id", f.stem),
            "description": data.get("goal", data.get("description", data.get("summary", ""))),
            "example": f"cockpit scenario {data.get('scene_id', f.stem)}",
            "source": "scene-card",
            "group": f"lifecycle={lifecycle}",
            "activation": data.get("activation", ""),
        })
    return items


def _collect_journeys() -> list[dict[str, str]]:
    """从 docs/journey-specs/ 采集 Journey (支持多文档 YAML)。"""
    specs_dir = _WORKSPACE / "docs" / "journey-specs"
    if not specs_dir.exists():
        return []
    items: list[dict[str, str]] = []
    for f in sorted(specs_dir.glob("*.yaml")):
        try:
            import yaml
            text = f.read_text(encoding="utf-8")
            docs = list(yaml.safe_load_all(text))
            data = next((d for d in docs if isinstance(d, dict) and "journey_id" in d), docs[0] if docs else None)
        except Exception as exc:
            logging.debug("Skip malformed journey %s: %s", f.name, exc)
            continue
        if not isinstance(data, dict):
            continue
        items.append({
            "name": data.get("journey_id", f.stem),
            "description": data.get("description", data.get("summary", "")),
            "example": f"cockpit journey {data.get('journey_id', f.stem)}",
            "source": "journey",
            "group": "journey",
        })
    return items


def _collect_governance_tools() -> list[dict[str, str]]:
    """从 bin/gac/ 采集治理工具清单。"""
    gac_dir = _WORKSPACE / "bin" / "gac"
    if not gac_dir.exists():
        return []
    items: list[dict[str, str]] = []
    for f in sorted(gac_dir.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logging.debug("Skip unreadable governance tool %s: %s", f.name, exc)
            continue
        # 提取 docstring 第一行作为描述
        m = re.search(r'"""(.*?)"""', text, re.DOTALL)
        desc = m.group(1).strip().split("\n")[0] if m else ""
        items.append({
            "name": f"bin/gac/{f.name}",
            "description": desc,
            "example": f"python3 bin/gac/{f.name} --help",
            "source": "governance",
            "group": "gac",
        })
    return items


def _collect_all() -> list[dict[str, str]]:
    """采集所有能力源。"""
    items: list[dict[str, str]] = []
    items.extend(_collect_cli_commands())
    items.extend(_collect_bos_services())
    items.extend(_collect_scene_cards())
    items.extend(_collect_journeys())
    items.extend(_collect_governance_tools())
    return items


# ---------------------------------------------------------------------------
# 搜索与推荐
# ---------------------------------------------------------------------------


def _search_capabilities(items: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    """自然语言搜索能力 (关键词匹配 + 权重排序, OR 逻辑)。"""
    # 支持中英文混合分词: 按空格分 + 2-4字滑动窗口
    raw_terms = [t.strip().lower() for t in re.split(r"\s+", query) if t.strip()]
    terms: list[str] = []
    for t in raw_terms:
        terms.append(t)
        # 对长词添加子串匹配 (中文)
        if len(t) > 4:
            for i in range(len(t) - 1):
                for j in range(2, min(5, len(t) - i + 1)):
                    sub = t[i:i+j]
                    if sub not in terms:
                        terms.append(sub)
    if not terms:
        return items
    scored: list[tuple[int, dict[str, str]]] = []
    for item in items:
        haystack = " ".join(
            str(v) for v in item.values() if isinstance(v, str)
        ).lower()
        score = sum(2 if t in haystack else 0 for t in raw_terms)  # 完整词权重2
        score += sum(1 for t in terms if t not in raw_terms and t in haystack)  # 子串权重1
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: (-x[0], x[1].get("source", "")))
    return [s[1] for s in scored]


def _recommend_for_task(items: list[dict[str, str]], task: str) -> list[dict[str, str]]:
    """基于任务描述推荐能力 (按来源优先级排序)。"""
    task_lower = task.lower()
    source_priority: list[str] = []
    if any(k in task_lower for k in ["研究", "调研", "search", "research", "论文", "paper"]):
        source_priority = ["cli", "scene-card", "journey", "bos", "governance"]
    elif any(k in task_lower for k in ["公文", "审查", "review", "审批", "document"]):
        source_priority = ["scene-card", "cli", "journey", "bos", "governance"]
    elif any(k in task_lower for k in ["治理", "检查", "audit", "governance", "合规"]):
        source_priority = ["governance", "cli", "bos", "scene-card", "journey"]
    elif any(k in task_lower for k in ["记忆", "笔记", "memory", "knowledge", "知识"]):
        source_priority = ["cli", "bos", "scene-card", "journey", "governance"]
    elif any(k in task_lower for k in ["项目", "交付", "project", "deliver"]):
        source_priority = ["scene-card", "journey", "cli", "bos", "governance"]
    else:
        source_priority = ["cli", "scene-card", "bos", "journey", "governance"]

    searched = _search_capabilities(items, task)
    # 按来源优先级排序, 同优先级按名称排序
    order = {s: i for i, s in enumerate(source_priority)}
    searched.sort(key=lambda x: (order.get(x.get("source", ""), 99), x.get("name", "")))
    # 去重 (按 name+source)
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for s in searched:
        key = f"{s.get('source')}:{s.get('name')}"
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique[:10]


# ---------------------------------------------------------------------------
# CLI 命令处理
# ---------------------------------------------------------------------------


def cmd_capabilities(args: Namespace) -> int:
    """统一能力发现入口 — 搜索 / 推荐 / 全量列出。"""
    from cockpit.domain.exit_codes import ExitCode

    console = Console()
    subcmd = getattr(args, "capabilities_command", "list")
    as_json = getattr(args, "json", False) or getattr(args, "global_output", "text") == "json"
    is_dry_run = getattr(args, "dry_run", False)
    query = getattr(args, "query", "") or ""
    task = getattr(args, "task", "") or ""
    source = getattr(args, "source", "") or ""
    limit = getattr(args, "limit", None) or 50

    items = _collect_all()

    # 统计各源数量
    src_counts: dict[str, int] = {}
    for it in items:
        src_counts[it.get("source", "?")] = src_counts.get(it.get("source", "?"), 0) + 1

    # 预检模式
    if is_dry_run:
        payload = {
            "dry_run": True,
            "total_capabilities": len(items),
            "source_distribution": src_counts,
            "ready": True,
        }
        if as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            console.print("[bold cyan]🔍 [Dry-Run] 预检系统统一能力分布[/]")
            console.print(f"  • 总计能力项: [cyan]{len(items)}[/]")
            for src, cnt in sorted(src_counts.items()):
                console.print(f"    - [green]{src}[/]: {cnt} 项")
        return ExitCode.SUCCESS

    if source:
        items = [it for it in items if it.get("source") == source]

    if subcmd == "search" and query:
        items = _search_capabilities(items, query)
    elif subcmd == "recommend" and task:
        items = _recommend_for_task(items, task)

    # 截取 limit
    items = items[:limit]

    # JSON 输出 (Agent 消费)
    if as_json:
        print(json.dumps({
            "total": len(items),
            "query": query or task,
            "source_filter": source or None,
            "capabilities": items,
        }, ensure_ascii=False, indent=2))
        return ExitCode.SUCCESS


    console.print(
        Panel.fit(
            f"[bold bright_cyan]🛸 cockpit 统一能力发现[/]\n"
            f"[dim]共 {len(items)} 项能力 · "
            f"CLI={src_counts.get('cli', 0)} BOS={src_counts.get('bos', 0)} "
            f"Scene={src_counts.get('scene-card', 0)} Journey={src_counts.get('journey', 0)} "
            f"Governance={src_counts.get('governance', 0)}[/]",
            border_style="bright_cyan",
        )
    )

    if subcmd == "recommend" and task:
        console.print(f"\n[bold]任务:[/] {task}")
        console.print("[dim]按相关性排序，最多展示 10 项[/]\n")
    elif subcmd == "search" and query:
        console.print(f"\n[bold]搜索:[/] {query}")
        console.print(f"[dim]匹配 {len(items)} 项[/]\n")

    if not items:
        console.print("[yellow]未匹配到能力，请尝试其他关键词[/]")
        return 0

    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("能力", style="cyan", min_width=20, max_width=40)
    table.add_column("来源", style="green", width=10)
    table.add_column("描述", min_width=30, max_width=60)
    table.add_column("示例", style="dim", min_width=20, max_width=40)
    for it in items[:50]:
        table.add_row(
            it.get("name", ""),
            it.get("source", ""),
            it.get("description", "")[:80],
            it.get("example", "")[:50],
        )
    console.print(table)

    if len(items) > 50:
        console.print(f"\n[dim]... 还有 {len(items) - 50} 项，用 --json 查看完整列表[/]")

    console.print("\n[dim]用法: cockpit capabilities search <关键词> | recommend <任务描述> | list --json[/]")
    return 0
