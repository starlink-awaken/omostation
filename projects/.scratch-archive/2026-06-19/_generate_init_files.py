#!/usr/bin/env python3
"""
Generate subdirectory __init__.py files for kairon_lib package restructuring.

This script:
1. Renames flat .py files that conflict with new subdirectory names
2. Creates subdirectories: audit/, cognitive/, metrics/, core/
3. Generates __init__.py files that re-export public symbols from flat modules
4. Updates existing governance/__init__.py
5. Updates root kairon_lib/__init__.py

The original flat .py files stay in kairon_lib/ as the source of truth.
"""

from __future__ import annotations

import ast
import os
import shutil
from pathlib import Path

LIB_DIR = Path(
    "/Users/xiamingxing/Workspace/projects/kairon/packages/shared-lib/src/kairon_lib"
)

# ── Category definitions ──────────────────────────────────────────────────────
# Each category maps to a subdirectory name and a set of flat module names.
# Modules can belong to only one category.

CATEGORIES: dict[str, list[str]] = {
    "governance": [
        "action_rollback",
        "agent_consensus",
        "ai_committee",
        "approval_escalation_matrix",
        "approval_observability",
        "approval_persistence",
        "approval_queue",
        "approval_router",
        "approval_router_observability",
        "approval_router_persistence",
        "architecture",
        "bootstrap",
        "committee",
        "committee_hall",
        "competency_tracker",
        "consensus_mechanism",
        "decision_journal",
        "decision_receipt",
        "dynamic_role_assigner",
        "edge",
        "ethical_governance",
        "execution_strategy",
        "extensions",
        "federated_learning",
        "federation_hive",
        "formal_method",
        "governance_engine",
        "governance_observability",
        "human_in_the_loop",
        "hybrid",
        "identity_federation",
        "incentive_alignment",
        "lifecycle",
        "phase_manager",
        "policy_registry",
        "principles",
        "quarantine",
        "rbac",
        "review_pipeline",
        "rfc_lifecycle",
        "rfc_promotion",
        "risk_classifier",
        "role_hot_swap",
        "role_rbac",
        "role_slo_registry",
        "rollback_decision_gates",
        "security",
        "security_best_practices",
        "security_practices",
        "threat",
        "tool_composer",
        "tool_registry",
        "user_veto",
        "validation",
        "verification",
        "voting_framework",
        "weighted_voting",
    ],
    "audit": [
        "audit",
        "audit_query",
        "audit_trail",
        "adr_storage",
        "retrospective",
        "retrospective_automation",
    ],
    "cognitive": [
        "agents_md",
        "cognitive_loop",
        "consolidation_state_machine",
        "context",
        "conversation",
        "delivery_loop",
        "emergency_stop",
        "intelligence",
        "knowledge_graph",
        "knowledge_toolkit",
        "local_reflex",
        "local_reflex_test",
        "markdown_parser",
        "orchestrator",
        "pattern_fabric",
        "pattern_loader",
        "patterns",
        "rag_engine",
        "reasoning",
        "reasoning_auditor",
        "rl_cognitive_loop",
        "scenario_engine",
        "self_contained_cognitive_loop",
        "telos_context",
        "thinking",
        "uri_models",
        "workflow_engine",
        "workflow_team",
        "xai_framework",
    ],
    "metrics": [
        "capability_standardization",
        "evolution_metrics",
        "harvest_scheduler",
        "observability_toolkit",
        "qa",
        "slo",
    ],
    "core": [
        "agent_toolkit_client",
        "auto_executor",
        "autogen",
        "beads_adapter",
        "cognition_bridge",
        "core",
        "errors",
        "events",
        "figma_integration",
        "integrations_mcp",
        "llm_clients",
        "llm_toolkit",
        "mcp_servers",
        "memory_store",
        "middleware",
        "middleware_chain",
        "openai_converter",
        "opencontext_adapter",
        "operation_level",
        "playwright_integration",
        "plugin",
        "runnable_chain",
        "session",
        "skill_system",
        "snapshot",
        "storage_adapter",
        "testing",
        "tuning",
        "vercel_deploy",
    ],
}

# ── Files to rename (conflict with subdirectory names) ────────────────────────
RENAME_MAP = {
    "audit.py": "_audit_inline.py",
    "core.py": "_core_inline.py",
}

# ── Flatten all categorized modules ───────────────────────────────────────────
ALL_CATEGORIZED = set()
for mods in CATEGORIES.values():
    ALL_CATEGORIZED.update(mods)

# Verify all flat modules are categorized
EXISTING_FLAT = sorted(
    p.stem
    for p in LIB_DIR.iterdir()
    if p.suffix == ".py"
    and p.name not in ("__init__.py", "_compat.py")
    and not p.name.startswith("_")
    and p.stem
    not in {
        "compliance",
        "extractors",
        "governance",
        "integration",
        "monitoring",
        "observability",
        "plugin_sdk",
        "quality",
        "sources",
        "utils",
    }
)

# Report uncategorized modules
uncategorized = [m for m in EXISTING_FLAT if m not in ALL_CATEGORIZED]
if uncategorized:
    print(f"⚠️  Uncategorized modules: {uncategorized}")
else:
    print("✅ All flat modules categorized.")


def extract_public_names(filepath: Path) -> dict[str, list[str]]:
    """Extract public names (classes, functions, public variables) from a Python file."""
    with open(filepath) as f:
        try:
            tree = ast.parse(f.read())
        except SyntaxError as e:
            print(f"  ⚠️  Syntax error in {filepath.name}: {e}")
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


def generate_init_for_category(category: str, modules: list[str]) -> str:
    """Generate __init__.py content for a given category/subdirectory."""
    lines: list[str] = []
    lines.append('"""')
    lines.append(f"{category.capitalize()} — organized submodule for kairon_lib.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")

    all_exports: list[str] = []
    seen: set[str] = set()

    for mod_name in sorted(modules):
        # Check if the file was renamed
        renamed_name = RENAME_MAP.get(f"{mod_name}.py")
        source_module = renamed_name.replace(".py", "") if renamed_name else mod_name
        flat_file = LIB_DIR / (renamed_name or f"{mod_name}.py")

        if not flat_file.exists():
            print(f"  ⚠️  Module {mod_name}.py not found at {flat_file}, skipping")
            continue

        names = extract_public_names(flat_file)
        class_names = names["classes"]
        func_names = names["functions"]
        var_names = names["variables"]

        if not class_names and not func_names and not var_names:
            # Module with no public symbols - just import the module itself
            lines.append(f"from kairon_lib import {source_module}")
            lines.append(f"from kairon_lib.{source_module} import (")
            lines.append("    # (no public exports detected)")
            lines.append(")")
            lines.append("")
            continue

        all_symbols = class_names + func_names + var_names
        # Deduplicate
        unique_symbols = sorted(set(all_symbols))

        # Filter out duplicates across modules (same symbol name in different modules)
        new_symbols = [s for s in unique_symbols if s not in seen]
        seen.update(new_symbols)
        all_exports.extend(new_symbols)

        if not new_symbols:
            # All symbols already exported by other modules
            continue

        lines.append(f"from kairon_lib.{source_module} import (")
        for sym in new_symbols:
            lines.append(f"    {sym},")
        lines.append(")")
        lines.append("")

    # Generate __all__
    # Sort exports, remove non-identifier names
    clean_exports = sorted(set(all_exports))
    lines.append("")
    lines.append("__all__ = (")
    for sym in clean_exports:
        lines.append(f'    "{sym}",')
    lines.append(")")
    lines.append("")

    return "\n".join(lines)


def main():
    # Step 1: Rename conflicting flat files
    print("\n=== Step 1: Rename conflicting flat files ===")
    for old_name, new_name in RENAME_MAP.items():
        old_path = LIB_DIR / old_name
        new_path = LIB_DIR / new_name
        if old_path.exists():
            if new_path.exists():
                print(f"  ✅ {old_name} → {new_name} (target already exists, skipping)")
            else:
                shutil.move(str(old_path), str(new_path))
                print(f"  ✅ Renamed {old_name} → {new_name}")
        else:
            print(f"  ⚠️  {old_name} not found at {old_path}")

    # Step 2: Create subdirectories
    print("\n=== Step 2: Create subdirectories ===")
    for category in CATEGORIES:
        if category == "governance":
            print(f"  ℹ️  governance/ already exists, skipping creation")
            continue
        dir_path = LIB_DIR / category
        dir_path.mkdir(exist_ok=True)
        print(f"  ✅ Created {category}/")

    # Step 3: Generate/update __init__.py for each subdirectory
    print("\n=== Step 3: Generate __init__.py files ===")
    for category, modules in CATEGORIES.items():
        print(f"\n  --- {category}/ ({len(modules)} modules) ---")
        content = generate_init_for_category(category, modules)
        init_path = LIB_DIR / category / "__init__.py"
        with open(init_path, "w") as f:
            f.write(content)
        lines_count = len(content.split("\n"))
        print(f"  ✅ Wrote {init_path} ({lines_count} lines)")

    # Step 4: Update root __init__.py
    print("\n=== Step 4: Update root __init__.py ===")
    root_init = LIB_DIR / "__init__.py"
    root_content = root_init.read_text()

    # Add imports from subdirectories
    extra_imports = []
    extra_imports.append("\n# ── Re-exports from organized subdirectories ──────────────\n")
    for category, modules in CATEGORIES.items():
        extra_imports.append(f"from kairon_lib.{category} import *  # noqa: F401, F403")
    extra_imports.append("")

    # Find where to insert - after the existing __all__
    insertion_point = root_content.find("__all__ = (")
    if insertion_point > 0:
        # Find the closing paren
        close_paren = root_content.find(")", insertion_point)
        insertion_idx = close_paren + 1
        new_root = root_content[:insertion_idx] + "\n" + "\n".join(extra_imports) + root_content[insertion_idx:]
    else:
        # Append at the end
        new_root = root_content.rstrip() + "\n\n" + "\n".join(extra_imports) + "\n"

    # Add to __all__ as well if it exists
    root_init.write_text(new_root)
    print("  ✅ Updated root __init__.py")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
