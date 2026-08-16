import ast
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class UnderstandAdapter:
    """Adapter for Mindpilot/SciTools Understand functionality."""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()

    def generate_architecture_diagram(self, module_path: str) -> str:
        """
        Parses a python module/file to extract imports and class relationships,
        returning a Mermaid.js diagram.
        """
        target = self.workspace_root / module_path
        if not target.exists() or not target.is_file():
            return f"Error: Module path {module_path} is invalid."

        try:
            with open(target, encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)

            imports = []
            classes = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)

            mermaid = ["```mermaid", "graph TD", f"    Target[{target.name}]"]

            for imp in set(imports):
                mermaid.append(f"    Target --> |imports| {imp.replace('.', '_')}[{imp}]")

            for c in set(classes):
                mermaid.append(f"    {c}[Class: {c}] --> |defined in| Target")

            mermaid.append("```")
            return "\\n".join(mermaid)

        except Exception as e:
            logger.error(f"Failed to generate diagram: {e}")
            return f"Error generating architecture diagram: {e}"

    def get_code_metrics(self, file_path: str) -> dict:
        """
        Returns complexity metrics for a file using radon.
        """
        target = self.workspace_root / file_path
        if not target.exists():
            return {"error": "File does not exist"}

        try:
            # Run radon cyclomatic complexity
            cc_res = subprocess.run(["radon", "cc", "-s", "-j", str(target)], capture_output=True, text=True)
            # Run radon raw metrics (LOC, LLOC, SLOC, etc.)
            raw_res = subprocess.run(["radon", "raw", "-j", str(target)], capture_output=True, text=True)

            cc_data = json.loads(cc_res.stdout) if cc_res.stdout else {}
            raw_data = json.loads(raw_res.stdout) if raw_res.stdout else {}

            # Extract metrics for the specific file
            file_key = str(target)
            file_cc = cc_data.get(file_key, [])
            file_raw = raw_data.get(file_key, {})

            # Calculate average complexity
            avg_complexity = sum(item.get("complexity", 0) for item in file_cc) / max(1, len(file_cc))

            return {
                "file": file_path,
                "cyclomatic_complexity": {"average": round(avg_complexity, 2), "details": file_cc},
                "raw_metrics": file_raw,
            }
        except Exception as e:
            return {"error": f"Radon analysis failed: {e}"}
