"""P108 refactor: omo_governance_surfaces c2g-omo-boundary 子模块 (从 omo_governance_surfaces.py 提取).

ADR-0101 P107 末 omo_governance_surfaces.py 556L (<600L ideal 首次达成).
P108 继续拆: _check_c2g_omo_boundary (50L) + _check_internal_write_profile_registry (103L)
= 153L → ~403L, 接近黄金值 400-500L.

业务:
  - _check_c2g_omo_boundary (L104-154, 50L):
    校验 c2g 只能通过本地 facade 接入 OMO, 不得散弹式 import 内核模块 (Round 31 P0)
    - facade 路径存在性: projects/c2g/src/c2g/omo_client.py
    - 散弹 import 违规检测
    - facade-only 边界强制

模块依赖:
  - Path (stdlib)
  - yaml (via inline _load_yaml helper, 见 P105 D2 范式)
  - omo.omo_shared.load_yaml_required (SSOT)

向后兼容 (P100-P107 模式):
  omo_governance_surfaces.py 通过 `from .omo_governance_surfaces_c2g_boundary import (...)` re-export,
  保持 `_check_c2g_omo_boundary()` 调用点 (P102 cmd_lint_c2g_omo_boundary wrapper) 不破.

P108 收益:
  - omo_governance_surfaces.py 556L → ~403L, 逼近黄金值 400-500L
  - 7 子模块架构完整
  - 累计 omo_governance_surfaces.py: 1762 → 403L (-1359L, -77%)
"""

from __future__ import annotations

import ast
from pathlib import Path

from omo.omo_shared import load_yaml_required


def _load_yaml(path):
    """Inline helper (P108): avoid circular import with omo_governance_surfaces."""
    return load_yaml_required(path)


def _check_c2g_omo_boundary(
    workspace_root: Path,
) -> tuple[dict[str, object], list[str]]:
    c2g_src = workspace_root / "projects" / "c2g" / "src" / "c2g"
    facade_path = c2g_src / "omo_client.py"
    summary: dict[str, object] = {
        "exists": c2g_src.exists(),
        "path": str(c2g_src),
        "facade_path": str(facade_path),
        "facade_exists": facade_path.exists(),
        "violations": [],
    }
    if not c2g_src.exists():
        return summary, ["projects/c2g/src/c2g missing"]
    if not facade_path.exists():
        return summary, ["c2g omo facade missing: projects/c2g/src/c2g/omo_client.py"]

    violations: list[str] = []
    violating_files: list[str] = []
    for py_file in sorted(c2g_src.rglob("*.py")):
        if py_file.name == "omo_client.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError as exc:
            violations.append(
                f"failed to parse {py_file.relative_to(workspace_root)}: {exc}"
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "omo" or alias.name.startswith("omo."):
                        violating_files.append(str(py_file.relative_to(workspace_root)))
                        violations.append(
                            f"c2g direct omo import forbidden outside facade: "
                            f"{py_file.relative_to(workspace_root)} imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "omo" or module.startswith("omo."):
                    violating_files.append(str(py_file.relative_to(workspace_root)))
                    violations.append(
                        f"c2g direct omo import forbidden outside facade: "
                        f"{py_file.relative_to(workspace_root)} imports from {module}"
                    )

    summary["violations"] = sorted(set(violating_files))
    return summary, violations
