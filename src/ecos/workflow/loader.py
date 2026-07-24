"""Workflow Loader — 加载 M1 节点和 definitions 目录的工作流定义

支持优先从 M1 节点目录加载，回退到项目内 definitions/ 目录。
"""

from __future__ import annotations

from pathlib import Path

import yaml

# ── 路径常量 ──

WF_DIR = Path(__file__).parent / "definitions"
M1_WF_DIR = Path(__file__).parent.parent / "ssot" / "mof" / "m1" / "workflow"


# ── 主加载函数 ──


def load_workflow(name: str) -> dict | None:
    """加载工作流定义·优先从 M1 节点目录加载"""
    # 尝试从 M1 节点目录加载
    node = _load_from_m1(name)
    if node:
        return node
    # 回退到 definitions/ 目录
    path = WF_DIR / f"{name}.yaml"
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def _load_from_m1(name: str) -> dict | None:
    """从 M1 Workflow 节点目录加载"""
    if not M1_WF_DIR.exists():
        return None
    name_lower = name.lower()
    for f in sorted(M1_WF_DIR.glob("WORKFLOW-*.yaml")):
        try:
            with open(f) as fh:
                node = yaml.safe_load(fh)
            if not node or node.get("type") != "Workflow":
                continue
            nid = node.get("id", "").lower()
            kebab = nid.replace("workflow-", "").replace("_", "-")
            nname = node.get("name", "").lower()
            # 匹配: 精确ID / kebab名称 / 中文名 / 子串
            if (
                name_lower == nid
                or name_lower == kebab
                or name_lower == nname
                or name_lower in nid
                or name_lower in kebab
            ):
                return node
        except Exception:  # defensive fallback
            continue
    return None


# ── 列表函数 ──


def list_workflows() -> list[dict]:
    """列出所有可用工作流·合并 M1 节点 + definitions"""
    workflows = []
    seen_names: set[str] = set()

    # M1 节点
    if M1_WF_DIR.exists():
        for f in sorted(M1_WF_DIR.glob("WORKFLOW-*.yaml")):
            try:
                with open(f) as fh:
                    node = yaml.safe_load(fh)
                if node and node.get("type") == "Workflow":
                    kebab = node.get("id", "").replace("WORKFLOW-", "").lower()
                    entry = {
                        "name": kebab,
                        "display": node.get("name", kebab),
                        "id": node.get("id"),
                        "source": "m1",
                        "domain": node.get("domain"),
                        "layer": node.get("layer"),
                        "subtype": node.get("subtype"),
                    }
                    workflows.append(entry)
                    seen_names.add(kebab)
            except Exception:  # defensive fallback
                continue

    # definitions/ 目录（去重）
    if WF_DIR.exists():
        for f in WF_DIR.glob("*.yaml"):
            name = f.stem
            if name not in seen_names:
                try:
                    with open(f) as fh:
                        wf = yaml.safe_load(fh)
                    workflows.append(
                        {
                            "name": name,
                            "display": wf.get("name", name),
                            "source": "definition",
                        }
                    )
                    seen_names.add(name)
                except Exception:  # defensive fallback
                    continue

    return workflows


def list_from_m1() -> list[dict]:
    """仅列出 M1 节点的工作流"""
    result = []
    if not M1_WF_DIR.exists():
        return result
    for f in sorted(M1_WF_DIR.glob("WORKFLOW-*.yaml")):
        try:
            with open(f) as fh:
                node = yaml.safe_load(fh)
            if node and node.get("type") == "Workflow":
                result.append(
                    {
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "domain": node.get("domain"),
                        "layer": node.get("layer"),
                        "subtype": node.get("subtype"),
                        "bos_uri": node.get("bos_uri"),
                        "status": node.get("status"),
                        "steps_count": len(node.get("steps", [])),
                    }
                )
        except Exception:  # defensive fallback
            continue
    return result
