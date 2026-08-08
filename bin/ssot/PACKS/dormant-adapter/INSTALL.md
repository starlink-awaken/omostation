# Install: Dormant Adapter Detector

## 1. System Analysis

Before installing, verify the runtime environment:

```bash
# Python 3.13+ required (uses tomllib in 3.11+, dataclass in 3.7+)
python3 --version  # must be >= 3.11

# pyyaml required for the --json output
python3 -c "import yaml; print(yaml.__version__)"
# If missing: uv pip install pyyaml

# bus-foundation itself (the dep we're checking for)
# Should be a workspace dep, not a runtime dep here.
grep bus-foundation /Users/xiamingxing/Workspace/pyproject.toml 2>/dev/null || \
    echo "bus-foundation not in workspace root pyproject (OK — it's a project dep)"
```

## 2. Decision Points

Before proceeding, the operator decides:

- **Where to install?** This Pack ships in the workspace; no separate
  install is needed. The `bin/ssot/bus-usage-report.py` symlink is the
  public entry point.
- **Tolerance for false positives?** If a consumer uses bus-foundation
  only in test code (e.g. integration tests that mock the facade), the
  current heuristic may flag it. Mitigation: add the call site to
  the production path or add a `# noqa: dormant-adapter` comment.

## 3. Backup

Before modifying any state, back up the existing files:

```bash
# No state to back up — this Pack is read-only.
# (However, if you remove the old bin/ssot/bus-usage-report.py
# and the symlink points to a wrong target, restore via:)
git checkout -- bin/ssot/bus-usage-report.py
```

## 4. Execution

Place the Pack into the workspace:

```bash
# Already in place. To verify:
ls -la /Users/xiamingxing/Workspace/bin/ssot/PACKS/dormant-adapter/

# Should show:
#   SKILL.md
#   INSTALL.md (this file)
#   VERIFY.md
#   src/dormant_adapter.py
#   src/Tests/  (when added)
```

The entry point at `bin/ssot/bus-usage-report.py` is a symlink to
`PACKS/dormant-adapter/src/dormant_adapter.py` for backward
compatibility with the existing `gac-local-gate.py` registration.

## 5. Dependency Resolution

```bash
# This Pack's only runtime dep is pyyaml (for --json output).
uv pip install pyyaml

# Optional: register the Pack as a CI gate (already done in
# gac-local-gate.py DEFAULT_POLICY):
#   {"id": "bus-usage-report", "command": ["bin/bus-usage-report.py"]}
```

## Post-Install

```bash
# Smoke test
python3 /Users/xiamingxing/Workspace/bin/ssot/bus-usage-report.py
# Expected: "8 projects, 8 active, 0 dormant" (or similar)

# Full check
python3 /Users/xiamingxing/Workspace/bin/ssot/bus-usage-report.py --json | jq
```
