#!/usr/bin/env python3
"""bin/layer-dependency-check.py — 分层依赖检查工具

验证 eCOS v6 代码是否遵守架构分层依赖契约：
- L3 (入口层) → L2 (引擎层) → L1 (运行时层) → L0 (协议层)
- I0 (织层) 可以调用任何层
- M0 (横切框架) 可以调用 L0/L1
- X (横切扩展) 可以调用任何层

使用方法：
  uv run --with pyyaml python bin/layer-dependency-check.py
  uv run --with pyyaml python bin/layer-dependency-check.py --json
  uv run --with pyyaml python bin/layer-dependency-check.py --project projects/ecos
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml


def load_layer_contract(contract_path: Path = Path("docs/layer-contract.yaml")) -> Dict:
    """加载分层依赖契约"""
    if not contract_path.exists():
        raise FileNotFoundError(f"Layer contract not found: {contract_path}")
    
    with open(contract_path, "r") as f:
        return yaml.safe_load(f)


def get_project_layer(project_name: str, contract: Dict) -> Optional[str]:
    """获取项目所属层"""
    for layer, layer_info in contract["layers"].items():
        if project_name in layer_info["projects"]:
            return layer
    return None


def find_python_imports(file_path: Path) -> List[str]:
    """从 Python 文件中解析导入语句"""
    imports = []
    try:
        with open(file_path, "r") as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except Exception as e:
        print(f"  [warning] Could not parse {file_path}: {e}", file=sys.stderr)
    
    return imports


def get_project_from_import(import_name: str, project_dirs: Set[str]) -> Optional[str]:
    """从导入名提取可能的项目名.

    规则 (ADR-0217):
    - 只匹配**导入前缀** (最长优先), 支持 underscore↔hyphen
    - **禁止**把子模块名当成项目 (e.g. bus_foundation.observability ≠ observability 项目)
    """
    parts = import_name.split(".")
    if not parts:
        return None

    def _candidates(token: str) -> List[str]:
        return [token, token.replace("_", "-"), token.replace("-", "_")]

    # 最长前缀优先: bus_foundation.foo → bus_foundation → bus-foundation
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        for cand in _candidates(prefix):
            if cand in project_dirs:
                return cand if cand in project_dirs else cand

    # 仅首段 (包根), 不再扫中间段 — 避免 false positive
    for cand in _candidates(parts[0]):
        if cand in project_dirs:
            return cand

    return None


class DependencyViolation:
    """表示一个分层依赖违规"""
    def __init__(
        self,
        from_project: str,
        from_layer: str,
        to_project: str,
        to_layer: str,
        file_path: Path,
        import_name: str
    ):
        self.from_project = from_project
        self.from_layer = from_layer
        self.to_project = to_project
        self.to_layer = to_layer
        self.file_path = file_path
        self.import_name = import_name
    
    def to_dict(self) -> Dict:
        return {
            "from_project": self.from_project,
            "from_layer": self.from_layer,
            "to_project": self.to_project,
            "to_layer": self.to_layer,
            "file_path": str(self.file_path),
            "import_name": self.import_name
        }
    
    def __str__(self) -> str:
        return (
            f"{self.from_project} ({self.from_layer}) → "
            f"{self.to_project} ({self.to_layer}) in {self.file_path}"
        )


class LayerDependencyChecker:
    """分层依赖检查器"""
    
    def __init__(self, contract_path: Optional[Path] = None):
        if contract_path is None:
            contract_path = Path("docs/layer-contract.yaml")
        
        self.contract = load_layer_contract(contract_path)
        self.project_dirs = self._collect_project_dirs()
        self.violations: List[DependencyViolation] = []
        self.exceptions = self._load_exceptions()
    
    def _collect_project_dirs(self) -> Set[str]:
        """收集所有项目目录名"""
        dirs = set()
        for layer_info in self.contract["layers"].values():
            dirs.update(layer_info["projects"])
        return dirs
    
    def _load_exceptions(self) -> Dict[Tuple[str, str], Dict]:
        """加载例外情况"""
        exceptions = {}
        
        for ex in self.contract.get("exceptions", []):
            key = (ex["project"], ex["depends_on"])
            exceptions[key] = ex
        
        return exceptions
    
    def _is_exception(self, from_project: str, to_project: str, file_path: Path) -> bool:
        """检查是否是例外情况"""
        key = (from_project, to_project)
        
        if key in self.exceptions:
            ex = self.exceptions[key]
            # 检查是否限制了特定文件
            if "files" in ex:
                file_str = str(file_path)
                for allowed_file in ex["files"]:
                    if allowed_file in file_str:
                        return True
            else:
                # 没有文件限制，全部允许
                return True
        
        return False
    
    def _is_dependency_allowed(self, from_layer: str, to_layer: str) -> bool:
        """检查依赖是否被允许"""
        # 同层互调合法 (e.g. X→X bus-foundation 真依赖 observability 时)
        if from_layer == to_layer:
            return True
        allowed = self.contract["dependency_rules"]["allowed_directions"]

        for rule in allowed:
            if from_layer in rule["from"] and to_layer in rule["to"]:
                return True

        return False
    
    def check_project(self, project_path: Path) -> List[DependencyViolation]:
        """检查单个项目的依赖"""
        project_name = project_path.name
        from_layer = get_project_layer(project_name, self.contract)
        
        if not from_layer:
            print(f"  [skip] {project_name} not found in layer contract", file=sys.stderr)
            return []
        
        violations = []
        exceptions = []
        
        # 遍历项目中的 Python 文件
        for py_file in project_path.rglob("*.py"):
            if ".venv" in py_file.parts:
                continue
            if ".git" in py_file.parts:
                continue
            if "__pycache__" in py_file.parts:
                continue
            
            imports = find_python_imports(py_file)
            
            for imp in imports:
                to_project = get_project_from_import(imp, self.project_dirs)
                
                if to_project and to_project != project_name:
                    to_layer = get_project_layer(to_project, self.contract)
                    
                    if to_layer and not self._is_dependency_allowed(from_layer, to_layer):
                        # 检查是否是例外
                        if self._is_exception(project_name, to_project, py_file):
                            exceptions.append((to_project, py_file))
                        else:
                            violations.append(DependencyViolation(
                                from_project=project_name,
                                from_layer=from_layer,
                                to_project=to_project,
                                to_layer=to_layer,
                                file_path=py_file,
                                import_name=imp
                            ))
        
        # 打印例外情况（可选，用于审计）
        if exceptions:
            print(f"  [info] {len(exceptions)} allowed exception(s) for {project_name}")
        
        return violations
    
    def check_all(self, projects_root: Path = Path("projects")) -> List[DependencyViolation]:
        """检查所有项目"""
        all_violations = []
        
        for project_dir in projects_root.iterdir():
            if not project_dir.is_dir():
                continue
            
            project_name = project_dir.name
            
            # 检查是否在契约中定义
            if not get_project_layer(project_name, self.contract):
                continue
            
            print(f"Checking {project_name}...")
            violations = self.check_project(project_dir)
            all_violations.extend(violations)
        
        return all_violations


def main():
    parser = argparse.ArgumentParser(description="Layer dependency checker")
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("docs/layer-contract.yaml"),
        help="Path to layer contract file"
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="Check only a single project"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )
    
    args = parser.parse_args()
    
    try:
        checker = LayerDependencyChecker(args.contract)
        
        if args.project:
            violations = checker.check_project(args.project)
        else:
            violations = checker.check_all()
        
        if args.json:
            output = {
                "violation_count": len(violations),
                "violations": [v.to_dict() for v in violations]
            }
            print(json.dumps(output, indent=2))
        else:
            if violations:
                print(f"\n❌ Found {len(violations)} layer dependency violation(s):")
                for v in violations:
                    print(f"  - {v}")
                sys.exit(1)
            else:
                print("✅ No layer dependency violations found!")
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
