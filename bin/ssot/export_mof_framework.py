#!/usr/bin/env python3
"""export_mof_framework.py — MOF 治理框架导出（Wave 3 平台化）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 3:
把 MOF 四层模型 + L0 约束 + 工具链提炼为可复用框架包（模板 + manifest），
供其他项目接入模型驱动治理。

用法:
    python3 bin/ssot/export_mof_framework.py --dest <输出目录>
"""

import argparse
import sys
import shutil
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]

ASSET_GROUPS = {
    "m3": ("projects/ecos/src/ecos/ssot/mof/m3.yaml",),
    "m2": ("projects/ecos/src/ecos/ssot/mof/m2/constraint_l0.yaml",),
    "m1_template": ("projects/ecos/src/ecos/ssot/mof/m1/governance/GOV-CONSTRAINT-L0-INDEX.yaml",),
    "ontology": ("projects/ecos/src/ecos/ssot/mof/ontology.yaml",),
    "l0_source": ("projects/ecos/src/ecos/l0/constraints.yaml",),
    "tool_consumer_index": ("bin/ssot/consumer_index.py",),
    "tool_m0_feedback": ("bin/ssot/m0_feedback.py",),
    "tool_semantic_diff": ("bin/ssot/semantic_diff.py",),
    "tool_inference": ("projects/ecos/bin/inference_engine.py",),
    "tool_graph_query": ("bin/ssot/model_graph_query.py",),
    "tool_corrosion": ("bin/ssot/corrosion_learner.py",),
    "tool_onto_ekg": ("bin/ssot/onto_ekg_bootstrap.py",),
}


def collect_assets() -> list[dict]:
    """收集框架资产：层分组 + 文件信息。"""
    assets = []
    for layer, rels in ASSET_GROUPS.items():
        for rel in rels:
            p = ROOT / rel
            if not p.exists():
                continue
            assets.append({"layer": layer.split("_")[0], "name": p.name,
                           "rel": rel, "size": p.stat().st_size})
    return assets


def build_manifest(assets: list[dict]) -> dict:
    """构建框架 manifest（层计数 + 总资产 + 元信息）。"""
    layers = {}
    for a in assets:
        layers[a["layer"]] = layers.get(a["layer"], 0) + 1
    return {"framework": "mof-governance", "version": "1.0.0",
            "exported_at": datetime.utcnow().isoformat(timespec="seconds"),
            "total_assets": len(assets), "layers": layers}


def export_framework(assets: list[dict], dest: str) -> dict:
    """导出框架包：复制资产到 dest/ + 写 manifest.yaml。"""
    dest_dir = Path(dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for a in assets:
        src = ROOT / a["rel"]
        rel_dest = Path(a["layer"]) / a["name"]
        target = dest_dir / rel_dest
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(str(rel_dest))
    manifest = build_manifest(assets)
    manifest["files"] = copied
    (dest_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest", default="docs/templates/mof-governance",
                    help="框架包输出目录")
    ap.add_argument("--dry-run", action="store_true", help="只打印清单")
    args = ap.parse_args()
    assets = collect_assets()
    if not assets:
        print("[FAIL] 未收集到资产（MOF 源缺失？）", file=sys.stderr)
        return 1
    if args.dry_run:
        manifest = build_manifest(assets)
        print(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False))
        return 0
    manifest = export_framework(assets, args.dest)
    print(f"[OK] 框架包已导出 → {args.dest}（{manifest['total_assets']} 资产）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
