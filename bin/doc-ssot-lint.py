#!/usr/bin/env python3
"""doc-ssot-lint — 文档 SSOT 正交契约门禁.

检测 markdown 文件中与 docs/project-registry.yaml 冲突的硬编码值.

规则 (见 .omo/standards/doc-ssot-contract.md):
  1. 禁止 markdown 包含与 registry 冲突的易变数字 (包数/工具数/源文件数等)
  2. 禁止 markdown 出现过期架构版本 ("eCOS v5", "5+3+1")
  3. 入口文档必须使用 agent-workflow bootstrap, 不复制 workflow/profile/adapter 清单
  4. 入口文档不得重新粘贴完整 GaC 规则表或手写项目分层表

用法:
  python3 bin/doc-ssot-lint.py              # 检测, 有冲突返回 1
  python3 bin/doc-ssot-lint.py --fix          # 自动修复已知模式
  python3 bin/doc-ssot-lint.py --file PATH   # 只检查单个文件
  python3 bin/doc-ssot-lint.py --json        # 机器可读 JSON (CI/仪表盘消费)

退出码:
  0 = 通过 (0 冲突)
  1 = 有冲突
  2 = 配置错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = WORKSPACE_ROOT / "docs" / "project-registry.yaml"
SYSTEM_YAML = WORKSPACE_ROOT / ".omo" / "state" / "system.yaml"
GENERATED_GAC_DIGEST = WORKSPACE_ROOT / "docs/generated/agent-gac-rules.md"
GENERATED_LAYER_DIGEST = WORKSPACE_ROOT / "docs/generated/project-layer-index.md"

# ── Stale patterns (always wrong, regardless of registry) ──
STALE_PATTERNS = [
    (r"eCOS\s*v5", "eCOS v5", "过期架构版本, 应为 eCOS v6"),
    (r"5\+3\+1", "5+3+1", "过期架构命名, 应为 5+4+1+1"),
    (r"7\s*层架构", "7 层架构", "过期架构命名, 应为 5+4+1+1"),
    (r"Python\s*3\.10\+", "Python 3.10+", "过期 Python 版本, 应为 3.13+ (见 pyproject.toml)"),
    (r"hermes-console", "hermes-console", "已归档项目名, 应为 cockpit-ui"),
]

# ── Files to scan ──
SCAN_GLOBS = [
    "CLAUDE.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "LAYER-INDEX.md",
    "README.md",
    "CONTRIBUTING.md",
    "DESIGN.md",
    "docs/*.md",
    "projects/AGENTS.md",
    "projects/*/AGENTS.md",
    "projects/*/CLAUDE.md",
    "projects/*/ARCHITECTURE.md",
    "projects/*/README.md",
    "projects/*/BOUNDARY.md",
    "projects/*/GOVERNANCE.md",
]

# ── Exclusion patterns ──
EXCLUDE_SUBSTRINGS = [
    "node_modules",
    ".venv",
    "__pycache__",
    "_archived",
    "/archive/",
    "DOC-ARCH.md",
]


def load_registry() -> dict:
    """Load project-registry.yaml."""
    try:
        import yaml
    except ImportError:
        print("ERROR: pyyaml not installed", file=sys.stderr)
        sys.exit(2)

    if not REGISTRY_PATH.exists():
        print(f"ERROR: registry not found at {REGISTRY_PATH}", file=sys.stderr)
        sys.exit(2)

    with open(REGISTRY_PATH) as f:
        return yaml.safe_load(f)


def find_md_files() -> list[Path]:
    """Find all markdown files to scan."""
    files = []
    for glob_pat in SCAN_GLOBS:
        files.extend(WORKSPACE_ROOT.glob(glob_pat))
    # Deduplicate and filter exclusions
    seen = set()
    result = []
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        path_str = str(f)
        if any(excl in path_str for excl in EXCLUDE_SUBSTRINGS):
            continue
        if f.is_file():
            result.append(f)
    return result


def check_stale_patterns(filepath: Path, content: str, fixes: list) -> list[tuple[int, str, str]]:
    """Check for stale patterns that are always wrong."""
    findings = []
    for pattern, label, reason in STALE_PATTERNS:
        for i, line in enumerate(content.splitlines(), 1):
            if re.search(pattern, line):
                # Skip if it's a historical/archive reference
                if "归档" in line or "archived" in line.lower() or "historical" in line.lower():
                    continue
                findings.append((i, label, reason))
                if fixes is not None:
                    new_line = line
                    if "v5" in label:
                        new_line = new_line.replace("eCOS v5", "eCOS v6")
                    if "5+3+1" in label:
                        new_line = new_line.replace("5+3+1", "5+4+1+1")
                    if "7 层" in label or "7层" in label:
                        new_line = new_line.replace("7 层架构", "5+4+1+1 架构").replace("7层架构", "5+4+1+1 架构")
                    if "3.10+" in label:
                        new_line = new_line.replace("Python 3.10+", "Python 3.13+").replace("Python >=3.10", "Python >=3.13")
                    if "hermes-console" in label:
                        new_line = new_line.replace("hermes-console", "cockpit-ui")
                    if new_line != line:
                        fixes.append((filepath, i, line, new_line))
    return findings


def check_registry_conflicts(filepath: Path, content: str, registry: dict) -> list[tuple[int, str, str]]:
    """Check for hardcoded numbers that conflict with registry."""
    findings = []
    projects = registry.get("projects", {})

    # Check for hardcoded package counts
    for proj_name, proj_data in projects.items():
        pkg_count = proj_data.get("packages")
        if pkg_count:
            for match in re.finditer(rf"{proj_name}.*?(\d+)\s*(?:包|packages|个包)", content, re.IGNORECASE):
                found_num = int(match.group(1))
                if found_num != pkg_count:
                    context_start = max(0, match.start() - 40)
                    context = content[context_start:match.end() + 40]
                    if any(kw in context for kw in ["收敛", "从", "历史", "→", "->", "至", "拆出", "归档", "was ", "from "]):
                        continue
                    line_num = content[:match.start()].count("\n") + 1
                    findings.append((
                        line_num,
                        f"{found_num} 包",
                        f"{proj_name} 包数应为 {pkg_count} (见 project-registry.yaml)"
                    ))

    return findings


def check_semantic_contracts(filepath: Path, content: str) -> list[tuple[int, str, str]]:
    """Check doc ownership rules that are not simple numeric conflicts."""
    findings: list[tuple[int, str, str]] = []
    rel = filepath.relative_to(WORKSPACE_ROOT).as_posix()

    if rel in {"CLAUDE.md", "AGENTS.md", "projects/AGENTS.md"} and "agent-workflow.py\" bootstrap" not in content:
        findings.append((1, "missing bootstrap", "入口文档必须使用 bin/agent-workflow.py bootstrap 作为单入口"))

    if rel == "AGENTS.md":
        start_marker = "<!-- GaC-RULES-START -->"
        end_marker = "<!-- GaC-RULES-END -->"
        if start_marker in content and end_marker in content:
            section = content.split(start_marker, 1)[1].split(end_marker, 1)[0]
            if "| 规则 ID |" in section or "#### X1" in section:
                line_num = content[: content.index(start_marker)].count("\n") + 1
                findings.append((line_num, "embedded GaC table", "AGENTS.md 只能保留 GaC 指针, 完整表应在 docs/generated/agent-gac-rules.md"))

    layer_docs = {"README.md", "AGENTS.md", "ARCHITECTURE.md", "LAYER-INDEX.md", "projects/AGENTS.md"}
    if rel in layer_docs:
        layer_table_patterns = [
            r"(?m)^L4\s+.*->",
            r"(?m)^\| L4(?:\s|\|)",
            r"(?m)^\| L3(?:\s|\|)",
            r"(?m)^\| Layer \| Projects",
            r"(?m)^\| Layer \| Role \| Projects",
        ]
        for pattern in layer_table_patterns:
            match = re.search(pattern, content)
            if match:
                line_num = content[: match.start()].count("\n") + 1
                findings.append((line_num, "embedded layer table", "项目分层表必须从 docs/project-registry.yaml 生成到 docs/generated/project-layer-index.md"))
                break

    return findings


def check_required_generated_artifacts() -> list[tuple[Path, int, str, str]]:
    findings: list[tuple[Path, int, str, str]] = []
    for path, label in [
        (GENERATED_GAC_DIGEST, "agent-gac-rules.md"),
        (GENERATED_LAYER_DIGEST, "project-layer-index.md"),
    ]:
        if not path.exists():
            findings.append((WORKSPACE_ROOT / "AGENTS.md", 1, label, f"缺少生成物 {path.relative_to(WORKSPACE_ROOT)}"))
    return findings


def run_lint(fix: bool = False, single_file: str | None = None, as_json: bool = False) -> int:
    """Run the lint check. Returns 0 (pass) or 1 (fail).

    as_json=True 时输出机器可读 JSON (供 CI 仪表盘/gac-healthcheck 消费).
    """
    registry = load_registry()
    files = [Path(single_file)] if single_file else find_md_files()

    all_findings = []
    all_fixes = [] if fix else None

    for filepath in files:
        if not filepath.exists():
            continue
        content = filepath.read_text(encoding="utf-8", errors="replace")

        # Check stale patterns
        findings = check_stale_patterns(filepath, content, all_fixes)
        for line_num, label, reason in findings:
            all_findings.append((filepath, line_num, label, reason))

        # Check registry conflicts
        conflicts = check_registry_conflicts(filepath, content, registry)
        for line_num, label, reason in conflicts:
            all_findings.append((filepath, line_num, label, reason))

        semantic_findings = check_semantic_contracts(filepath, content)
        for line_num, label, reason in semantic_findings:
            all_findings.append((filepath, line_num, label, reason))

    if single_file is None:
        all_findings.extend(check_required_generated_artifacts())

    # Apply fixes
    if all_fixes:
        applied = 0
        # Group fixes by file to avoid read/write conflicts
        file_fixes: dict[Path, list[tuple[int, str, str]]] = {}
        for filepath, line_num, old_line, new_line in all_fixes:
            file_fixes.setdefault(filepath, []).append((line_num, old_line, new_line))

        for filepath, fixes in file_fixes.items():
            content = filepath.read_text(encoding="utf-8")
            # Sort fixes by line number descending so earlier fixes don't shift line numbers
            for line_num, old_line, new_line in sorted(fixes, key=lambda x: x[0], reverse=True):
                # Use direct string replacement (more robust than line matching)
                if old_line in content:
                    content = content.replace(old_line, new_line, 1)
                    applied += 1
            filepath.write_text(content, encoding="utf-8")
        if not as_json:
            print(f"已自动修复 {applied} 处")

    # Report (JSON 分支: 机器可读, 供 gac-healthcheck/CI 仪表盘消费)
    if as_json:
        payload = {
            "ok": len(all_findings) == 0,
            "conflicts": len(all_findings),
            "files_scanned": len(files),
            "findings": [
                {
                    "file": str(fp.relative_to(WORKSPACE_ROOT)),
                    "line": line_num,
                    "label": label,
                    "reason": reason,
                }
                for fp, line_num, label, reason in all_findings
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1

    # Report (人类可读)
    if all_findings:
        print(f"❌ 检测到 {len(all_findings)} 项文档 SSOT 冲突:\n")
        for filepath, line_num, label, reason in all_findings:
            rel_path = filepath.relative_to(WORKSPACE_ROOT)
            print(f"  {rel_path}:{line_num}")
            print(f"    发现: {label}")
            print(f"    原因: {reason}")
            print()
        print("修复方式:")
        print("  1. 手动修改为 SSOT 指针 (见 .omo/standards/doc-ssot-contract.md)")
        print("  2. 或运行: python3 bin/doc-ssot-lint.py --fix")
        return 1
    else:
        print(f"✅ 文档 SSOT 检查通过 (扫描 {len(files)} 文件, 0 冲突)")
        return 0


def main():
    parser = argparse.ArgumentParser(description="文档 SSOT 正交契约门禁")
    parser.add_argument("--fix", action="store_true", help="自动修复已知模式")
    parser.add_argument("--file", type=str, help="只检查单个文件")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON (CI/仪表盘消费)")
    args = parser.parse_args()

    return run_lint(fix=args.fix, single_file=args.file, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
