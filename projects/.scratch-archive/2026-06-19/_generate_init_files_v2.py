#!/usr/bin/env python3
"""
Generate __init__.py files for existing kairon_lib subdirectories.

The flat .py files have already been converted to re-export stubs that
point to actual content in subdirectories. This script:
1. Stubs the two remaining flat files (audit.py, core.py) that still
   have their original content (were restored from git).
2. Generates proper __init__.py files for each subdirectory that
   re-export all public symbols from their module files.
3. Updates the root __init__.py.
"""

from __future__ import annotations

import ast
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent / "packages" / "shared-lib" / "src" / "kairon_lib"

# Subdirectories (all already exist with content files)
SUBDIRS = ["governance", "audit", "cognitive", "metrics", "core"]

# Flat files that still need stubbing (restored from git, content already in subdir)
FILES_TO_STUB = {
    "audit.py": "kairon_lib.audit.audit",
    "core.py": "kairon_lib.core.core",
}


def extract_public_names(filepath: Path) -> dict[str, list[str]]:
    """Extract public names from a Python file."""
    with open(filepath) as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError as e:
            print(f"  WARNING: Syntax error in {filepath.name}: {e}")
            return {"classes": [], "functions": [], "variables": []}

    classes: list[str] = []
    functions: list[str] = []
    variables: list[str] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)
        elif isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            functions.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    variables.append(target.id)

    return {"classes": classes, "functions": functions, "variables": variables}


def generate_subdir_init(subdir: Path) -> str:
    """Generate __init__.py for a subdirectory that re-exports all its modules."""
    lines: list[str] = []
    category = subdir.name
    lines.append('"""')
    lines.append(f"{category.capitalize()} — organized submodule for kairon_lib.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")

    # Find all .py files in subdirectory (excluding __init__.py)
    module_files = sorted(
        p for p in subdir.iterdir() if p.suffix == ".py" and p.name != "__init__.py"
    )

    all_exports: list[str] = []
    seen: set[str] = set()
    export_lines: list[str] = []

    for mod_path in module_files:
        mod_name = mod_path.stem
        names = extract_public_names(mod_path)
        symbol_names = sorted(set(names["classes"] + names["functions"] + names["variables"]))

        if not symbol_names:
            # Module with no public symbols detected - use import * for backward compat
            export_lines.append(f"from kairon_lib.{category}.{mod_name} import *  # noqa: F401, F403")
            export_lines.append("")
            continue

        # Filter duplicates across modules
        new_symbols = sorted(set(s for s in symbol_names if s not in seen))
        seen.update(new_symbols)
        all_exports.extend(new_symbols)

        if new_symbols:
            export_lines.append(f"from kairon_lib.{category}.{mod_name} import (")
            for sym in new_symbols:
                export_lines.append(f"    {sym},")
            export_lines.append(")")
            export_lines.append("")

    lines.extend(export_lines)

    # Generate __all__
    clean_exports = sorted(set(all_exports))
    lines.append("")
    lines.append("__all__ = (")
    for sym in clean_exports:
        lines.append(f'    "{sym}",')
    lines.append(")")
    lines.append("")

    return "\n".join(lines)


def main():
    # Step 1: Stub remaining flat files
    print("=== Step 1: Stub flat files ===")
    for filename, import_target in FILES_TO_STUB.items():
        filepath = LIB_DIR / filename
        stub_content = f'"""Backward-compat re-export."""\nfrom {import_target} import *  # noqa: F401, F403\n'
        with open(filepath, "w") as f:
            f.write(stub_content)
        print(f"  Stubbed {filename} -> {import_target}")

    # Step 2: Generate/update __init__.py for each subdirectory
    print("\n=== Step 2: Generate subdirectory __init__.py files ===")
    for subdir_name in SUBDIRS:
        subdir_path = LIB_DIR / subdir_name
        if not subdir_path.is_dir():
            print(f"  WARNING: {subdir_name}/ does not exist, creating it")
            subdir_path.mkdir()

        content = generate_subdir_init(subdir_path)
        init_path = subdir_path / "__init__.py"
        with open(init_path, "w") as f:
            f.write(content)
        module_count = len(list(subdir_path.glob("*.py"))) - 1  # exclude __init__.py
        print(f"  Updated {subdir_name}/__init__.py ({len(content.splitlines())} lines, {module_count} modules)")

    # Step 3: Update root __init__.py
    print("\n=== Step 3: Update root __init__.py ===")
    root_init = LIB_DIR / "__init__.py"
    root_content = root_init.read_text()

    extra_imports = []
    extra_imports.append("# ── Re-exports from organized subdirectories (new structure) ──\n")
    for subdir_name in SUBDIRS:
        extra_imports.append(f"from kairon_lib.{subdir_name} import *  # noqa: F401, F403\n")
    extra_imports.append("")

    # Find where to insert - after the existing __all__
    insertion_point = root_content.find("__all__ = (")
    if insertion_point > 0:
        close_paren = root_content.find(")", insertion_point)
        insertion_idx = close_paren + 1
        extra_text = "\n" + "\n".join(extra_imports)
        new_root = root_content[:insertion_idx] + extra_text + root_content[insertion_idx:]
    else:
        new_root = root_content.rstrip() + "\n\n" + "\n".join(extra_imports) + "\n"

    root_init.write_text(new_root)
    print(f"  Updated root __init__.py (was {len(root_content.splitlines())} lines)")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
