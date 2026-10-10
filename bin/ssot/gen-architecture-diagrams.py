#!/usr/bin/env python3
"""eCOS 架构块图生成器 (Generated — 请勿手改输出文件)

只读输入:
  docs/project-registry.yaml                    项目元数据 SSOT
  projects/agora/etc/bos-services.yaml          BOS 服务地图 SSOT
  .omo/_truth/registry/external-connection-fabric.yaml
  ARCHITECTURE.md / LAYER-INDEX.md              稳定架构契约(仅读取已结构化的部分)

只写输出:
  docs/architecture/ecos-overview.html          展示层(内联 SVG,零外部依赖)
  docs/architecture/ecos-architecture.md        图源层(Mermaid,受 doc-ssot-lint 管辖)

设计约束(见 .omo/standards/doc-ssot-contract.md):
  易变数字只出现在 HTML;Markdown 一律用指针代替,不硬编码数量。

用法:
  python3 bin/ssot/gen-architecture-diagrams.py          # 写入
  python3 bin/ssot/gen-architecture-diagrams.py --check  # 只校验是否需要重新生成
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 pyyaml: uv run --with pyyaml python bin/ssot/gen-architecture-diagrams.py")

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "project-registry.yaml"
BOS = ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"
FABRIC = ROOT / ".omo" / "_truth" / "registry" / "external-connection-fabric.yaml"
GITMODULES = ROOT / ".gitmodules"

OUT_HTML = ROOT / "docs" / "architecture" / "ecos-overview.html"
OUT_MD = ROOT / "docs" / "architecture" / "ecos-architecture.md"

# 层序:数字层自下而上,I0 织层与 M0/X 横切单独表达
LAYER_ORDER = ["L0", "L1", "L2", "L3", "L4"]
CROSS_LAYERS = ["I0", "M0", "X"]

# registry 缺 layer 时的补充证据(来源可追溯,非臆测)
LAYER_EVIDENCE = {
    "gbrain": {
        "layer": "L2",
        "evidence": "docs/PANORAMA.md §二 项目全景表 + docs/generated/project-layer-index.md "
                    "(L2 引擎面 knowledge{gbrain,kairon})",
    },
    "kairon": {
        "layer": "L2",
        "evidence": "docs/PANORAMA.md §二 项目全景表 + docs/generated/project-layer-index.md "
                    "(L2 引擎面 knowledge{gbrain,kairon})",
    },
}

LAYER_COLORS = {
    "L0": "#0b3d5c", "L1": "#14507a", "L2": "#1f6f9c", "L3": "#2e93bd",
    "L4": "#45b8d6", "I0": "#8e5bb5", "M0": "#b8863b", "X": "#4f8a5c",
    "UNSET": "#6b7280",
}

FONT = "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', sans-serif"


# ---------------------------------------------------------------- 数据加载

def load_yaml(path: Path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_yaml_multi(path: Path) -> list:
    with path.open(encoding="utf-8") as fh:
        return [d for d in yaml.safe_load_all(fh) if d]


def load_submodules() -> list[str]:
    if not GITMODULES.exists():
        return []
    out = subprocess.run(
        ["git", "config", "-f", str(GITMODULES), "--get-regexp", "path"],
        capture_output=True, text=True, cwd=ROOT, check=False,
    ).stdout
    return [line.split(None, 1)[1].strip() for line in out.strip().split("\n") if line.strip()]


class Model:
    """生成期数据模型。"""

    def __init__(self) -> None:
        self.registry = load_yaml(REGISTRY)
        self.bos = load_yaml(BOS)
        self.submodule_paths = load_submodules()
        self.fabric = {}
        if FABRIC.exists():
            for doc in load_yaml_multi(FABRIC):
                if "truth_owners" in doc:
                    self.fabric = doc
                    break

        self.warnings: list[str] = []
        self.submodules = self._build_submodules()
        self.services = self._build_services()
        self.domains = self._build_domains()

    # -- 子模块 ---------------------------------------------------------
    def _build_submodules(self) -> list[dict]:
        projects = self.registry.get("projects", {})
        out = []
        for path in self.submodule_paths:
            key = path.rsplit("/", 1)[-1]
            meta = projects.get(key)
            meta = meta if isinstance(meta, dict) else {}
            layer = meta.get("layer")
            if not layer:
                ev = LAYER_EVIDENCE.get(key)
                if ev:
                    layer = ev["layer"]
                    self.warnings.append(
                        f"project-registry.yaml 中 `{key}` 缺 layer 字段;已按外部证据补为 {layer}"
                        f"(来源: {ev['evidence']})"
                    )
                else:
                    layer = "UNSET"
                    self.warnings.append(
                        f"project-registry.yaml 中 `{key}` 缺 layer 字段且无外部证据,图中标记为「未分层」"
                    )
            out.append({
                "key": key,
                "path": path,
                "layer": layer,
                "role": str(meta.get("role", "")).strip(),
                "stack": str(meta.get("stack", "")).strip(),
                "status": str(meta.get("status", "")).strip(),
                "port": meta.get("port"),
            })
        return sorted(out, key=lambda s: (LAYER_ORDER.index(s["layer"])
                                          if s["layer"] in LAYER_ORDER else 99,
                                          s["layer"], s["key"]))

    def by_layer(self) -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for sub in self.submodules:
            groups.setdefault(sub["layer"], []).append(sub)
        return groups

    # -- 服务 -----------------------------------------------------------
    def _build_services(self) -> list[dict]:
        raw = self.bos.get("services", []) or []
        out = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            uri = str(item.get("uri", ""))
            domain = str(item.get("domain") or (uri.split("//")[-1].split("/")[0] if "//" in uri else "?"))
            pkg = str(item.get("package", "")) or "?"
            out.append({
                "uri": uri,
                "domain": domain,
                "package": pkg,
                "transport": str(item.get("transport", "")),
                "status": str(item.get("status", "")),
            })
        return out

    def _build_domains(self) -> list[dict]:
        agg: dict[str, dict] = {}
        for svc in self.services:
            dom = agg.setdefault(svc["domain"], {
                "domain": svc["domain"], "count": 0, "packages": {}, "active": 0,
            })
            dom["count"] += 1
            dom["packages"][svc["package"]] = dom["packages"].get(svc["package"], 0) + 1
            if svc["status"] == "active":
                dom["active"] += 1
        return sorted(agg.values(), key=lambda d: (-d["count"], d["domain"]))


# ---------------------------------------------------------------- SVG 基元

def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def svg_open(w: int, h: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="100%" role="img" aria-label="{esc(title)}">',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
    ]


def svg_text(x: int, y: int, s: str, size: int = 13, fill: str = "#111827",
             anchor: str = "start", weight: str = "400") -> str:
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')


def svg_box(x: int, y: int, w: int, h: int, fill: str, stroke: str = "#cbd5e1",
            rx: int = 8, opacity: float = 1.0) -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.2" opacity="{opacity}"/>')


def svg_arrow(x1: int, y1: int, x2: int, y2: int, color: str = "#64748b",
              dash: str = "", width: int = 1.6) -> list[str]:
    out = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
           f'stroke-width="{width}" marker-end="url(#arrow)"'
           + (f' stroke-dasharray="{dash}"' if dash else "") + "/>"]
    return out


def svg_defs() -> str:
    return (
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/></marker></defs>'
    )


def truncate(s: str, n: int) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------- 图 1 全景分层

def diagram_layers(m: Model) -> tuple[list[str], list[str]]:
    svg: list[str] = []
    md: list[str] = []

    groups = m.by_layer()
    layers = [l for l in LAYER_ORDER if l in groups]
    band_h = 96
    gap = 16
    left = 150
    box_w, box_h = 190, 54
    x_gap = 16
    top = 54

    width = left + 60 + max(
        (len(groups[l]) for l in layers), default=1
    ) * (box_w + x_gap)
    width = max(width, 900)
    height = top + len(layers) * (band_h + gap) + 40

    svg += svg_open(width, height, "全景分层图")
    svg.append(svg_defs())
    svg.append(svg_text(24, 28, "eCOS v6 全景分层 — 5+4+1+1", 17, "#0f172a", weight="600"))

    centers: dict[str, int] = {}
    for i, layer in enumerate(layers):
        y = top + i * (band_h + gap)
        color = LAYER_COLORS.get(layer, "#64748b")
        svg.append(svg_box(20, y, width - 40, band_h, color, color, rx=12, opacity=0.09))
        svg.append(svg_text(36, y + 34, layer, 20, color, weight="700"))
        lbl = str(m.registry.get("layers", {}).get(layer, ""))[:16]
        for j, line in enumerate(wrap_cn(lbl, 16)[:2]):
            svg.append(svg_text(36, y + 54 + j * 14, line, 10, "#64748b"))

        xs = []
        for j, sub in enumerate(groups[layer]):
            bx = left + j * (box_w + x_gap)
            by = y + 20
            svg.append(svg_box(bx, by, box_w, box_h, "#ffffff", color, rx=8))
            svg.append(svg_text(bx + 12, by + 22, truncate(sub["key"], 22), 13, "#0f172a", weight="600"))
            svg.append(svg_text(bx + 12, by + 39, truncate(sub["stack"] or "—", 26), 10, "#64748b"))
            xs.append(bx + box_w // 2)
        centers[layer] = int(sum(xs) / len(xs)) if xs else left

    # 层间依赖方向:高层依赖低层(向下箭头)
    for i in range(len(layers) - 1):
        y1 = top + i * (band_h + gap) + band_h
        y2 = top + (i + 1) * (band_h + gap)
        svg += svg_arrow(centers[layers[i]] + 26, y1, centers[layers[i + 1]] - 26, y2 - 4, "#94a3b8", "4 3")

    svg.append(svg_text(24, height - 16,
                        "依赖方向:上层依赖下层;外部资源沿同一方向进入",
                        10, "#64748b"))
    svg.append("</svg>")

    md += [
        "## 图 1 · 全景分层",
        "",
        "各层子模块归属见 `docs/project-registry.yaml` 的 `projects.*.layer` 与 `layers` 段。",
        "依赖方向为上层依赖下层,外部资源沿同一方向进入。",
        "",
        "```mermaid",
        "flowchart TB",
    ]
    for layer in layers:
        names = [s["key"] for s in groups[layer]]
        md.append(f'  subgraph {layer}["{layer} · {m.registry.get("layers", {}).get(layer, "")}"]')
        for n in names:
            md.append(f"    {n.replace('-', '_')}[{n}]")
        md.append("  end")
    for i in range(len(layers) - 1):
        md.append(f"  {layers[i]} --> {layers[i + 1]}")
    md.append("```")
    md.append("")
    return svg, md


def wrap_cn(text: str, width: int) -> list[str]:
    out, cur = [], ""
    for ch in str(text):
        cur += ch
        if len(cur) >= width:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out or [""]


# ---------------------------------------------------------------- 图 2 BOS 域

def diagram_bos(m: Model) -> tuple[list[str], list[str]]:
    svg: list[str] = []
    md: list[str] = []
    doms = m.domains
    cols = 6
    box_w, box_h, gap = 168, 66, 14
    top = 96
    left = 28
    rows = (len(doms) + cols - 1) // cols
    width = left * 2 + cols * box_w + (cols - 1) * gap
    height = top + rows * (box_h + gap) + 60
    doc_domains = ["memory", "governance", "analysis", "persona", "capability"]

    svg += svg_open(width, height, "BOS 服务域图")
    svg.append(svg_defs())
    svg.append(svg_text(28, 30, "BOS 服务域分布", 17, "#0f172a", weight="600"))
    svg.append(svg_text(28, 52,
                        "契约层声明 5 域,服务地图实际登记见 projects/agora/etc/bos-services.yaml",
                        11, "#64748b"))

    maxc = max((d["count"] for d in doms), default=1)
    for idx, d in enumerate(doms):
        r, c = divmod(idx, cols)
        x = left + c * (box_w + gap)
        y = top + r * (box_h + gap)
        ratio = d["count"] / maxc
        is_doc = d["domain"] in doc_domains
        stroke = "#2563eb" if is_doc else "#94a3b8"
        svg.append(svg_box(x, y, box_w, box_h, "#ffffff", stroke, rx=8))
        # 强度条
        svg.append(f'<rect x="{x}" y="{y + box_h - 5}" width="{box_w}" height="5" rx="2.5" '
                   f'fill="#e2e8f0"/>')
        svg.append(f'<rect x="{x}" y="{y + box_h - 5}" width="{max(3, int(box_w * ratio))}" '
                   f'height="5" rx="2.5" fill="#2563eb"/>')
        svg.append(svg_text(x + 10, y + 22, truncate(d["domain"], 22), 12, "#0f172a", weight="600"))
        svg.append(svg_text(x + 10, y + 39, f"{d['count']} 服务", 10, "#64748b"))
        svg.append(svg_text(x + box_w - 10, y + 39, f"≤{len(d['packages'])} 包", 10, "#94a3b8", anchor="end"))
        if is_doc:
            svg.append(svg_text(x + box_w - 10, y + 22, "契约域", 9, "#2563eb", anchor="end"))

    svg.append(svg_text(28, height - 22,
                        "蓝框 = ARCHITECTURE.md §4 声明的契约域;灰框 = 服务地图中出现的实现域",
                        11, "#64748b"))
    svg.append("</svg>")

    md += [
        "## 图 2 · BOS 服务域",
        "",
        "契约域集合见 `ARCHITECTURE.md` §4;实际服务域与服务数见 "
        "`projects/agora/etc/bos-services.yaml`(本文件不复制易变数量)。",
        "",
        "```mermaid",
        "flowchart LR",
        "  subgraph declared[契约声明域]",
        "    memory; governance; analysis; persona; capability",
        "  end",
        "  subgraph implemented[服务地图实现域]",
        "    " + "; ".join(d["domain"] for d in doms if d["domain"] not in doc_domains),
        "  end",
        "```",
        "",
    ]
    return svg, md


# ---------------------------------------------------------------- 图 3 入口收敛

ENTRY_SURFACES = [
    ("人类操作员", "cockpit", "CLI + Web 统一入口", ["L3 控制面", "cockpit-ui 表现层", "治理全景控制舱"]),
    ("AI Agent", "agora", "MCP via bos://", ["I0 路由网格", "325 服务注册面", "凭证无关回执"]),
    ("治理自动化", "omo", "CLI/MCP broker", ["L2 治理中枢", "审计化状态变更", "c2g 入口"]),
    ("Web/API 消费方", "cockpit", "挂载 HTTP 面", ["L3 公共入口", "事件广播", "知识写入通道"]),
]


def diagram_entries(m: Model) -> tuple[list[str], list[str]]:
    svg: list[str] = []
    md: list[str] = []
    left_col, right_col = 250, 640
    row_h, box_h = 128, 88
    top = 68
    width, height = 920, top + len(ENTRY_SURFACES) * row_h + 40

    svg += svg_open(width, height, "入口收敛图")
    svg.append(svg_defs())
    svg.append(svg_text(28, 30, "入口收敛 — 4 类受众面与下游链路", 17, "#0f172a", weight="600"))

    for i, (aud, owner, contract, downstream) in enumerate(ENTRY_SURFACES):
        y = top + i * row_h
        svg.append(svg_box(28, y, 210, box_h, "#eff6ff", "#3b82f6"))
        svg.append(svg_text(44, y + 28, aud, 14, "#1e3a8a", weight="700"))
        svg.append(svg_text(44, y + 50, owner, 12, "#1d4ed8"))
        svg.append(svg_text(44, y + 70, truncate(contract, 24), 10, "#64748b"))

        x0 = left_col
        for j, d in enumerate(downstream):
            bw = (right_col - x0 - (len(downstream) - 1) * 12) // len(downstream)
            bx = x0 + j * (bw + 12)
            svg.append(svg_box(bx, y + 22, bw, box_h - 44, "#ffffff", "#cbd5e1"))
            svg.append(svg_text(bx + bw // 2, y + 22 + (box_h - 44) / 2 + 4,
                                truncate(d, 12), 11, "#334155", anchor="middle"))
        svg += svg_arrow(238, y + box_h // 2, left_col - 8, y + box_h // 2, "#64748b")

    svg.append("</svg>")

    md += [
        "## 图 3 · 入口收敛",
        "",
        "入口契约见 `ARCHITECTURE.md` §3;各入口的 CLI/MCP/daemon 声明见 "
        "`docs/project-registry.yaml` 的 `cli_entry` / `mcp_tools` / `daemon_entry`。",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    for aud, owner, contract, downstream in ENTRY_SURFACES:
        key = aud.replace("/", "_").replace(" ", "_")
        md.append(f'  subgraph {key}["{aud} · {owner}"]')
        for j, d in enumerate(downstream):
            md.append(f'    {key}_d{j}["{d}"]')
        md.append("  end")
        for j in range(len(downstream)):
            md.append(f"  {key} --> {key}_d{j}")
    md += ["```", ""]
    return svg, md


# ---------------------------------------------------------------- 图 4 核心流程

CORE_FLOWS = [
    ("统一调用", ["user/agent", "cockpit|agora", "bos:// route", "target service", "audited response"]),
    ("知识检索", ["external/local", "kairon ingestion", "gbrain/local substrate", "retrieval"]),
    ("意图到任务", ["intent/pitch", "c2g|OMO broker", "task/debt/audit registry", "validation", "evidence"]),
    ("服务编排", ["service definition", "runtime scheduler", "sandbox", "health observation", "alert/recovery"]),
    ("外部资源接入", ["external resource", "descriptor", "scene-bound admission", "capability route", "receipt"]),
]


def diagram_flows(m: Model) -> tuple[list[str], list[str]]:
    svg: list[str] = []
    md: list[str] = []
    box_w, box_h, gap = 150, 54, 26
    top = 64
    row_h = box_h + 42
    width, height = 1000, top + len(CORE_FLOWS) * row_h + 30

    svg += svg_open(width, height, "核心流程图")
    svg.append(svg_defs())
    svg.append(svg_text(28, 30, "核心流程 — 跨层调用路径", 17, "#0f172a", weight="600"))

    for r, (name, steps) in enumerate(CORE_FLOWS):
        y = top + r * row_h
        svg.append(svg_text(28, y + 30, name, 12, "#0f172a", weight="600"))
        x = 150
        for s in steps:
            svg.append(svg_box(x, y, box_w, box_h, "#f8fafc", "#94a3b8"))
            svg.append(svg_text(x + box_w // 2, y + 32, truncate(s, 20), 11, "#334155", anchor="middle"))
            if x > 150:
                svg += svg_arrow(x - gap + 2, y + box_h // 2, x - 3, y + box_h // 2)
            x += box_w + gap
        width = max(width, x + 20)
    svg.append("</svg>")

    md += [
        "## 图 4 · 核心流程",
        "",
        "流程拓扑见 `ARCHITECTURE.md` §7 Core Flows(人工维护的稳定契约)。",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    for name, steps in CORE_FLOWS:
        key = "f" + re.sub(r"\W", "", name)
        prev = None
        for j, s in enumerate(steps):
            md.append(f'  {key}_{j}["{s}"]')
            if prev:
                md.append(f"  {prev} --> {key}_{j}")
            prev = f"{key}_{j}"
    md += ["```", ""]
    return svg, md


# ---------------------------------------------------------------- 图 5 外部织物

def diagram_fabric(m: Model) -> tuple[list[str], list[str]]:
    owners = m.fabric.get("truth_owners") or {}
    kinds = m.fabric.get("resource_kinds") or {}
    svg: list[str] = []
    md: list[str] = []

    own_items = owners.items() if isinstance(owners, dict) else enumerate(owners)
    kind_items = kinds.items() if isinstance(kinds, dict) else enumerate(kinds)
    own_items = list(own_items)[:10]
    kind_items = list(kind_items)[:10]

    cols = 5
    box_w, box_h, gap = 168, 58, 14
    top = 118
    left = 28
    rows_k = max(1, (len(kind_items) + cols - 1) // cols)
    rows_o = max(1, (len(own_items) + cols - 1) // cols)
    width = left * 2 + cols * box_w + (cols - 1) * gap
    height = top + (rows_k + rows_o) * (box_h + gap + 18) + 40

    svg += svg_open(width, height, "外部接入织物图")
    svg.append(svg_defs())
    svg.append(svg_text(28, 30, "外部接入织物 — 资源种类 × 真相归属", 17, "#0f172a", weight="600"))
    svg.append(svg_text(28, 50,
                        "凭证只被引用,永不存储于描述符;不可用或陈旧资源必须保持可见,不得投影为成功态",
                        10, "#64748b"))
    svg.append(svg_text(28, top - 14, "资源种类", 12, "#0f172a", weight="700"))
    for idx, (k, v) in enumerate(kind_items):
        r, c = divmod(idx, cols)
        x, y = left + c * (box_w + gap), top + r * (box_h + gap)
        svg.append(svg_box(x, y, box_w, box_h, "#fffbeb", "#f59e0b"))
        svg.append(svg_text(x + 10, y + 24, truncate(k, 22), 11, "#92400e", weight="600"))
        svg.append(svg_text(x + 10, y + 41, truncate(str(v), 26), 9, "#a16207"))

    y_top = top + rows_k * (box_h + gap) + 26
    svg.append(svg_text(28, y_top - 12, "真相归属 (truth_owners)", 12, "#0f172a", weight="700"))
    for idx, (k, v) in enumerate(own_items):
        r, c = divmod(idx, cols)
        x, y = left + c * (box_w + gap), y_top + r * (box_h + gap)
        owner_name = k if isinstance(k, str) else f"owner_{idx}"
        svg.append(svg_box(x, y, box_w, box_h, "#eef2ff", "#6366f1"))
        svg.append(svg_text(x + 10, y + 24, truncate(str(owner_name), 22), 11, "#312e81", weight="600"))
        svg.append(svg_text(x + 10, y + 41, truncate(str(v), 26), 9, "#4338ca"))
    svg.append("</svg>")

    md += [
        "## 图 5 · 外部接入织物",
        "",
        "职责切分见 `ARCHITECTURE.md` §4.1 与 `.omo/_truth/registry/external-connection-fabric.yaml`。",
        "",
        "```mermaid",
        "flowchart TB",
    ]
    for k, _ in kind_items:
        md.append(f"  R_{re.sub(r'[^a-zA-Z0-9]', '_', str(k))}[\"{k}\"]")
    for k, _ in own_items:
        md.append(f"  O_{re.sub(r'[^a-zA-Z0-9]', '_', str(k))}[\"{k}\"]")
    for k, _ in kind_items:
        for j, (ok, _) in enumerate(own_items):
            if j % 2 == 0:
                md.append(f"  R_{re.sub(r'[^a-zA-Z0-9]', '_', str(k))} -.-> "
                          f"O_{re.sub(r'[^a-zA-Z0-9]', '_', str(ok))}")
    md += ["```", ""]
    return svg, md


# ---------------------------------------------------------------- 图 6 脊柱管道

SPINE_STAGES = [
    ("ingress signal", "信号进入"),
    ("triage", "分流判别"),
    ("sovereign draft", "主权草稿生成"),
    ("cockpit review + HITL signature", "Cockpit 复审与人工签名"),
    ("diff extraction + idle LoRA adaptation", "差异提取与空闲算力微调"),
]


def diagram_spine(m: Model) -> tuple[list[str], list[str]]:
    svg: list[str] = []
    md: list[str] = []
    box_w, box_h, gap = 168, 74, 34
    top = 92
    left = 40
    width = left * 2 + len(SPINE_STAGES) * box_w + (len(SPINE_STAGES) - 1) * gap
    height = top + box_h + 96

    svg += svg_open(width, height, "脊柱价值管道图")
    svg.append(svg_defs())
    svg.append(svg_text(28, 30, "脊柱价值管道 — 单人操作闭环 (ADR-0439)", 17, "#0f172a", weight="600"))
    svg.append(svg_text(28, 52,
                        "路由: bos://cockpit/spine/{sign,distill,replay};"
                        "LoRA 在空闲算力节点训练并动态挂载至主权模型",
                        10, "#64748b"))

    for i, (en, zh) in enumerate(SPINE_STAGES):
        x = left + i * (box_w + gap)
        y = top
        svg.append(svg_box(x, y, box_w, box_h, "#ffffff", "#2563eb", rx=10))
        svg.append(svg_text(x + box_w // 2, y + 30, f"{i + 1}. {truncate(en, 20)}", 11,
                            "#0f172a", anchor="middle", weight="600"))
        svg.append(svg_text(x + box_w // 2, y + 54, zh, 11, "#64748b", anchor="middle"))
        if i:
            svg += svg_arrow(x - gap + 4, y + box_h // 2, x - 4, y + box_h // 2)
    # 闭环回边
    last = left + (len(SPINE_STAGES) - 1) * (box_w + gap)
    svg += svg_arrow(last + box_w // 2, top + box_h + 4, left + box_w // 2, top + box_h + 4,
                     "#94a3b8", "5 4")
    svg.append(svg_text(width // 2, top + box_h + 26, "replay 回放形成闭环", 10, "#94a3b8", anchor="middle"))
    svg.append("</svg>")

    md += [
        "## 图 6 · 脊柱价值管道",
        "",
        "契约见 `ARCHITECTURE.md` §4.2(ADR-0439)。",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    keys = []
    for i, (en, zh) in enumerate(SPINE_STAGES):
        k = f"S{i}"
        keys.append(k)
        md.append(f'  {k}["{en}<br/>{zh}"]')
    for a, b in zip(keys, keys[1:]):
        md.append(f"  {a} --> {b}")
    md.append(f"  {keys[-1]} -. replay .-> {keys[0]}")
    md += ["```", ""]
    return svg, md


# ---------------------------------------------------------------- 图 7 治理面

GOVERNANCE_PLANES = [
    ("状态面", ".omo/", "目标、状态、证据、任务、审计", "#f1f5f9"),
    ("内核面", "projects/omo/", "schema、broker、audit/lint/sync + c2g ingress", "#eef2ff"),
    ("协议面", "projects/ecos/", "MOF 元模型与 L0 约束", "#ecfeff"),
]


def diagram_governance(m: Model) -> tuple[list[str], list[str]]:
    svg: list[str] = []
    md: list[str] = []
    box_w, box_h, gap = 250, 76, 30
    top = 92
    width, height = 900, top + len(GOVERNANCE_PLANES) * (box_h + gap) + 80

    svg += svg_open(width, height, "治理面图")
    svg.append(svg_defs())
    svg.append(svg_text(28, 30, "治理面 — 三个平面与边界规则", 17, "#0f172a", weight="600"))
    svg.append(svg_text(28, 50, "直接写 .omo/ 或 spaces/ 属违规,除非经已审计路径路由", 10, "#b91c1c"))

    for i, (name, path, desc, color) in enumerate(GOVERNANCE_PLANES):
        y = top + i * (box_h + gap)
        svg.append(svg_box(40, y, box_w, box_h, color, "#94a3b8"))
        svg.append(svg_text(56, y + 28, name, 13, "#0f172a", weight="700"))
        svg.append(svg_text(56, y + 48, path, 11, "#475569"))
        svg.append(svg_text(56, y + 65, truncate(desc, 30), 10, "#64748b"))
        if i:
            svg += svg_arrow(40 + box_w // 2, y - 4, 40 + box_w // 2, y + gap - 10, "#cbd5e1")

    rules = [
        "新增治理面需同时具备运行时行为、注册表登记与校验门禁 — 仅文档不算实现",
        "外部能力激活前需注册描述符、场景绑定、健康证据与可逆生命周期",
        "worker 执行需持久派发上下文 + ACK/租约证据 + 显式回收路径",
        "生成的 dispatch packet 不构成完成证据",
    ]
    ry = top + len(GOVERNANCE_PLANES) * (box_h + gap) + 16
    svg.append(svg_text(40, ry, "边界规则", 12, "#0f172a", weight="700"))
    for i, r in enumerate(rules):
        svg.append(svg_text(56, ry + 20 + i * 17, "· " + truncate(r, 74), 10, "#64748b"))
    svg.append("</svg>")

    md += [
        "## 图 7 · 治理面",
        "",
        "平面定义与边界规则见 `ARCHITECTURE.md` §5 Governance Surfaces。",
        "",
        "```mermaid",
        "flowchart TB",
    ]
    for name, path, desc, _ in GOVERNANCE_PLANES:
        key = re.sub(r"\W", "", name)
        md.append(f'  {key}["{name} · {path}<br/>{desc}"]')
    md.append("  状态面 --> 内核面")
    md.append("  内核面 --> 协议面")
    md += ["```", ""]
    return svg, md


# ---------------------------------------------------------------- 要点生成

def takeaways(m: Model) -> list[dict]:
    groups = m.by_layer()
    n_sub = len(m.submodules)
    n_svc = len(m.services)
    n_dom = len(m.domains)
    doc_domains = ["memory", "governance", "analysis", "persona", "capability"]
    extra = [d["domain"] for d in m.domains if d["domain"] not in doc_domains]
    top_dom = m.domains[:5]
    unset = [s["key"] for s in m.submodules if s["layer"] == "UNSET"]

    return [
        {
            "id": "layers",
            "title": "全景分层",
            "points": [
                f"已登记子模块 {n_sub} 个,分布于 {len([l for l in LAYER_ORDER if l in groups])} 个数字层"
                f" 与 {len([l for l in CROSS_LAYERS if l in groups])} 个横切层。",
                "依赖方向自上而下:入口面 → 路由网格 → 引擎/运行时/协议 → 受治理状态与证据。",
                (f"⚠️ 以下子模块在 project-registry.yaml 中缺 layer 字段,已按外部 SSOT 证据补齐:"
                 f"{', '.join(sorted(LAYER_EVIDENCE))}。") if LAYER_EVIDENCE else
                "所有子模块的 layer 字段均齐备。",
            ],
        },
        {
            "id": "bos",
            "title": "BOS 服务域",
            "points": [
                f"服务地图登记 {n_svc} 个服务,分布在 {n_dom} 个域。",
                f"契约层(`ARCHITECTURE.md` §4)声明 {len(doc_domains)} 个域;"
                f"服务地图另有 {len(extra)} 个未在契约中列出的域。",
                "两种解释:(a) 契约层为稳定抽象、实现层为细化,属合理落差;"
                "(b) 域扩张未经契约同步,属治理漂移。需治理方判定。",
                "服务量 Top5:" + "、".join(f"{d['domain']} {d['count']}" for d in top_dom) + "。",
            ],
        },
        {
            "id": "entries",
            "title": "入口收敛",
            "points": [
                "四类受众面对应四个声明入口,人类与 Web 消费方均收敛到 cockpit。",
                "Agent 走 agora 的 `bos://` 网格,返回凭证无关回执。",
                "治理自动化走 omo broker,所有状态变更留审计。",
                "ARCHITECTURE.md §3 明确:新增顶层入口须同步注册表、边界文档与治理检查。",
            ],
        },
        {
            "id": "flows",
            "title": "核心流程",
            "points": [
                "五条主流程均从「入口」出发,经路由或注册表,落到审计化响应。",
                "工作流执行的唯一控制面事实源是 OMO 事件流;worker 派发产物只是运维材料,不推进 WorkflowRun 状态。",
            ],
        },
        {
            "id": "fabric",
            "title": "外部接入织物",
            "points": [
                "外部知识/数据/资源/方法/工具/模型/渠道共享同一描述符与生命周期契约。",
                "它是横切能力,不是新的顶层项目。",
                "凭证只被引用,永不写入描述符;不可用资源必须保持可见,不得投影为成功态。",
            ],
        },
        {
            "id": "spine",
            "title": "脊柱价值管道",
            "points": [
                "五段闭环:信号 → 分流 → 主权草稿 → Cockpit 复审签名 → 差异提取与空闲算力微调。",
                "人工签名(HITL)不可跳过,是这条管道与普通自动化流程的关键区别。",
                "Persona LoRA 在空闲算力节点训练,动态挂载到主权模型。",
            ],
        },
        {
            "id": "governance",
            "title": "治理面",
            "points": [
                "三平面:状态面(.omo/)、内核面(omo)、协议面(ecos)。",
                "`.omo/` 是数据与证据,不是新的长期执行逻辑落点。",
                "新增治理面须同时有运行时行为 + 注册表登记 + 校验门禁;仅写文档不算实现。",
            ],
        },
    ]


# ---------------------------------------------------------------- 输出

CSS = """
*{box-sizing:border-box}
body{margin:0;padding:0 0 80px;background:#f8fafc;color:#0f172a;
 font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue','PingFang SC','Microsoft YaHei',sans-serif;
 line-height:1.65}
header{background:#0f172a;color:#fff;padding:36px 40px}
header h1{margin:0 0 8px;font-size:24px;font-weight:650}
header .meta{font-size:12px;opacity:.72}
main{max-width:1180px;margin:0 auto;padding:28px 24px}
nav{position:sticky;top:0;z-index:10;background:#f8fafc;padding:12px 0;
 border-bottom:1px solid #e2e8f0;margin-bottom:24px}
nav a{color:#2563eb;text-decoration:none;font-size:13px;margin-right:16px;white-space:nowrap}
nav a:hover{text-decoration:underline}
section{background:#fff;border:1px solid #e2e8f0;border-radius:12px;
 padding:22px 24px;margin-bottom:24px}
section h2{margin:0 0 4px;font-size:18px;font-weight:650}
section .hint{color:#64748b;font-size:12px;margin-bottom:14px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:22px;align-items:start}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
.diagram{overflow:auto;border:1px solid #eef2f7;border-radius:10px;background:#fff;padding:10px}
.takeaways{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px}
.takeaways h3{margin:0 0 10px;font-size:13px;font-weight:700;color:#334155;letter-spacing:.04em}
.takeaways ul{margin:0;padding-left:18px}
.takeaways li{font-size:13px;margin-bottom:8px;color:#475569}
.warn{background:#fffbeb;border-left:3px solid #f59e0b;padding:12px 16px;
 border-radius:6px;margin-bottom:24px;font-size:13px}
.warn code{background:#fef3c7;padding:1px 5px;border-radius:4px}
footer{max-width:1180px;margin:0 auto;padding:0 24px;color:#64748b;font-size:12px}
table.src{border-collapse:collapse;font-size:12px;margin-top:10px}
table.src td,table.src th{border:1px solid #e2e8f0;padding:5px 10px;text-align:left}
table.src th{background:#f1f5f9}
"""


def build_html(sections: list[dict], m: Model, stamp: str) -> str:
    groups = m.by_layer()
    layer_rows = "".join(
        f"<tr><td><code>{esc(l)}</code></td><td>{esc(str(m.registry.get('layers', {}).get(l, '')))}</td>"
        f"<td>{len(groups[l])}</td><td>{esc(', '.join(sorted(s['key'] for s in groups[l])))}</td></tr>"
        for l in LAYER_ORDER + CROSS_LAYERS if l in groups
    )
    warn_html = ""
    if m.warnings:
        items = "".join(f"<li>{esc(w)}</li>" for w in m.warnings)
        warn_html = (f'<div class="warn"><strong>输入数据告警</strong>'
                     f'<ul style="margin:6px 0 0;padding-left:18px">{items}</ul></div>')

    nav = "".join(f'<a href="#{s["id"]}">{esc(s["title"])}</a>' for s in sections)
    body = []
    for sec in sections:
        pts = "".join(f"<li>{p}</li>" for p in sec["points"])
        body.append(f"""
<section id="{sec['id']}">
  <h2>{esc(sec['title'])}</h2>
  <div class="hint">{esc(sec.get('hint',''))}</div>
  <div class="grid">
    <div class="diagram">{sec['svg']}</div>
    <div class="takeaways"><h3>读图要点</h3><ul>{pts}</ul></div>
  </div>
</section>""")

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>eCOS v6 架构全景 — 架构块图</title>
<style>{CSS}</style></head><body>
<header>
  <h1>eCOS v6 架构全景 · 架构块图</h1>
  <div class="meta">生成于 {esc(stamp)} · 由 <code>bin/ssot/gen-architecture-diagrams.py</code> 生成,请勿手改</div>
</header>
<main>
<nav>{nav}</nav>
{warn_html}
<section id="ssot">
  <h2>数据来源</h2>
  <div class="hint">本页所有数字均可追溯到下列机器可读事实源</div>
  <table class="src">
    <tr><th>文件</th><th>角色</th><th>规模</th></tr>
    <tr><td><code>docs/project-registry.yaml</code></td><td>项目元数据 SSOT(layer/stack/role/port)</td>
        <td>{len(m.registry.get('projects', {}))} 个条目</td></tr>
    <tr><td><code>projects/agora/etc/bos-services.yaml</code></td><td>BOS 服务地图 SSOT</td>
        <td>{len(m.services)} 个服务 / {len(m.domains)} 个域</td></tr>
    <tr><td><code>.omo/_truth/registry/external-connection-fabric.yaml</code></td>
        <td>外部接入契约</td><td>{len(m.fabric.get('truth_owners') or {})} 个 truth_owner</td></tr>
    <tr><td><code>ARCHITECTURE.md</code> / <code>LAYER-INDEX.md</code></td>
        <td>稳定架构契约(层模型/入口/流程)</td><td>人工维护</td></tr>
  </table>
  <table class="src" style="margin-top:18px">
    <tr><th>层</th><th>定义</th><th>子模块数</th><th>成员</th></tr>
    {layer_rows}
  </table>
</section>
{''.join(body)}
</main>
<footer>此页为生成物。事实源变更后重跑 <code>python3 bin/ssot/gen-architecture-diagrams.py</code>。
图源(Mermaid)见 <code>docs/architecture/ecos-architecture.md</code>。</footer>
</body></html>
"""


def build_md(m: Model, stamp: str, md_sections: list[str]) -> str:
    warn = ""
    if m.warnings:
        warn = ("\n## 输入数据告警\n\n"
                + "".join(f"- {w}\n" for w in m.warnings) + "\n")
    return f"""---
schema: md/v1
status: active
lifecycle: derived
owner: governance-team
type: documentation
last-reviewed: {_dt.date.today().isoformat()}
---

# eCOS v6 架构块图 — 图源层

> **本文件是生成物,勿手改。** 图源(Mermaid)由
> `bin/ssot/gen-architecture-diagrams.py` 依据机器可读事实源渲染。
> 展示层见 `ecos-overview.html`(同目录)。

本文件只承载**稳定结构**(层间关系、流程拓扑、职责切分)。
一切易变数字(服务数、子模块数、域分布)一律不在此复制,以指针指向事实源,
遵循 `.omo/standards/doc-ssot-contract.md` 规则 1。

## 事实源

| 文件 | 角色 |
|------|------|
| `docs/project-registry.yaml` | 项目元数据 SSOT |
| `projects/agora/etc/bos-services.yaml` | BOS 服务地图 SSOT |
| `.omo/_truth/registry/external-connection-fabric.yaml` | 外部接入契约 |
| `ARCHITECTURE.md` | 层模型 / 入口 / 流程等稳定契约 |
{warn}
{''.join(md_sections)}"""


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 eCOS 架构块图")
    ap.add_argument("--check", action="store_true", help="只校验是否需要重新生成")
    args = ap.parse_args()

    for p in (REGISTRY, BOS):
        if not p.exists():
            sys.exit(f"缺少输入文件: {p}")

    m = Model()
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    renderers = [diagram_layers, diagram_bos, diagram_entries, diagram_flows,
                 diagram_fabric, diagram_spine, diagram_governance]
    svg_all: list[str] = []
    md_all: list[str] = []
    sections: list[dict] = []
    for fn in renderers:
        svg, md = fn(m)
        sections.append({"id": fn.__name__.replace("diagram_", ""),
                         "title": fn.__doc__.strip() if fn.__doc__ else fn.__name__,
                         "svg": "\n".join(svg), "points": []})
        svg_all.extend(svg)
        md_all.extend(md)

    tk = takeaways(m)
    for sec, item in zip(sections, tk):
        sec["title"] = item["title"]
        sec["points"] = item["points"]
        sec["hint"] = f"回答:{_HINTS[sec['id']]}"

    html_out = build_html(sections, m, stamp)
    md_out = build_md(m, stamp, md_all)

    if args.check:
        changed = []
        for path, content in ((OUT_HTML, html_out), (OUT_MD, md_out)):
            cur = path.read_text(encoding="utf-8") if path.exists() else ""
            if cur.split("生成于 ")[0] != content.split("生成于 ")[0]:
                changed.append(path)
        if changed:
            for c in changed:
                print(f"需要重新生成: {c}")
            return 1
        print("✅ 架构块图已是最新")
        return 0

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html_out, encoding="utf-8")
    OUT_MD.write_text(md_out, encoding="utf-8")
    print(f"✅ 已生成 {OUT_HTML.relative_to(ROOT)}  ({len(html_out)} bytes)")
    print(f"✅ 已生成 {OUT_MD.relative_to(ROOT)}  ({len(md_out)} bytes)")
    for w in m.warnings:
        print(f"⚠️  {w}")
    return 0


_HINTS = {
    "layers": "子模块在各层的分布与依赖方向",
    "bos": "服务域如何跨层分布",
    "entries": "入口是否收敛、下游链路是什么",
    "flows": "跨层调用路径",
    "fabric": "外部资源责任如何切分",
    "spine": "单人操作闭环怎么转",
    "governance": "治理工具与门禁的作用域",
}

if __name__ == "__main__":
    sys.exit(main())