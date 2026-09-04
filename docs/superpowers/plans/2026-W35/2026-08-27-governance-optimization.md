---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-08-29
type: ssot
last_updated: 2026-09-03
---
# Governance Optimization & Anti-Corrosion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish long-term governance health through automated monitoring, anti-corrosion mechanisms, and documentation updates.

**Architecture:** Multi-layer defense: automated drift detection → fix → verify → report. Each layer is independently testable and can be disabled without breaking others.

**Tech Stack:** Python 3.13+, Bash, YAML, GitHub Actions

---

## Global Constraints

- Python >= 3.13 (workspace standard)
- All scripts must pass `make gac-local-gate`
- No new dependencies unless absolutely necessary
- Follow existing patterns in `bin/gac/` and `bin/ssot/`
- All changes must have corresponding tests
- Documentation must be updated for any new scripts

---

## Task 1: Governance Health Monitor

**Purpose:** Daily automated health report tracking governance metrics over time.

**Files:**
- Create: `bin/gac/governance-health-monitor.py`
- Create: `tests/test_governance_health_monitor.py`
- Modify: `.github/workflows/governance-check.yml` (add health report step)

**Interfaces:**
- Consumes: `bin/gac/governance-convergence-lint.py --json`, `bin/gac/governance-semantic-gate.py --json`, `bin/gac/check-execution-chain.py --json`
- Produces: `.omo/state/governance-health-history.json` (append-only log)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_governance_health_monitor.py
import json
from pathlib import Path
from bin.gac.governance_health_monitor import collect_metrics, append_history

def test_collect_metrics():
    metrics = collect_metrics()
    assert "timestamp" in metrics
    assert "convergence_errors" in metrics
    assert "semantic_blocking" in metrics
    assert "legacy_cr_ids_count" in metrics

def test_append_history(tmp_path):
    history_file = tmp_path / "health-history.json"
    metrics = {"timestamp": "2026-08-27T00:00:00Z", "convergence_errors": 0}
    append_history(history_file, metrics)
    data = json.loads(history_file.read_text())
    assert len(data) == 1
    assert data[0]["convergence_errors"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_governance_health_monitor.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write implementation**

```python
# bin/gac/governance_health_monitor.py
#!/usr/bin/env python3
"""Daily governance health monitoring and historical tracking."""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HISTORY_FILE = WORKSPACE / ".omo/state/governance-health-history.json"

def collect_metrics() -> dict:
    metrics = {"timestamp": datetime.now(UTC).isoformat()}
    
    # Convergence lint
    try:
        r = subprocess.run(
            [sys.executable, "bin/gac/governance-convergence-lint.py", "--json"],
            cwd=WORKSPACE, capture_output=True, text=True, timeout=60
        )
        d = json.loads(r.stdout)
        metrics["convergence_errors"] = len(d.get("errors", []))
        metrics["convergence_warnings"] = len(d.get("warnings", []))
    except Exception:
        metrics["convergence_errors"] = -1
    
    # Semantic gate
    try:
        r = subprocess.run(
            [sys.executable, "bin/gac/governance-semantic-gate.py", "--json"],
            cwd=WORKSPACE, capture_output=True, text=True, timeout=120
        )
        d = json.loads(r.stdout)
        metrics["semantic_ok"] = d.get("ok", False)
        metrics["semantic_blocking"] = d.get("blocking_failures", 0)
    except Exception:
        metrics["semantic_ok"] = False
        metrics["semantic_blocking"] = -1
    
    # LEGACY_CR_IDS count
    try:
        import re
        script = (WORKSPACE / "bin/gac/governance-convergence-lint.py").read_text()
        match = re.search(r"LEGACY_CR_IDS\s*=\s*\{([^}]+)\}", script, re.DOTALL)
        if match:
            metrics["legacy_cr_ids_count"] = len(re.findall(r'"[^"]+"', match.group(1)))
        else:
            metrics["legacy_cr_ids_count"] = 0
    except Exception:
        metrics["legacy_cr_ids_count"] = -1
    
    return metrics

def append_history(history_file: Path, metrics: dict) -> None:
    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text())
        except Exception:
            history = []
    history.append(metrics)
    # Keep last 90 days
    if len(history) > 90:
        history = history[-90:]
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False))

def main() -> int:
    metrics = collect_metrics()
    append_history(HISTORY_FILE, metrics)
    print(f"Governance health: {json.dumps(metrics, indent=2)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_governance_health_monitor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/gac/governance_health_monitor.py tests/test_governance_health_monitor.py
git commit -m "feat(gac): add governance health monitor for daily tracking"
```

---

## Task 2: Anti-Corrosion Drift Detector

**Purpose:** Detect governance rule staleness and auto-suggest fixes.

**Files:**
- Create: `bin/gac/anti-corrosion-detector.py`
- Create: `tests/test_anti_corrosion_detector.py`

**Interfaces:**
- Consumes: `bin/gac/governance-convergence-lint.py`, `.omo/_truth/registry/governance-checks.yaml`
- Produces: Drift report with actionable suggestions

- [ ] **Step 1: Write the failing test**

```python
# tests/test_anti_corrosion_detector.py
from pathlib import Path
from bin.gac.anti_corrosion_detector import detect_stale_rules, suggest_fixes

def test_detect_stale_rules():
    stale = detect_stale_rules()
    assert isinstance(stale, list)
    for rule in stale:
        assert "id" in rule
        assert "reason" in rule

def test_suggest_fixes():
    fixes = suggest_fixes()
    assert isinstance(fixes, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_anti_corrosion_detector.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write implementation**

```python
# bin/gac/anti_corrosion_detector.py
#!/usr/bin/env python3
"""Detect governance rule staleness and suggest fixes."""

import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

def detect_stale_rules() -> list[dict]:
    stale = []
    checks_yaml = WORKSPACE / ".omo/_truth/registry/governance-checks.yaml"
    if not checks_yaml.exists():
        return stale
    
    content = checks_yaml.read_text()
    # Find rules with lifecycle != active
    for match in re.finditer(r"- id: (CR-[^\n]+)\n.*?lifecycle: (\w+)", content, re.DOTALL):
        rule_id, lifecycle = match.groups()
        if lifecycle != "active":
            stale.append({"id": rule_id.strip(), "reason": f"lifecycle={lifecycle}", "fix": "Review and update lifecycle or remove"})
    
    return stale

def suggest_fixes() -> list[dict]:
    fixes = []
    # Check LEGACY_CR_IDS size
    script = (WORKSPACE / "bin/gac/governance-convergence-lint.py").read_text()
    match = re.search(r"LEGACY_CR_IDS\s*=\s*\{([^}]+)\}", script, re.DOTALL)
    if match:
        count = len(re.findall(r'"[^"]+"', match.group(1)))
        if count > 80:
            fixes.append({"area": "LEGACY_CR_IDS", "current": count, "threshold": 80, "fix": "Audit and remove unreferenced entries"})
    
    # Check for stale ADR references
    adr_dir = WORKSPACE / ".omo/_knowledge/decisions"
    if adr_dir.exists():
        for adr_file in adr_dir.glob("*.md"):
            content = adr_file.read_text()
            if "Status: SUPERSEDED" in content or "Status: DEPRECATED" in content:
                fixes.append({"area": "ADR", "file": adr_file.name, "fix": "Archive or remove"})
    
    return fixes

def main() -> int:
    print("=== Stale Rules ===")
    for rule in detect_stale_rules():
        print(f"  {rule['id']}: {rule['reason']}")
    
    print("\n=== Suggested Fixes ===")
    for fix in suggest_fixes():
        print(f"  {fix['area']}: {fix['fix']}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_anti_corrosion_detector.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/gac/anti_corrosion_detector.py tests/test_anti_corrosion_detector.py
git commit -m "feat(gac): add anti-corrosion detector for rule staleness"
```

---

## Task 3: Documentation Auto-Update

**Purpose:** Automatically update documentation when code changes.

**Files:**
- Create: `bin/gac/doc-auto-update.py`
- Create: `tests/test_doc_auto_update.py`

**Interfaces:**
- Consumes: `bin/ssot/doc-governance-check.py`, `docs/generated/`
- Produces: Updated documentation files

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doc_auto_update.py
from pathlib import Path
from bin.gac.doc_auto_update import check_stale_docs, generate_update_plan

def test_check_stale_docs():
    stale = check_stale_docs()
    assert isinstance(stale, list)

def test_generate_update_plan():
    plan = generate_update_plan()
    assert isinstance(plan, list)
    for item in plan:
        assert "file" in item
        assert "action" in item
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_doc_auto_update.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write implementation**

```python
# bin/gac/doc_auto_update.py
#!/usr/bin/env python3
"""Automatically detect and update stale documentation."""

import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

def check_stale_docs() -> list[dict]:
    stale = []
    # Check docs/generated/ for stale files
    gen_dir = WORKSPACE / "docs/generated"
    if gen_dir.exists():
        for f in gen_dir.glob("*.md"):
            # Check if file is older than 7 days
            import time
            age_days = (time.time() - f.stat().st_mtime) / 86400
            if age_days > 7:
                stale.append({"file": str(f.relative_to(WORKSPACE)), "age_days": round(age_days, 1)})
    return stale

def generate_update_plan() -> list[dict]:
    plan = []
    stale = check_stale_docs()
    for item in stale:
        plan.append({"file": item["file"], "action": "regenerate", "reason": f"stale by {item['age_days']} days"})
    return plan

def main() -> int:
    print("=== Stale Documentation ===")
    for item in check_stale_docs():
        print(f"  {item['file']}: {item['age_days']} days old")
    
    print("\n=== Update Plan ===")
    for item in generate_update_plan():
        print(f"  {item['file']}: {item['action']}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_doc_auto_update.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/gac/doc_auto_update.py tests/test_doc_auto_update.py
git commit -m "feat(gac): add documentation auto-update detector"
```

---

## Task 4: Pre-Push Hook Optimization

**Purpose:** Reduce pre-push hook execution time by caching results.

**Files:**
- Modify: `.git/hooks/pre-push` (add caching logic)

**Interfaces:**
- Consumes: Existing pre-push checks
- Produces: Cached results for faster subsequent pushes

- [ ] **Step 1: Add caching to pre-push hook**

Add at the beginning of the hook (after shebang and set commands):

```bash
# Cache configuration
CACHE_DIR="/tmp/gac-pre-push-cache"
CACHE_TTL=300  # 5 minutes

mkdir -p "$CACHE_DIR"

check_cached() {
    local check_name="$1"
    local cache_file="$CACHE_DIR/$check_name"
    if [ -f "$cache_file" ]; then
        local cache_age=$(( $(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file" 2>/dev/null || echo 0) ))
        if [ "$cache_age" -lt "$CACHE_TTL" ]; then
            return 0  # Cache hit
        fi
    fi
    return 1  # Cache miss
}

set_cache() {
    local check_name="$1"
    echo "cached" > "$CACHE_DIR/$check_name"
}
```

- [ ] **Step 2: Apply caching to slow checks**

Wrap slow checks with cache logic:

```bash
# Example for a slow check
if ! check_cached "gac-local-gate"; then
    # Run the actual check
    python3 bin/gac/gac-local-gate.py || exit 1
    set_cache "gac-local-gate"
fi
```

- [ ] **Step 3: Test the hook**

Run: `git push --dry-run`
Expected: Faster execution on second run

- [ ] **Step 4: Commit**

```bash
git add .git/hooks/pre-push
git commit -m "perf(gac): add caching to pre-push hook for faster execution"
```

---

## Task 5: Documentation Updates

**Purpose:** Update all relevant documentation for the new governance tools.

**Files:**
- Modify: `bin/README.md` (add new scripts)
- Modify: `AGENTS.md` (add governance health monitoring section)
- Modify: `docs/INDEX-TOOLS.md` (add new tools)

**Interfaces:**
- Consumes: All new scripts from Tasks 1-4
- Produces: Updated documentation

- [ ] **Step 1: Update bin/README.md**

Add to the governance scripts section:

```markdown
### Governance Health Monitoring

| Script | Purpose | Usage |
|--------|---------|-------|
| `bin/gac/governance_health_monitor.py` | Daily health metrics tracking | `python3 bin/gac/governance_health_monitor.py` |
| `bin/gac/anti_corrosion_detector.py` | Rule staleness detection | `python3 bin/gac/anti_corrosion_detector.py` |
| `bin/gac/doc_auto_update.py` | Documentation freshness check | `python3 bin/gac/doc_auto_update.py` |
| `bin/gac/auto-sync-submodules.sh` | Submodule pointer sync | `bash bin/gac/auto-sync-submodules.sh --apply` |
```

- [ ] **Step 2: Update AGENTS.md**

Add to the governance section:

```markdown
### Governance Health Monitoring

Daily automated health reports track governance metrics over time:

```bash
# Run health monitor
python3 bin/gac/governance_health_monitor.py

# Check for stale rules
python3 bin/gac/anti_corrosion_detector.py

# Check documentation freshness
python3 bin/gac/doc_auto_update.py
```
```

- [ ] **Step 3: Update docs/INDEX-TOOLS.md**

Add entries for new tools.

- [ ] **Step 4: Commit**

```bash
git add bin/README.md AGENTS.md docs/INDEX-TOOLS.md
git commit -m "docs: update documentation for new governance tools"
```

---

## Task 6: CI Integration

**Purpose:** Add governance health monitoring to CI pipeline.

**Files:**
- Modify: `.github/workflows/governance-check.yml`

**Interfaces:**
- Consumes: `bin/gac/governance_health_monitor.py`
- Produces: CI health report artifact

- [ ] **Step 1: Add health check step to governance-check.yml**

```yaml
- name: Governance Health Report
  run: python3 bin/gac/governance_health_monitor.py
  continue-on-error: true
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/governance-check.yml
git commit -m "ci: add governance health monitoring to CI pipeline"
```

---

## Task 7: Final Verification

**Purpose:** Verify all changes work together.

**Files:**
- None (verification only)

**Interfaces:**
- Consumes: All tasks above
- Produces: Final verification report

- [ ] **Step 1: Run all tests**

Run: `pytest tests/test_governance_health_monitor.py tests/test_anti_corrosion_detector.py tests/test_doc_auto_update.py -v`
Expected: All PASS

- [ ] **Step 2: Run governance gate**

Run: `make gac-local-gate`
Expected: All checks PASS

- [ ] **Step 3: Run health monitor**

Run: `python3 bin/gac/governance_health_monitor.py`
Expected: Output shows governance metrics

- [ ] **Step 4: Run anti-corrosion detector**

Run: `python3 bin/gac/anti_corrosion_detector.py`
Expected: Output shows any stale rules

- [ ] **Step 5: Run doc auto-update**

Run: `python3 bin/gac/doc_auto_update.py`
Expected: Output shows any stale documentation

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: governance optimization complete - health monitoring, anti-corrosion, doc update"
```
