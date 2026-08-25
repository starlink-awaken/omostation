#!/usr/bin/env python3
"""fix-frontmatter: 自动为 Markdown 文档补齐合规 Frontmatter."""
import argparse
import sys
import datetime
from pathlib import Path

DEFAULT_FRONTMATTER = f"""---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-24
---
"""

def fix_file(filepath: Path) -> bool:
    if not filepath.exists() or not filepath.is_file() or filepath.suffix != ".md":
        return False
    content = filepath.read_text(encoding="utf-8")
    if content.lstrip().startswith("---"):
        # has some frontmatter, skip or just warn for now
        # auto-fix-loop specifically targets files without frontmatter or missing fields
        # To be safe, if it has "---", we don't mess with it in this simple version
        return False
    
    # insert default frontmatter at the very top
    new_content = DEFAULT_FRONTMATTER + "\n" + content
    filepath.write_text(new_content, encoding="utf-8")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="Files to fix")
    args = parser.parse_args()
    
    fixed = 0
    for f in args.files:
        if fix_file(Path(f)):
            fixed += 1
            print(f"Fixed: {f}")
    
    if fixed > 0:
        return 0
    else:
        print("No files fixed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
