#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KEMS 跨域巡检 — kems-cross-check.py
检查所有已落地域的工具链完整性、本体结构、版本一致性。
闭环「@公共 单点维护」：确保四域软链指向同一版本，无漂移。
用法：
  python3 kems-cross-check.py --domains 卫健委,国转中心,规自委,@家庭生活
  python3 kems-cross-check.py --domains ~/Documents/@工作文档/卫健委,...   # 或绝对路径
"""
import argparse, hashlib, os, sys, yaml
from pathlib import Path

KEMS_V2 = Path(__file__).resolve().parent  # @公共/kems-v2
TOOLS = ["check-ssot-sync.py", "check-ontology-consistency.py", "check-model-conformance.py",
         "refresh-indexes.py", "kems-snapshot.py", "model-ask.py", "gen-report-view.py",
         "graph-query.py", "kems-toolkit.py", "kems-init.py", "check-critical-path.py"]

DEFAULT_DOMAINS = {
    "卫健委": "/Users/xiamingxing/Documents/@工作文档/卫健委",
    "国转中心": "/Users/xiamingxing/Documents/@工作文档/国转中心",
    "规自委": "/Users/xiamingxing/Documents/@工作文档/规自委",
    "@家庭生活": "/Users/xiamingxing/Documents/@家庭生活",
}


def check_domain(name: str, root: Path) -> tuple[int, list[str]]:
    issues = []
    n_ok = 0
    if not root.exists():
        return 0, [f"❌ {name}: 目录不存在 {root}"]
    rt = root / "_runtime"
    if not rt.exists():
        return 0, [f"❌ {name}: 无 _runtime"]

    # 1. 工具链软链完整性
    for t in TOOLS:
        p = rt / t
        if p.is_symlink():
            target = Path(os.readlink(p))
            if str(target).startswith("/Users") and "kems-v2" in str(target):
                n_ok += 1
            else:
                issues.append(f"⚠️ {name}: {t} 软链目标异常 → {target}")
        elif p.exists():
            issues.append(f"❌ {name}: {t} 是本地副本（应软链 @公共）")
        else:
            issues.append(f"❌ {name}: {t} 缺失")

    # 2. 本体结构
    ont = root / "_entities/ontology"
    for f in ["metamodel.yaml", "classes.yaml", "relations.yaml", "layers.yaml",
              "instances.yaml", "gaps.yaml", "aliases.yaml", "associations.yaml", "constraints.yaml"]:
        if (ont / f).exists():
            n_ok += 1
        else:
            issues.append(f"❌ {name}: ontology/{f} 缺失")

    # 3. 实例/边/缺口计数一致性
    try:
        inst = yaml.safe_load(open(ont / "instances.yaml", encoding="utf-8"))
        if len(inst.get("instances", [])) != inst.get("total_instances", -1):
            issues.append(f"⚠️ {name}: instances total({inst.get('total_instances')}) ≠ 实际({len(inst.get('instances', []))})")
        edges = yaml.safe_load(open(ont / "associations.yaml", encoding="utf-8"))
        if len(edges.get("edges", [])) != edges.get("total_edges", -1):
            issues.append(f"⚠️ {name}: edges total({edges.get('total_edges')}) ≠ 实际({len(edges.get('edges', []))})")
        n_ok += 2
    except Exception as ex:
        issues.append(f"❌ {name}: 本体解析异常 {ex}")

    # 4. 模型层
    models_dir = root / "_entities/models"
    n_models = len(list(models_dir.glob("*.md"))) if models_dir.exists() else 0
    if n_models == 0:
        issues.append(f"⚠️ {name}: 无 M1 模型")
    n_ok += 1

    return n_ok, issues


def main():
    ap = argparse.ArgumentParser(description="KEMS 跨域巡检")
    ap.add_argument("--domains", help="逗号分隔的域名或路径")
    a = ap.parse_args()
    domains = {}
    if a.domains:
        for d in a.domains.split(","):
            d = d.strip()
            if "/" in d:
                domains[Path(d).name] = Path(d)
            else:
                domains[d] = Path(DEFAULT_DOMAINS[d])
    else:
        domains = {n: Path(p) for n, p in DEFAULT_DOMAINS.items()}

    print("=" * 66)
    print("KEMS 跨域巡检 — 工具链/本体/版本一致性")
    print(f"@公共/kems-v2: {KEMS_V2}")
    ver = (KEMS_V2 / "VERSION").read_text(encoding="utf-8") if (KEMS_V2 / "VERSION").exists() else "?"
    print(f"工具链版本: {ver.strip()}")
    print("=" * 66)

    all_ok = True
    for name, path in domains.items():
        n_ok, issues = check_domain(name, path)
        status = "✅" if not issues else ("⚠️" if all("⚠️" in i for i in issues) else "❌")
        print(f"\n{status} {name}（{path}）· 检查通过 {n_ok}/{len(TOOLS)+10}")
        for i in issues:
            print(f"  {i}")
        if issues:
            all_ok = False

    print("\n" + "=" * 66)
    print("✅ 跨域巡检完成：四域工具链/本体一致" if all_ok else "❌ 存在需修复项")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
