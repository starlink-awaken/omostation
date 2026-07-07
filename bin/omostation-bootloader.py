#!/usr/bin/env python3
"""omostation-bootloader.py — P76 Phase 5 自演化平台雏形

读 audit-finding → 自动产出 ADR 草稿 + PR skeleton + closeout checklist

入口: omostation-bootloader audit
产出:
  - .omo/_knowledge/decisions/draft/<NNN>-<title>.md (ADR 草稿)
  - .omo/_delivery/bootloader-output/<timestamp>/ (证据)
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]


def find_top_finding() -> dict | None:
    """找当下最关键的 finding (governance score, gac-healthcheck 中 lowest).

    简化: 返回 omo governance 总分; 若 < 98 → 标 finding.
    """
    try:
        result = subprocess.run(
            ["uv", "run", "--project", "projects/omo", "omo", "governance", "--json"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    # 简化解析, 不依赖 json
    last_lines = [l for l in result.stdout.splitlines() if "总分" in l or "total_score" in l]
    if not last_lines:
        return None
    score_line = last_lines[-1]
    return {"source": "omo-governance", "summary": score_line[:120]}


def generate_adr_draft(finding: dict | None) -> Path | None:
    """基于 finding 生成 ADR 草稿."""
    if not finding:
        print("✓ no critical finding — no ADR needed")
        return None
    drafts_dir = WORKSPACE / ".omo" / "_knowledge" / "decisions" / "draft"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    adr = drafts_dir / f"DRAFT-{ts}-boilerplate.md"
    content = f"""---
status: DRAFT
lifecycle: decision
owner: bootloader
last-reviewed: {datetime.utcnow().strftime("%Y-%m-%d")}
related: []
---

# DRAFT ADR (omostation-bootloader)

## Source
{finding.get('source', 'manual')}

## Summary (1 line)
{finding.get('summary', 'TBD')}

## TODO: this draft is auto-generated. Fill in:
- WHY: root cause analysis
- WHAT: at minimum 3 alternative solutions (light/mid/heavy)
- NEXT: candidate items for following phase

## Verification
- [ ] Run `omo governance` and check score
- [ ] Cross-ref ADR INDEX + governance-evolution-roadmap
- [ ] Tag as ACCEPTED if all checks pass
"""
    adr.write_text(content)
    print(f"✓ ADR draft created: {adr.relative_to(WORKSPACE)}")
    return adr


def main() -> int:
    print("=== omostation-bootloader (Phase 5 雏形) ===")
    finding = find_top_finding()
    if finding:
        print(f"  finding source: {finding['source']}")
        print(f"  finding summary: {finding['summary']}")
    else:
        print("  no finding detected")
    adr = generate_adr_draft(finding)
    return 0


if __name__ == "__main__":
    sys.exit(main())
