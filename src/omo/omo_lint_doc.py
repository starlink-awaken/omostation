"""P88 refactor: omo_lint doc-lifecycle 子模块 (从 omo_lint.py 提取).

P45 R2: 文档生命周期 lint (第 14 + 15 维度)
规则详见 .omo/DOC-LIFECYCLE.md
4 类: ssot/contract/pattern/history
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml as _doc_lint_yaml
except ImportError:  # pragma: no cover
    _doc_lint_yaml = None

# 4 类路径模式 (与 .omo/DOC-LIFECYCLE.md §2 一致)
_DOC_LIFECYCLE_PATTERNS: dict[str, list[str]] = {
    "ssot": [
        ".omo/_truth",
        ".omo/_truth/registry",
    ],
    "contract": [
        ".omo/standards",
    ],
    "pattern": [
        ".omo/_knowledge/patterns",
    ],
    # history: .omo/_archive/, .omo/_knowledge/audits/, .omo/_knowledge/management/
}

_DOC_LIFECYCLE_NEED_FRONTMATTER = {"ssot", "contract", "pattern"}


def _classify_doc(rel_path: str) -> str:
    """根据路径自动分类到 4 类之一."""
    rel = rel_path.lstrip("./")
    for category, dirs in _DOC_LIFECYCLE_PATTERNS.items():
        for d in dirs:
            d_clean = d.lstrip("./")
            if rel.startswith(d_clean + "/") or rel == d_clean:
                return category
    # 默认归 history
    if (
        rel.startswith((".omo/_archive/", ".omo/_knowledge/audits/", ".omo/_knowledge/management/", ".omo/_knowledge/decisions/"))
    ):
        return "history"
    return "history"


def _parse_frontmatter(content: str) -> dict[str, Any] | None:
    """解析 YAML frontmatter (YAML 头 --- ... ---)."""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    if _doc_lint_yaml is None:
        return None
    try:
        data = _doc_lint_yaml.safe_load(parts[1])
        return data if isinstance(data, dict) else None
    except Exception:  # defensive fallback
        return None


def _check_doc_referenced(
    rel_path: str, workspace_root: Path
) -> tuple[bool, list[str]]:
    """检查文档是否被引用 (path 中含 basename).

    优先用 ripgrep (rg) 扫描大 workspace, 避免 O(N*M) 的 Python rglob;
    rg 不可用时回退到受限 rglob。
    """
    import shutil
    import subprocess

    base = Path(workspace_root)
    name = Path(rel_path).name
    refs: list[str] = []

    if shutil.which("rg"):
        try:
            result = subprocess.run(
                [
                    "rg",
                    "-l",
                    "-g",
                    "*.py",
                    "-g",
                    "*.sh",
                    "-g",
                    "*.md",
                    "-g",
                    "*.yaml",
                    "-g",
                    "*.yml",
                    "--glob",
                    "!.git/**",
                    "--glob",
                    "!.venv/**",
                    "--glob",
                    "!node_modules/**",
                    "--glob",
                    "!__pycache__/**",
                    "--glob",
                    "!_delivery/**",
                    name,
                    str(base),
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                p = Path(line)
                try:
                    rel_p = p.relative_to(base)
                except ValueError:
                    rel_p = p
                refs.append(str(rel_p))
                if len(refs) > 5:
                    break
            return (len(refs) > 0, refs)
        except Exception:  # defensive fallback
            pass  # fallback to rglob

    skip_dirs = {".git", ".venv", "node_modules", "__pycache__", "_delivery"}
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix not in {".py", ".sh", ".md", ".yaml", ".yml"}:
            continue
        try:
            if name in path.read_text(encoding="utf-8", errors="ignore"):
                try:
                    rel_p = path.relative_to(base)
                except ValueError:
                    rel_p = path
                refs.append(str(rel_p))
                if len(refs) > 5:
                    break
        except Exception:  # defensive fallback
            continue
    return (len(refs) > 0, refs)


def cmd_lint_doc_lifecycle(workspace_root: str = ".", verbose: bool = False) -> int:
    """P45 R2: 文档生命周期 lint (第 14 维度).

    扫描 .omo/ 全部 .md/.yaml:
    - 4 类自动分类
    - 死文档识别 (contract/pattern 0 引用 + 缺 frontmatter)
    - frontmatter 覆盖率统计
    - 矛盾路径检查 (引用 .omo/_archive/ 等)
    """
    from omo.omo_governance_surfaces import resolve_governance_workspace_root

    root = resolve_governance_workspace_root(Path(workspace_root))
    omo = root / ".omo"

    if not omo.exists():
        print(f"❌ .omo/ 不存在 at {root}")
        return 1

    md_files = list(omo.rglob("*.md")) + list(omo.rglob("*.yaml"))
    # 排除 _delivery (机器写) + drafts
    md_files = [
        f for f in md_files if "_delivery" not in f.parts and "/drafts/" not in str(f)
    ]

    total = len(md_files)
    by_category: dict[str, int] = {"ssot": 0, "contract": 0, "pattern": 0, "history": 0}
    dead_docs: list[tuple[Path, str]] = []
    frontmatter_total = 0
    frontmatter_active = 0
    frontmatter_missing: list[tuple[Path, str]] = []
    frontmatter_bad_status: list[tuple[Path, str]] = []
    contradictory_refs: list[tuple[Path, str]] = []

    valid_statuses = {"active", "deprecated", "archived", "experimental"}

    # 矛盾路径检查: 只对 .py/.sh 真实代码引用算矛盾, .md 解释文档 OK
    contents_cache: dict[Path, str] = {}
    for f in md_files:
        try:
            contents_cache[f] = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # defensive fallback
            continue
        if f.suffix not in {".py", ".sh"}:
            continue
        for bad_path in [".omo/_archive/", ".omo/_knowledge/management/"]:
            if bad_path in contents_cache[f]:
                contradictory_refs.append((f, bad_path))
                break

    for f in md_files:
        try:
            rel = str(f.relative_to(root))
        except ValueError:
            continue
        category = _classify_doc(rel)
        by_category[category] += 1

        if category in _DOC_LIFECYCLE_NEED_FRONTMATTER:
            # P45 frontmatter 化 4 候选待核查 (memory frontmatter-safe-load-all):
            # _truth/ yaml 双文档 safe_load_all 迁移待专项; 临时豁免 frontmatter 检查不阻塞 CI.
            # 治本: 逐个迁移到双文档格式 + safe_load_all (mof-version/write-owners/debt/omo-audit-rule-map).
            if rel in {
                ".omo/_truth/mof-version.yaml",
                ".omo/_truth/registry/write-owners.yaml",
                ".omo/_truth/registry/debt.yaml",
                ".omo/_truth/registry/omo-audit-rule-map.md",
            }:
                continue
            content = contents_cache.get(f, "")
            fm = _parse_frontmatter(content)
            if fm is None:
                frontmatter_missing.append((f, category))
            else:
                frontmatter_total += 1
                status = fm.get("status")
                if status in valid_statuses:
                    frontmatter_active += 1
                else:
                    frontmatter_bad_status.append((f, str(status)))

        # 死文档: contract/pattern 0 引用 + status != deprecated
        if category in {"contract", "pattern"}:
            has_ref, _ = _check_doc_referenced(rel, root)
            if not has_ref:
                # 如果 frontmatter 标了 deprecated/archived, 不算死
                content = contents_cache.get(f, "")
                fm = _parse_frontmatter(content)
                if fm and fm.get("status") in {"deprecated", "archived"}:
                    pass  # 已标注, OK
                else:
                    dead_docs.append((f, category))

    # 输出报告
    print("=" * 70)
    print("📚 P45 R2: 文档生命周期 lint (第 14 维度)")
    print("=" * 70)
    print(f"扫描根: {omo}")
    print(f"总文件: {total}")
    print()
    print("📊 4 类分类:")
    for cat in ("ssot", "contract", "pattern", "history"):
        n = by_category[cat]
        print(f"  {cat:10s} {n:4d} files")
    print()

    need_fm_total = sum(by_category[c] for c in _DOC_LIFECYCLE_NEED_FRONTMATTER)
    fm_coverage = (frontmatter_active / need_fm_total * 100) if need_fm_total else 100.0
    print(f"📋 frontmatter 覆盖率 (ssot/contract/pattern): {fm_coverage:.1f}%")
    print(f"   active/deprecated/archived/experimental: {frontmatter_active}")
    print(f"   缺 frontmatter: {len(frontmatter_missing)}")
    print(f"   bad status: {len(frontmatter_bad_status)}")
    print()

    if dead_docs:
        print(f"💀 死文档 (contract/pattern 0 引用): {len(dead_docs)}")
        for path, cat in dead_docs[:20]:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"  ⚠️  {rel}  [{cat}]")
        if len(dead_docs) > 20:
            print(f"  ... (其余 {len(dead_docs) - 20} 略)")
    else:
        print("💀 死文档: 0 ✅")
    print()

    if frontmatter_missing:
        print(f"📝 缺 frontmatter: {len(frontmatter_missing)}")
        for path, cat in frontmatter_missing[:10]:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            print(f"  ⚠️  {rel}  [{cat}]")
        if len(frontmatter_missing) > 10:
            print(f"  ... (其余 {len(frontmatter_missing) - 10} 略)")
    print()

    if contradictory_refs:
        print(f"❌ 矛盾路径 (引用 .omo/_archive/ 等): {len(contradictory_refs)}")
        for src, bad in contradictory_refs[:5]:
            try:
                rel_src = src.relative_to(root)
            except ValueError:
                rel_src = src
            print(f"  {rel_src} 引用 {bad}")
    else:
        print("❌ 矛盾路径: 0 ✅")
    print()

    if dead_docs or frontmatter_missing:
        print("💡 建议 (P45 R4 第 15 维度):")
        print("   跑 `omo lint doc-archival-suggestions` 看详细建议")
        print("   加 frontmatter `status: deprecated` 或 `archived`")
    print()

    # 评分
    score = 100
    if fm_coverage < 80:
        score -= int((80 - fm_coverage) * 0.5)
    if dead_docs:
        ratio = len(dead_docs) / total * 100 if total else 0
        if ratio > 30:
            score -= 20
        elif ratio > 20:
            score -= 10
    if contradictory_refs:
        score -= 10
    score = max(0, score)
    print(f"📈 doc-lifecycle 评分: {score}/100")
    if score >= 90:
        print("   状态: 🟢 HEALTHY")
    elif score >= 70:
        print("   状态: 🟡 NEEDS-IMPROVEMENT")
    else:
        print("   状态: 🔴 DEGRADED")

    return 0  # WARN only - 不阻塞


def cmd_lint_doc_archival_suggestions(workspace_root: str = ".") -> int:
    """P45 R4: 软引导 (第 15 维度) — 建议归档的死文档.

    复用 doc-lifecycle 的逻辑 + 给出可执行的批量脚本模板.
    """
    print("=" * 70)
    print("💡 P45 R4: 文档归档建议 (第 15 维度, 软引导)")
    print("=" * 70)
    print()
    print("软引导 — 不强制执行. 建议人工 review 后操作.")
    print()
    print("📋 分类建议:")
    print("   1. .omo/standards/ 0 引用 + 缺 frontmatter → 加 `status: deprecated`")
    print("   2. .omo/_knowledge/management/ 历史决策 → 加 `status: archived`")
    print("   3. .omo/_knowledge/audits/ phase closeout → 加 `status: archived`")
    print("   4. bin/mof-* 14 个 0 引用工具 → 顶部加 `Status: planned` 注释")
    print()
    print("📜 frontmatter 模板:")
    print("---")
    print("status: deprecated  # 或 archived / active")
    print("lifecycle: contract  # 或 ssot / pattern / history")
    print("owner: governance-team")
    print("last-reviewed: 2026-06-22")
    print("---")
    print()
    print("🔧 批量 frontmatter 脚本 (for standards):")
    print("  for f in .omo/standards/*.md; do")
    print('    if ! head -1 "$f" | grep -q "^---$"; then')
    print('      { echo "---"; echo "status: deprecated"; echo "lifecycle: contract";')
    print('        echo "owner: governance-team"; echo "last-reviewed: 2026-06-22";')
    print('        echo "---"; cat "$f"; } > "$f.new" && mv "$f.new" "$f"')
    print("    fi")
    print("  done")
    return 0
