#!/usr/bin/env python3
import ast
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR = REPO_ROOT / ".omo/_archive/scripts"
REGISTRY_SCRIPT = REPO_ROOT / "bin/ssot/script-registry.py"

def run_cmd(cmd, cwd=REPO_ROOT):
    try:
        return subprocess.check_output(cmd, cwd=cwd, shell=True, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return ""

def get_docstring(filepath: Path) -> str:
    if filepath.suffix == ".py":
        try:
            content = filepath.read_text()
            tree = ast.parse(content)
            doc = ast.get_docstring(tree)
            return doc.strip() if doc else ""
        except Exception:
            return ""
    elif filepath.suffix == ".sh":
        try:
            lines = filepath.read_text().splitlines()
            docs = []
            for line in lines:
                if line.startswith("#!"):
                    continue
                if line.startswith("#"):
                    docs.append(line.lstrip("#").strip())
                elif line.strip() != "":
                    break
            return " ".join(docs)
        except Exception:
            return ""
    return ""

def is_dead(filepath: Path) -> bool:
    rel_path = filepath.relative_to(REPO_ROOT)

    # Check Git activity in the last 90 days
    git_log = run_cmd(f"git log --since='90 days' --oneline -- {rel_path}").strip()
    if git_log:
        return False

    # Check incoming references via grep
    stem = filepath.stem.replace('_', '-')
    stem_py = filepath.stem.replace('-', '_')

    # Exclude the registry yaml and the file itself from the count
    grep_cmd = f"git grep -l -E '{stem}|{stem_py}' -- .github Makefile bin projects"
    refs = run_cmd(grep_cmd).strip().splitlines()

    valid_refs = []
    for ref in refs:
        if not ref.strip():
            continue
        if str(rel_path) in ref or "bin/_registry/scripts/" in ref:
            continue
        valid_refs.append(ref)

    if len(valid_refs) > 0:
        return False

    return True

def main():
    print("=== Phase 4: The Great Pruning & Capability Ascension ===")

    targets = []

    for p in (REPO_ROOT / "bin").rglob("*"):
        if p.is_file() and p.suffix in (".py", ".sh") and "_registry" not in p.parts and not p.name.startswith("_"):
            targets.append(p)

    projects_dir = REPO_ROOT / "projects"
    if projects_dir.exists():
        for p in projects_dir.iterdir():
            if p.is_dir() and (p / "bin").exists():
                for s in (p / "bin").rglob("*.py"):
                    targets.append(s)
                for s in (p / "bin").rglob("*.sh"):
                    targets.append(s)

    dead_count = 0
    survivors = []

    print(f"Analyzing {len(targets)} scripts...")

    for filepath in targets:
        if filepath.name == "prune-and-register.py" or filepath.name == "script-registry.py":
            survivors.append(filepath)
            continue

        if is_dead(filepath):
            rel = filepath.relative_to(REPO_ROOT)
            dest = ARCHIVE_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)

            if run_cmd(f"git ls-files {rel}"):
                subprocess.call(["git", "mv", str(rel), str(dest.relative_to(REPO_ROOT))], cwd=REPO_ROOT)
            else:
                shutil.move(str(filepath), str(dest))

            dead_count += 1
            print(f"[ARCHIVED] {rel}")
        else:
            survivors.append(filepath)

    print("\n--- Pruning Complete ---")
    print(f"Archived {dead_count} dead scripts.")
    print(f"Registering {len(survivors)} surviving scripts...\n")

    for filepath in survivors:
        rel = filepath.relative_to(REPO_ROOT)
        subprocess.call(["python3", str(REGISTRY_SCRIPT), "register", str(rel)], cwd=REPO_ROOT, stdout=subprocess.DEVNULL)

        docstring = get_docstring(filepath)
        if docstring:
            stem = filepath.stem
            for yaml_file in (REPO_ROOT / "bin/_registry/scripts").rglob(f"{stem}.yaml"):
                content = yaml_file.read_text()
                safe_doc = repr(docstring)
                content = content.replace('description: ""', f'description: {safe_doc}')
                yaml_file.write_text(content)

    print("\n[SUCCESS] Registration complete. Run `python3 bin/ssot/script-registry.py validate` to confirm.")

if __name__ == "__main__":
    main()
