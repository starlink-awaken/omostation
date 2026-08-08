#!/usr/bin/env python3
"""check-dashboard-registry-consistency: debt-dashboard vs debt.yaml 一致性检测 (ISC-12).

治本 A1 (ISC-12): dashboard.debt_categories.*.partial 之和 必须等于 registry 中
lifecycle_state=partial 的 item 数. 不一致 → 看板停更或漂移 (ISC-50 看板分裂症状).

用法:
  python bin/ssot/check-dashboard-registry-consistency.py   # 不一致 exit 1
"""
from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
DASHBOARD = WORKSPACE / ".omo" / "_control" / "debt-dashboard" / "current.yaml"
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "debt.yaml"


def _load_yaml_aware(path: Path) -> dict:
    """加载 yaml (含 _truth/ frontmatter 多文档, 取正文最后一个 dict)."""
    if not path.is_file():
        return {}
    try:
        import yaml  # noqa: PLC0415
        docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]
        return docs[-1] if docs else {}
    except Exception:  # noqa: BLE001
        return {}


def main() -> int:
    dash = _load_yaml_aware(DASHBOARD)
    reg = _load_yaml_aware(REGISTRY)

    # dashboard 端: 所有 debt_categories 的 partial 之和
    categories = dash.get("debt_categories") or {}
    dash_partial = sum(
        (cat or {}).get("partial", 0) if isinstance(cat, dict) else 0
        for cat in categories.values()
    )

    # registry 端: lifecycle_state=partial 的 item 数
    items = reg.get("items") or []
    reg_partial = sum(
        1 for it in items
        if isinstance(it, dict) and it.get("lifecycle_state") == "partial"
    )

    if dash_partial == reg_partial:
        print(f"✅ dashboard-registry consistency: partial={dash_partial} (一致)")
        return 0
    print(f"❌ dashboard-registry 不一致: dashboard partial={dash_partial} vs registry partial={reg_partial}")
    print(f"   治本: 看 ISC-50 (两套看板 SSOT 统一 ADR) — dashboard 停更或漂移导致 partial 计数分叉")
    return 1


if __name__ == "__main__":
    sys.exit(main())
