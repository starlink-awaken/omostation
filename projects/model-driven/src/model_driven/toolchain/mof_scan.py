"""
model_driven.toolchain.mof_scan — System→M1 节点扫描器

自动扫描系统资产 (文件系统/项目结构/配置)，生成 M1 节点声明。
基于 M2 元模型定义，为每个发现的要素创建结构化的 M1 节点。

移植自 ecos/ssot/tools/mof-scan.py，改为纯函数 + 可配置路径模式。

扫描源:
  1. 项目目录 (pyproject.toml)          → Component/CodeModule
  2. 测试文件                           → TestSuite
  3. YAML 配置                          → DeploymentConfig/Specification
  4. 文档文件                           → Artifact/Document
  5. 脚本文件                           → Artifact/Script
  6. CLAUDE.md / AGENTS.md              → Specification (Agent契约)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from model_driven.mof.m2_lifecycle import ALL_M2_SCHEMAS


@dataclass
class ScanResult:
    """扫描结果"""

    source: str
    nodes: list[dict[str, Any]]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def scan_project_dir(
    project_dir: str | Path,
    project_name: str = "",
) -> ScanResult:
    """扫描项目目录 → Component + CodeModule + TestSuite 节点"""
    root = Path(project_dir)
    if not root.exists():
        return ScanResult(source=str(root), nodes=[], errors=[f"目录不存在: {root}"])

    nodes = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        name = project_name or root.name
        nodes.append({
            "id": f"COMPONENT-{name}",
            "type": "component",
            "subtype": "Project",
            "name": name,
            "description": f"项目: {name}",
            "status": "active",
            "created": now(),
            "version": "1.0.0",
            "properties": {
                "path": str(root),
                "format": "python",
                "config": str(pyproject),
            },
        })

    # 扫描 src 目录
    src_dir = root / "src"
    if src_dir.exists():
        for py_file in sorted(src_dir.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            rel = py_file.relative_to(root)
            nodes.append({
                "id": f"CODE_MODULE-{py_file.stem}",
                "type": "code_module",
                "name": py_file.stem,
                "description": str(rel),
                "status": "active",
                "created": now(),
                "version": "1.0.0",
                "properties": {
                    "path": str(py_file),
                    "relative_path": str(rel),
                    "size": py_file.stat().st_size,
                },
            })

    # 扫描 tests 目录
    tests_dir = root / "tests"
    if tests_dir.exists():
        for test_file in sorted(tests_dir.rglob("test_*.py")):
            if "__pycache__" in str(test_file):
                continue
            rel = test_file.relative_to(root)
            nodes.append({
                "id": f"TEST_SUITE-{test_file.stem}",
                "type": "test_suite",
                "name": test_file.stem,
                "description": str(rel),
                "status": "active",
                "created": now(),
                "version": "1.0.0",
                "properties": {
                    "path": str(test_file),
                    "relative_path": str(rel),
                },
            })

    return ScanResult(source=str(root), nodes=nodes)


def scan_yaml_configs(
    config_dir: str | Path,
    pattern: str = "*.yaml",
) -> ScanResult:
    """扫描 YAML 配置 → DeploymentConfig/Specification 节点"""
    root = Path(config_dir)
    if not root.exists():
        return ScanResult(source=str(root), nodes=[], errors=[f"目录不存在: {root}"])

    nodes = []
    for yaml_file in sorted(root.rglob(pattern)):
        if "__pycache__" in str(yaml_file) or ".venv" in str(yaml_file):
            continue
        rel = yaml_file.relative_to(root)
        nodes.append({
            "id": f"CONFIG-{yaml_file.stem}",
            "type": "deployment_config",
            "name": yaml_file.stem,
            "description": str(rel),
            "status": "active",
            "created": now(),
            "version": "1.0.0",
            "properties": {
                "path": str(yaml_file),
                "relative_path": str(rel),
                "format": "yaml",
                "size": yaml_file.stat().st_size,
            },
        })

    return ScanResult(source=str(root), nodes=nodes)


def scan_agent_contracts(
    root_dir: str | Path,
    file_names: list[str] | None = None,
) -> ScanResult:
    """扫描 Agent 契约文件 (CLAUDE.md/AGENTS.md) → Specification 节点"""
    root = Path(root_dir)
    file_names = file_names or ["CLAUDE.md", "AGENTS.md", "CODEBUDDY.md"]
    nodes = []

    for md_file in sorted(root.rglob("*")):
        if md_file.name in file_names and "__pycache__" not in str(md_file):
            rel = md_file.relative_to(root)
            nodes.append({
                "id": f"SPEC-{md_file.name.replace('.md', '').replace('.', '_')}",
                "type": "specification",
                "name": md_file.name,
                "description": f"Agent 契约: {rel}",
                "status": "active",
                "created": now(),
                "version": "1.0.0",
                "properties": {
                    "path": str(md_file),
                    "relative_path": str(rel),
                    "size": md_file.stat().st_size,
                },
            })

    return ScanResult(source=str(root), nodes=nodes)


def scan_mof_m1_nodes(
    m1_dir: str | Path,
) -> ScanResult:
    """扫描现有 M1 节点目录 → 按类型分类统计"""
    root = Path(m1_dir)
    if not root.exists():
        return ScanResult(source=str(root), nodes=[], errors=[f"目录不存在: {root}"])

    nodes = []
    by_type: dict[str, int] = {}

    for yaml_file in sorted(root.rglob("*.yaml")):
        try:
            import yaml
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and "type" in data:
                mtype = data["type"]
                by_type[mtype] = by_type.get(mtype, 0) + 1
                nodes.append(data)
        except Exception:
            pass

    return ScanResult(
        source=str(root),
        nodes=nodes,
        warnings=[f"类型分布: {by_type}"] if by_type else [],
    )


def scan_workspace(
    workspace_dir: str | Path,
    project_pattern: str = "projects/*",
) -> ScanResult:
    """扫描整个工作区 → 全量资产建模"""
    root = Path(workspace_dir)
    if not root.exists():
        return ScanResult(source=str(root), nodes=[], errors=[f"目录不存在: {root}"])

    all_nodes = []
    errors = []

    # 扫描项目目录
    for project_dir in sorted(root.glob(project_pattern)):
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith("_") or project_dir.name.startswith("."):
            continue

        result = scan_project_dir(project_dir, project_name=project_dir.name)
        all_nodes.extend(result.nodes)
        errors.extend(result.errors)

    # 扫描 Agent 契约
    contract_result = scan_agent_contracts(root)
    all_nodes.extend(contract_result.nodes)

    return ScanResult(source=str(root), nodes=all_nodes, errors=errors)


# ── 工具函数 ──────────────────────────────────────


def scan_system(
    paths: list[str] | None = None,
    scan_projects: bool = True,
    scan_configs: bool = True,
    scan_contracts: bool = True,
    workspace_dir: str | None = None,
) -> dict[str, Any]:
    """统一扫描入口 — 扫描系统资产生成 M1 节点"""
    all_nodes = []
    results = []

    if scan_projects and workspace_dir:
        result = scan_workspace(workspace_dir)
        all_nodes.extend(result.nodes)
        results.append({"type": "projects", "count": len(result.nodes), "errors": result.errors})

    if paths:
        for p in paths:
            path_obj = Path(p)
            if path_obj.is_dir():
                if (path_obj / "pyproject.toml").exists():
                    result = scan_project_dir(path_obj)
                    all_nodes.extend(result.nodes)
                    results.append({"type": "project", "path": p, "count": len(result.nodes)})
                elif scan_configs and list(path_obj.rglob("*.yaml")):
                    result = scan_yaml_configs(path_obj)
                    all_nodes.extend(result.nodes)
                    results.append({"type": "configs", "path": p, "count": len(result.nodes)})

            if scan_contracts and path_obj.name in ("CLAUDE.md", "AGENTS.md", "CODEBUDDY.md"):
                result = scan_agent_contracts(path_obj.parent, [path_obj.name])
                all_nodes.extend(result.nodes)
                results.append({"type": "contract", "path": p, "count": len(result.nodes)})

    # 按类型统计
    by_type: dict[str, int] = {}
    for node in all_nodes:
        mtype = node.get("type", "unknown")
        by_type[mtype] = by_type.get(mtype, 0) + 1

    return {
        "success": True,
        "total_nodes": len(all_nodes),
        "by_type": by_type,
        "nodes": all_nodes,
        "scan_results": results,
        "scanned_at": now(),
    }
