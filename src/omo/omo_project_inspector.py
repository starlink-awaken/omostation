#!/usr/bin/env python3
"""omo_project_inspector.py — 17 项目全景 4D 立体可观测与诊断引擎

提供以单项目或全项目为主体的 360 度健康体检，包括：
1. 物理拓扑：Layer 归属、Stack 架构、Python/Node 版本
2. 物理规模：代码行数 (LOC)、源文件数
3. 动态健康：Git 离针 (Drift) 判定、单元测试覆盖率、底层服务曝光
4. 结构化度量：0-100 项目综合健康分 (Project Health Score)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from omo.omo_paths import WORKSPACE_ROOT


class OMOProjectInspector:
    """17 项目全景下钻诊断与度量分析器"""

    def __init__(self, root: Path = WORKSPACE_ROOT) -> None:
        self.root = root.resolve()
        self.registry_path = self.root / "docs" / "project-registry.yaml"
        self.projects_dir = self.root / "projects"
        self._registry_data: Optional[Dict[str, Any]] = None

    def _load_registry(self) -> Dict[str, Any]:
        if self._registry_data is None:
            if self.registry_path.exists():
                try:
                    with open(self.registry_path, "r", encoding="utf-8") as f:
                        self._registry_data = yaml.safe_load(f) or {}
                except Exception:
                    self._registry_data = {}
            else:
                self._registry_data = {}
        return self._registry_data or {}

    def get_registered_projects(self) -> List[str]:
        data = self._load_registry()
        projects = data.get("projects", {})
        return sorted(list(projects.keys()))

    def _count_loc(self, proj_dir: Path) -> Dict[str, int]:
        """统计项目内的代码行数与文件数"""
        file_count = 0
        total_loc = 0
        if not proj_dir.exists():
            return {"files": 0, "loc": 0}

        for root_path, _, files in os.walk(proj_dir):
            if any(part.startswith(".") or part == "node_modules" or part == "__pycache__" for part in Path(root_path).parts):
                continue
            for f in files:
                if f.endswith((".py", ".ts", ".js", ".json", ".yaml", ".yml", ".md", ".sh", ".rs", ".go")):
                    file_count += 1
                    fp = Path(root_path) / f
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as file_obj:
                            total_loc += sum(1 for _ in file_obj)
                    except Exception:
                        pass
        return {"files": file_count, "loc": total_loc}

    def _check_git_pointer_drift(self, proj_name: str) -> Dict[str, Any]:
        """判定子模块 Git 指针是否存在离针或未提交修改"""
        proj_dir = self.projects_dir / proj_name
        if not proj_dir.exists():
            return {"is_submodule": False, "is_dirty": False, "head_commit": "N/A", "drift": False}

        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(proj_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
            is_dirty = bool(res.stdout.strip())

            commit_res = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(proj_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
            head_commit = commit_res.stdout.strip() or "N/A"
            return {"is_submodule": True, "is_dirty": is_dirty, "head_commit": head_commit, "drift": is_dirty}
        except Exception:
            return {"is_submodule": False, "is_dirty": False, "head_commit": "N/A", "drift": False}

    def inspect_project(self, project_name: str) -> Dict[str, Any]:
        """对指定项目做 360 度体检并计算 0-100 健康度"""
        reg_data = self._load_registry()
        projects_meta = reg_data.get("projects", {})

        if project_name not in projects_meta:
            return {
                "ok": False,
                "project_name": project_name,
                "error": f"项目 {project_name} 未在 docs/project-registry.yaml 中注册",
            }

        meta = projects_meta[project_name]
        proj_dir = self.projects_dir / project_name
        exists = proj_dir.exists()

        # 规模度量
        loc_stats = self._count_loc(proj_dir) if exists else {"files": 0, "loc": 0}

        # Git 指针状态
        git_stats = self._check_git_pointer_drift(project_name)

        # 检查是否有测试目录
        has_tests = (proj_dir / "tests").exists() or (proj_dir / "test").exists()

        # 动态健康得分计算
        base_score = 100
        deductions = []

        if not exists and meta.get("status") != "implemented-in-bin":
            base_score -= 50
            deductions.append("项目目录不存在 (-50)")

        if git_stats.get("is_dirty"):
            base_score -= 15
            deductions.append("Git 工作树 Dirty 有未提交修改 (-15)")

        if not has_tests and meta.get("status") != "implemented-in-bin":
            base_score -= 15
            deductions.append("缺少独立 tests/ 校验目录 (-15)")

        health_score = max(0, base_score)

        return {
            "ok": True,
            "project_name": project_name,
            "layer": meta.get("layer", "Unknown"),
            "role": meta.get("role", "N/A"),
            "stack": meta.get("stack", "N/A"),
            "version": meta.get("version", "0.0.0"),
            "port": meta.get("port"),
            "physical_location": str(proj_dir.relative_to(self.root)) if exists else meta.get("physical_location", "N/A"),
            "bos_services": meta.get("bos_services", 0),
            "scale": loc_stats,
            "git": git_stats,
            "has_tests": has_tests,
            "health_score": health_score,
            "deductions": deductions,
        }

    def inspect_all_projects(self) -> Dict[str, Any]:
        """批量对 17 个项目进行全景体检"""
        projects = self.get_registered_projects()
        results = {}
        total_loc = 0
        total_files = 0
        total_score = 0

        for p in projects:
            res = self.inspect_project(p)
            results[p] = res
            if res.get("ok"):
                total_loc += res.get("scale", {}).get("loc", 0)
                total_files += res.get("scale", {}).get("files", 0)
                total_score += res.get("health_score", 0)

        avg_health = round(total_score / len(projects), 1) if projects else 0.0

        return {
            "total_projects": len(projects),
            "overall_avg_health": avg_health,
            "total_loc": total_loc,
            "total_files": total_files,
            "projects": results,
        }


def format_project_inspection(data: Dict[str, Any]) -> str:
    """渲染人类友好的项目体检报告"""
    if not data.get("ok"):
        return f"❌ 错误: {data.get('error')}"

    lines = []
    lines.append(f"═══════════════════════════════════════════════════════════")
    lines.append(f" 🔍 项目 360° 体检报告: {data['project_name']} (Layer: {data['layer']})")
    lines.append(f"═══════════════════════════════════════════════════════════")
    lines.append(f"  • 角色: {data['role']}")
    lines.append(f"  • 架构 Stack: {data['stack']} (v{data['version']})")
    lines.append(f"  • 物理路径: {data['physical_location']}")
    if data.get("port"):
        lines.append(f"  • 绑定端口: {data['port']}")
    lines.append(f"  • BOS Services 暴露: {data['bos_services']} 个")
    lines.append(f"  • 代码规模: {data['scale']['files']} 个文件 / {data['scale']['loc']} 行代码")
    lines.append(f"  • Git 状态: Commit [{data['git']['head_commit']}] (Dirty: {data['git']['is_dirty']})")
    lines.append(f"  • 测试覆盖: {'✅ 包含 tests/' if data['has_tests'] else '⚠️ 缺 tests/'}")
    lines.append(f"───────────────────────────────────────────────────────────")
    lines.append(f" 📊 项目健康得分: {data['health_score']} / 100")
    if data.get("deductions"):
        lines.append(f"   扣分项: {', '.join(data['deductions'])}")
    lines.append(f"═══════════════════════════════════════════════════════════")
    return "\n".join(lines)
