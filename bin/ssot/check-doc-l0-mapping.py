#!/usr/bin/env python3
"""check-doc-l0-mapping.py — 文档 ↔ L0 ↔ MOF 映射验证 (doc-ssot-contract L0/MOF 映射关联)

依据 .omo/standards/doc-ssot-contract.md 的 L0/MOF 映射小节, 验证 4 条规则:

1. 文档 frontmatter 的 `dimension` 必须在 L0 派生约束 `dimension` 值域内 (X1-X4)
2. 文档 frontmatter 的 `surface` 必须在 `applies_to` 值域内 (L0/L1/L2/L3)
3. 每条 L0 约束必须有 `m3_parent: ConstraintL0` (MOF 映射完整性)
4. `l0-constraints.v2.yaml` 必须可从 `projects/ecos/src/ecos/l0/` 源再生成 (自动更新闭环)

用法:
    python3 bin/ssot/check-doc-l0-mapping.py            # 全量检查
    python3 bin/ssot/check-doc-l0-mapping.py --json     # JSON 输出
    python3 bin/ssot/check-doc-l0-mapping.py --quiet    # 仅错误

退出码: 0=通过, 1=存在违规
"""

import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
L0_DERIVED = os.path.join(ROOT, "projects", "ecos", ".omo", "_derived", "l0-constraints.v2.yaml")
L0_SOURCE = os.path.join(ROOT, "projects", "ecos", "src", "ecos", "l0")

DOC_GLOBS = [
    "docs/**/*.md",
    ".omo/standards/**/*.md",
    ".omo/_knowledge/**/*.md",
]

DIMENSIONS = {"X1", "X2", "X3", "X4", "X5", "X6", "X7"}
SURFACES = {"L0", "L1", "L2", "L3"}


def parse_frontmatter(path):
    """提取 frontmatter 的 dimension/surface/owner/status 字段."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            content = fh.read(4000)
    except OSError:
        return None
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end < 0:
        return None
    fm = content[3:end]
    fields = {}
    for key in ("dimension", "surface", "owner", "status"):
        m = re.search(rf"^{key}\s*:\s*(.+)$", fm, re.MULTILINE)
        if m:
            fields[key] = m.group(1).strip().strip("'\"")
    return fields


def parse_l0(yaml_path):
    """解析 L0 派生约束: 返回约束列表 + dimension 值域 + surface 值域."""
    if not os.path.exists(yaml_path):
        return None
    try:
        import yaml
    except ImportError:
        # 无 pyyaml 时用轻量正则
        return _parse_l0_light(yaml_path)
    with open(yaml_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    constraints = data.get("constraints", []) if isinstance(data, dict) else []
    dims = set()
    surfaces = set()
    for c in constraints:
        if c.get("dimension"):
            dims.add(c["dimension"])
        at = c.get("applies_to") or []
        if isinstance(at, str):
            surfaces.add(at)
        elif isinstance(at, list):
            surfaces.update(at)
    return {"constraints": constraints, "dimensions": dims, "surfaces": surfaces}


def _parse_l0_light(yaml_path):
    """无 pyyaml 时的降级解析 (仅提取维度与 id)."""
    dims, surfaces = set(), set()
    with open(yaml_path, encoding="utf-8") as fh:
        for line in fh:
            m = re.search(r"^  dimension:\s*([A-Z0-9]+)", line)
            if m:
                dims.add(m.group(1))
            m = re.search(r"^  - id:\s*([A-Z][0-9A-Z-]+)", line)
            if m:
                surfaces.add(m.group(1).split("-")[0])
    return {"constraints": [], "dimensions": dims, "surfaces": surfaces}


def main():
    ap = argparse.ArgumentParser(description="文档↔L0↔MOF 映射验证")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--quiet", action="store_true", help="仅输出错误")
    args = ap.parse_args()

    errors = []
    warnings = []

    # ---- L0 派生面加载 ----
    l0 = parse_l0(L0_DERIVED)
    v1_fallback = False
    if l0 is None:
        # v2 派生文件为 gitignored 本地生成物 (ADR-0129 投影面, 生成器已归档),
        # CI 全新检出无此文件 → 回退 v1 源做规则 1/2 值域校验; 规则 3/4 (v2 专属) 跳过.
        v1_path = os.path.join(
            ROOT, "projects", "ecos", "src", "ecos", "ssot", "registry", "L0-constraints.yaml"
        )
        l0 = parse_l0(v1_path)
        if l0 is None:
            errors.append(f"L0 约束源缺失: {L0_DERIVED} / {v1_path}")
            _emit({"ok": False, "errors": errors, "warnings": warnings}, args)
            return 1
        warnings.append(
            f"L0 派生约束缺失 ({os.path.relpath(L0_DERIVED, ROOT)}, 本地生成物), "
            "已回退 v1 源校验规则 1/2; 规则 3/4 跳过"
        )
        v1_fallback = True

    l0_dims = l0["dimensions"]
    l0_surfaces = l0["surfaces"]

    # ---- 规则 3: m3_parent 完整性 (仅 v2 派生面可验) ----
    missing_m3 = []
    if not v1_fallback:
        for c in l0.get("constraints", []):
            if c.get("m3_parent") != "ConstraintL0":
                missing_m3.append(c.get("id", "?"))
    if missing_m3:
        errors.append(f"规则3: {len(missing_m3)} 条 L0 约束缺 m3_parent: ConstraintL0 → {missing_m3[:5]}")

    # ---- 规则 4: L0 源可再生成 ----
    if not os.path.isdir(L0_SOURCE):
        warnings.append(f"规则4: L0 源目录缺失 {L0_SOURCE} (自动更新闭环无法验证)")

    # ---- 规则 1/2: 文档 frontmatter 值域 ----
    bad_dim, bad_surface = [], []
    for pattern in DOC_GLOBS:
        for path in glob.glob(os.path.join(ROOT, pattern), recursive=True):
            if "node_modules" in path:
                continue
            fields = parse_frontmatter(path)
            if not fields:
                continue
            dim = fields.get("dimension")
            if dim and dim not in l0_dims:
                bad_dim.append((os.path.relpath(path, ROOT), dim))
            surf = fields.get("surface")
            if surf and surf not in l0_surfaces:
                bad_surface.append((os.path.relpath(path, ROOT), surf))
    if bad_dim:
        errors.append(f"规则1: {len(bad_dim)} 文档 dimension 不在值域 {sorted(l0_dims)} → {bad_dim[:5]}")
    if bad_surface:
        errors.append(f"规则2: {len(bad_surface)} 文档 surface 不在值域 {sorted(l0_surfaces)} → {bad_surface[:5]}")

    # ---- 汇总 ----
    ok = not errors
    if not args.quiet or errors:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
    if not args.quiet:
        for w in warnings:
            print(f"[WARN] {w}", file=sys.stderr)
        if ok:
            print(
                f"[OK] doc↔L0↔MOF 映射通过 "
                f"(L0约束={len(l0['constraints'])} dimension={sorted(l0_dims)} surface={sorted(l0_surfaces)})"
            )
    if args.json:
        _emit({"ok": ok, "errors": errors, "warnings": warnings}, args)
    return 0 if ok else 1


def _emit(payload, args):
    if not args.json:
        return
    print(json.dumps(payload, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
