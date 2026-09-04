---
type: ssot
last-reviewed: 2026-08-26
---

# Domain Facts Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one truthful, read-only Cockpit facts-audit CLI/MCP projection for registered Documents document domains.

**Architecture:** `governance_context.domain_facts_audit()` is the sole `cockpit.domain-facts-audit.v1` producer. It loads L4 identity once and reuses the existing no-follow artifact probe. CLI and MCP only render or serialize that envelope, so they do not independently inspect Documents or alter the legacy script.

**Tech Stack:** Python 3.13, L4 Kernel, FastMCP, Rich, pytest and Ruff.

## Global Constraints

- Never write Documents, Workspace/Runtime state, manifests, bindings, client configuration, schedules or legacy scripts.
- Use `_load_domains()` exactly once per audit call; it stays the sole manifest/registry authority path.
- Audit every domain projected by `_load_domains()`; it is already the authoritative L4 Documents-domain projection. An empty projection is `unavailable` with `no registered domain projects`; a requested unknown ID is also `unavailable`, not an implicit all-domain query.
- Reuse `_artifact_status(root, Path("_entities/facts.md"))`; no second file walker or static-link following.
- A regular facts file may be opened with `O_NOFOLLOW` only to validate readability; audit code never reads its content.
- `modified_on` is a local date from `lstat` metadata and never a freshness or health verdict.
- Exact exit mapping: `ok=0`, `violations=1`, `unavailable=2`.
- Do not claim legacy retirement, bridge parity, scheduled operation or client installation/reload.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/cockpit/adapters/governance_context.py` | L4-backed facts audit and no-follow facts metadata. |
| `src/cockpit/commands/l4bridge.py` | Text/JSON renderer and exit mapping. |
| `src/cockpit/_subcommands.py` | `facts-audit` parser. |
| `src/cockpit/cli.py` | Lazy command dispatch. |
| `src/cockpit/agent_runtime_mcp_server.py` | Read-only MCP tool. |
| `src/cockpit/tests/test_governance_context_adapter.py` | Authority and facts artifact cases. |
| `src/cockpit/tests/test_cli.py` | CLI JSON/exit contract. |
| `src/cockpit/tests/test_agent_runtime_mcp_server.py` | MCP registration/argument forwarding. |
| `docs/superpowers/reports/2026-08-13-domain-facts-audit.md` | Exact verification and live-read result. |

### Task 1: Add the authority-backed facts audit

**Files:**
- Modify: `src/cockpit/adapters/governance_context.py`
- Modify: `src/cockpit/tests/test_governance_context_adapter.py`

**Consumes:** `_load_domains(registry_path, documents_root)` and `_artifact_status(root, relative)`.

**Produces:**

```python
domain_facts_audit(
    domain_id: str = "",
    *,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
) -> dict[str, Any]
```

- [ ] **Step 1: Write RED coverage**

Add these cases:

```python
def test_domain_facts_audit_reports_present_file_and_local_date(tmp_path, monkeypatch):
    registry_path = _write_domain_registry(tmp_path)
    facts = tmp_path / "domains" / "vault" / "_entities" / "facts.md"
    facts.parent.mkdir()
    facts.write_text("# facts\n", encoding="utf-8")
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    result = _adapter().domain_facts_audit("vault")
    assert result["status"] == "ok"
    assert result["summary"] == {"present": 1, "missing": 0, "unreadable": 0, "invalid": 0}
    assert (
        result["domains"][0]["facts"]["modified_on"] == datetime.fromtimestamp(facts.stat().st_mtime).date().isoformat()
    )


def test_domain_facts_audit_reports_missing_and_static_artifacts_as_violations(tmp_path, monkeypatch):
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    assert _adapter().domain_facts_audit("vault")["status"] == "violations"
    facts = tmp_path / "domains" / "vault" / "_entities" / "facts.md"
    facts.parent.mkdir()
    facts.symlink_to(tmp_path / "outside.md")
    result = _adapter().domain_facts_audit("vault")
    assert result["status"] == "violations"
    assert result["domains"][0]["facts"]["status"] == "invalid"


def test_domain_facts_audit_is_unavailable_without_authority_or_for_unknown_domain(tmp_path, monkeypatch):
    registry_path = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry_path))
    assert _adapter().domain_facts_audit("unknown")["status"] == "unavailable"
    registry_path.write_text("manifests: [", encoding="utf-8")
    assert _adapter().domain_facts_audit()["status"] == "unavailable"
```

When `os.mkfifo` is available, replace `facts.md` with a FIFO and assert `invalid`/`violations`; never open a FIFO.

- [ ] **Step 2: Confirm RED**

Run:

```bash
PYTHONPATH="src:/Users/xiamingxing/.local/share/omostation/accepted/projects/l4-kernel/src" \
uv run --no-project --with pytest --with pyyaml --with rich --with fastmcp --with fastapi \
  python -m pytest src/cockpit/tests/test_governance_context_adapter.py -q
```

Expected: the empty-registry and no-content-read regressions fail against the prior behavior.

- [ ] **Step 3: Implement only the shared envelope**

Import `datetime`. Retain the successful regular-file `lstat` result inside `_artifact_status`; when returning `present`, add:

```python
"modified_on": datetime.fromtimestamp(file_stat.st_mtime).date().isoformat(),
```

The existing project-status facts projection may receive this extra informational field; its status computation must not change.

Add an unavailable helper returning exactly:

```python
{
    "schema": "cockpit.domain-facts-audit.v1",
    "status": "unavailable",
    "available": False,
    "requested_domain_id": requested,
    "total": 0,
    "summary": {"present": 0, "missing": 0, "unreadable": 0, "invalid": 0},
    "domains": [],
    "sources": {"domain_registry": str(source)},
    "error": error,
}
```

`domain_facts_audit()` loads domains once; returns the unavailable envelope with `no registered domain projects` for an empty projection; handles a non-empty request before iteration; probes only `Path("_entities/facts.md")`; and creates each item exactly as:

```python
{"id": domain["id"], "name": domain["name"], "facts": facts}
```

Initialize the four summary counts to zero. Return `ok` only if every selected artifact is `present`; otherwise return `violations` with `available=True`. `_artifact_status()` may open a regular file with `O_NOFOLLOW` to validate readability but never reads content. Do not call `_binding_context()`.

- [ ] **Step 4: Confirm GREEN and commit**

Re-run Step 2 and expect PASS. Then:

```bash
git add src/cockpit/adapters/governance_context.py src/cockpit/tests/test_governance_context_adapter.py
git commit -m "feat(cockpit): audit Documents facts"
```

### Task 2: Expose the shared envelope through CLI and MCP

**Files:**
- Modify: `src/cockpit/commands/l4bridge.py`
- Modify: `src/cockpit/_subcommands.py`
- Modify: `src/cockpit/cli.py`
- Modify: `src/cockpit/agent_runtime_mcp_server.py`
- Modify: `src/cockpit/tests/test_cli.py`
- Modify: `src/cockpit/tests/test_agent_runtime_mcp_server.py`

**Consumes:** `domain_facts_audit(domain_id: str = "") -> dict[str, Any]`.

**Produces:** `cockpit facts-audit [DOMAIN_ID] --json` and `domain_facts_audit(domain_id: str = "") -> str`.

- [ ] **Step 1: Write RED coverage**

In CLI tests, patch `l4bridge.governance_context.domain_facts_audit` with:

```python
payload = {
    "schema": "cockpit.domain-facts-audit.v1",
    "status": "ok",
    "available": True,
    "domains": [],
    "summary": {"present": 1, "missing": 0, "unreadable": 0, "invalid": 0},
}
with patch("sys.argv", ["cockpit", "facts-audit", "vault", "--json"]):
    assert main() == 0
assert json.loads(capsys.readouterr().out) == payload
```

Also assert `violations` returns 1 and `unavailable` returns 2. In MCP tests, include `domain_facts_audit` in the registered governance set, patch its adapter and assert it forwards `"vault"` and returns parseable JSON.

- [ ] **Step 2: Confirm RED**

Run:

```bash
PYTHONPATH="src:/Users/xiamingxing/.local/share/omostation/accepted/projects/l4-kernel/src" \
uv run --no-project --with pytest --with pyyaml --with rich --with fastmcp --with fastapi \
  python -m pytest src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py -q
```

Expected: the parser, handler, dispatch and MCP tool are missing.

- [ ] **Step 3: Wire no new owner logic**

In `_subcommands.py` add:

```python
facts_audit_p = sub.add_parser("facts-audit", help="审计 Documents 文档域 facts 文件")
facts_audit_p.add_argument("domain_id", nargs="?", default="", help="可选 document 域 ID")
facts_audit_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
```

Add `cmd_facts_audit(args: Namespace) -> int` in `l4bridge.py`. It invokes the adapter exactly once; it prints `json.dumps(result, ensure_ascii=False, default=str)` when JSON is requested; default text shows only ID/name/facts status/optional date plus summary/error; and it ends with:

```python
return {"ok": 0, "violations": 1, "unavailable": 2}.get(result.get("status"), 2)
```

Add a lazy `_c_facts_audit()` wrapper and a single `"facts-audit": _c_facts_audit` mapping in `cli.py`. Add this tool in `agent_runtime_mcp_server.py`:

```python
@mcp.tool()
def domain_facts_audit(domain_id: str = "") -> str:
    """Audit registered Documents document-domain facts files without reading content."""
    return _json_envelope(governance_context.domain_facts_audit(domain_id))
```

Do not add a web route, Runtime job, action tool, registry entry, client config or Documents edit.

- [ ] **Step 4: Confirm GREEN and commit**

Re-run Step 2 and expect PASS. Then:

```bash
git add src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py
git commit -m "feat(cockpit): expose domain facts audit"
```

### Task 3: Validate and record live read-only evidence

**Files:**
- Create: `docs/superpowers/reports/2026-08-13-domain-facts-audit.md`

- [ ] **Step 1: Run focused contracts**

```bash
PYTHONPATH="src:/Users/xiamingxing/.local/share/omostation/accepted/projects/l4-kernel/src" \
uv run --no-project --with pytest --with pyyaml --with rich --with fastmcp --with fastapi \
  python -m pytest src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py -q
```

Expected: PASS.

- [ ] **Step 2: Run scoped static checks**

```bash
uv run --no-project --with ruff ruff check src/cockpit/adapters/governance_context.py src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py
uv run --no-project --with ruff ruff format --check src/cockpit/adapters/governance_context.py src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py
```

Expected: both commands exit zero.

- [ ] **Step 3: Run and record the live all-domain read**

```bash
L4_DOCUMENTS_ROOT="/Users/xiamingxing/Documents" \
PYTHONPATH="src:/Users/xiamingxing/.local/share/omostation/accepted/projects/l4-kernel/src" \
uv run --no-project --with pyyaml --with rich --with fastmcp --with fastapi \
  python -m cockpit.cli facts-audit --json
```

Create the report with exact commands and observed schema/status/summary. A `violations` result is evidence of an unresolved Documents fact-plane state, never a reason to mutate Documents.

- [ ] **Step 4: Commit evidence**

```bash
git add docs/superpowers/reports/2026-08-13-domain-facts-audit.md
git commit -m "docs(cockpit): record domain facts audit evidence"
```
