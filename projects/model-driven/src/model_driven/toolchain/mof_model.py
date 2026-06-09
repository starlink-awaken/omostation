"""
model_driven.toolchain.mof_model — 全量资产 → M1 节点建模

基于 M2 类型定义，对全量资产进行分类建模，生成 M1 节点。
移植自 ecos/ssot/tools/mof-model.py，改为纯函数 + 可配置路径模式。

建模策略:
  1. 项目目录 → Component/CodeModule/TestSuite
  2. 配置文件 → DeploymentConfig/Environment
  3. 文档资产 → Specification/Document
  4. 服务/组件 → Service/Component
  5. 工作流 → Workflow/Process
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from model_driven.toolchain.common import now


def model_project(
    project_path: str | Path,
    project_name: str = "",
    layer: str = "",
    domain: str = "",
) -> dict[str, Any]:
    """对单个项目进行全量 M1 建模"""
    root = Path(project_path)
    if not root.exists():
        return {"success": False, "error": f"项目不存在: {root}"}

    name = project_name or root.name
    model = {
        "project": {
            "id": f"COMPONENT-{name}",
            "type": "component",
            "name": name,
            "layer": layer,
            "domain": domain,
            "status": "active",
            "path": str(root),
        },
        "modules": [],
        "tests": [],
        "configs": [],
        "specs": [],
        "services": [],
    }

    # 代码模块
    src_dir = root / "src"
    if src_dir.exists():
        for py_file in sorted(src_dir.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            rel = py_file.relative_to(root)
            model["modules"].append(
                {
                    "id": f"CODE_MODULE-{py_file.stem}",
                    "type": "code_module",
                    "name": py_file.stem,
                    "path": str(rel),
                    "size": py_file.stat().st_size,
                    "status": "active",
                    "project": name,
                }
            )

    # 测试
    tests_dir = root / "tests"
    if tests_dir.exists():
        for test_file in sorted(tests_dir.rglob("test_*.py")):
            if "__pycache__" in str(test_file):
                continue
            rel = test_file.relative_to(root)
            model["tests"].append(
                {
                    "id": f"TEST_SUITE-{test_file.stem}",
                    "type": "test_suite",
                    "name": test_file.stem,
                    "path": str(rel),
                    "status": "active",
                    "project": name,
                }
            )

    # 配置
    for yaml_file in sorted(root.rglob("*.yaml")):
        if any(skip in str(yaml_file) for skip in ("__pycache__", ".venv", "uv.lock")):
            continue
        rel = yaml_file.relative_to(root)
        model["configs"].append(
            {
                "id": f"CONFIG-{yaml_file.stem}",
                "type": "deployment_config",
                "name": yaml_file.stem,
                "path": str(rel),
                "status": "active",
                "project": name,
            }
        )

    # Agent 契约
    for md_name in ("CLAUDE.md", "AGENTS.md", "CODEBUDDY.md"):
        md_path = root / md_name
        if md_path.exists():
            model["specs"].append(
                {
                    "id": f"SPEC-{md_name.replace('.md', '').replace('.', '_')}",
                    "type": "specification",
                    "name": md_name,
                    "path": str(md_path.relative_to(root)),
                    "status": "active",
                    "project": name,
                }
            )

    # 服务 (如果有 pyproject.toml 且定义了 scripts)
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            with open(pyproject) as f:
                data = tomllib.loads(f.read())
            scripts = data.get("project", {}).get("scripts", {})
            for script_name in scripts:
                model["services"].append(
                    {
                        "id": f"SERVICE-{script_name}",
                        "type": "service",
                        "name": script_name,
                        "status": "active",
                        "project": name,
                    }
                )
        except (OSError, ValueError, TypeError, ImportError):
            pass

    model["total"] = (
        len(model["modules"])
        + len(model["tests"])
        + len(model["configs"])
        + len(model["specs"])
        + len(model["services"])
    )

    return {"success": True, "model": model, "project": name}


def model_workspace(
    workspace_dir: str | Path | None = None,
    projects_glob: str = "projects/*",
    exclude_patterns: list[str] | None = None,
) -> dict[str, Any]:
    """对整个工作区进行全量 M1 建模"""
    if workspace_dir is None:
        from model_driven._paths import get_workspace_dir

        workspace_dir = str(get_workspace_dir())
    root = Path(workspace_dir)
    exclude_patterns = exclude_patterns or ["_archived", ".git", "__pycache__", ".venv"]

    all_models = []
    errors = []
    total_nodes = 0

    for project_dir in sorted(root.glob(projects_glob)):
        if not project_dir.is_dir():
            continue
        if any(pat in str(project_dir) for pat in exclude_patterns):
            continue
        if not (project_dir / "pyproject.toml").exists():
            continue

        result = model_project(project_dir, project_name=project_dir.name)
        if result["success"]:
            all_models.append(result)
            total_nodes += result["model"]["total"]
        else:
            errors.append(result.get("error", "未知错误"))

    # 按类型聚合
    by_type: dict[str, int] = {}
    for m in all_models:
        for category, items in m["model"].items():
            if isinstance(items, list):
                for item in items:
                    mtype = item.get("type", "unknown")
                    by_type[mtype] = by_type.get(mtype, 0) + 1

    return {
        "success": True,
        "total_projects": len(all_models),
        "total_nodes": total_nodes,
        "by_type": by_type,
        "models": all_models,
        "errors": errors,
        "modeled_at": now(),
    }


def classify_by_lifecycle_stage(
    model: dict[str, Any],
) -> dict[str, list[str]]:
    """将建模结果按生命周期阶段分类"""
    by_stage: dict[str, list[str]] = {
        "planning": [],
        "design": [],
        "development": [],
        "deployment": [],
        "runtime": [],
        "operations": [],
        "business_ops": [],
    }

    for m in model.get("models", []):
        proj_model = m.get("model", {})

        # 模块 → 开发态
        for mod in proj_model.get("modules", []):
            by_stage["development"].append(mod["id"])

        # 测试 → 开发态
        for test in proj_model.get("tests", []):
            by_stage["development"].append(test["id"])

        # 配置 → 部署态
        for cfg in proj_model.get("configs", []):
            by_stage["deployment"].append(cfg["id"])

        # Spec → 设计态
        for spec in proj_model.get("specs", []):
            by_stage["design"].append(spec["id"])

        # 服务 → 运行态
        for svc in proj_model.get("services", []):
            by_stage["runtime"].append(svc["id"])

    return by_stage
