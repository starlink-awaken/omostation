---
type: ssot
last-reviewed: 2026-08-26
---

# Domain Project Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only Cockpit CLI/MCP status view for each Documents domain's L4 identity, Workspace binding, and declared gateway files.

**Architecture:** `cockpit.adapters.governance_context` builds the sole `cockpit.domain-project-status.v1` envelope, reusing `_load_domains()` and `_binding_context()`. The CLI renders that envelope and MCP JSON-serializes it; neither owns a registry parser or writes to Documents.

**Tech Stack:** Python 3.13, PyYAML, L4 Kernel, Rich, FastMCP, pytest, Ruff.

## Global Constraints

- No writes to Documents, domain manifests, binding registry, facts, cron, Runtime, or third-party client configuration.
- Reuse `_load_domains()` for L4 identity and `_binding_context()` for Workspace binding; do not duplicate either parser.
- A gateway exists only for a non-empty string `clients.*.instruction_file`; `null` is not a missing gateway.
- Gateway/facts probes reject static symlinks, directories, FIFOs, and path escape without following them. Only regular files receive a bounded readability probe.
- Facts are informational: their status never changes domain or overall status.
- Preserve exact public semantics: `ok=0`, `degraded=1`, `unavailable=2`.
- Do not call this a content audit, KEMS health result, client-install/reload proof, or legacy-runtime cutover.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/cockpit/adapters/governance_context.py` | Authority-backed envelope and safe file probes. |
| `src/cockpit/commands/l4bridge.py` | Text/JSON rendering and exit-code mapping. |
| `src/cockpit/_subcommands.py` | `domain-status` arguments. |
| `src/cockpit/cli.py` | Command dispatch. |
| `src/cockpit/agent_runtime_mcp_server.py` | Read-only MCP registration. |
| `src/cockpit/tests/test_governance_context_adapter.py` | State and static-file-boundary tests. |
| `src/cockpit/tests/test_cli.py` | CLI parser, JSON, and code tests. |
| `src/cockpit/tests/test_agent_runtime_mcp_server.py` | MCP registration and argument forwarding tests. |

### Task 1: Build the authority-backed adapter

**Files:**
- Modify: `src/cockpit/adapters/governance_context.py`
- Modify: `src/cockpit/tests/test_governance_context_adapter.py`

**Interfaces:**
- Consumes: `_load_domains(registry_path, documents_root)` and `_binding_context(domain_id, workspace_root)`.
- Produces: `domain_project_status(domain_id: str = "", *, workspace_root: str | Path | None = None, registry_path: str | Path | None = None, documents_root: str | Path | None = None) -> dict[str, Any]`.

- [ ] **Step 1: Write failing adapter tests**

Add `_write_binding_registry(root, clients)` beside the existing test helpers, writing the current `DocumentsDomainProjects` shape. Add these tests:

```python
def test_domain_project_status_ok_and_facts_are_informational(tmp_path, monkeypatch):
    registry = _write_domain_registry(tmp_path)
    root = tmp_path / "domains" / "vault"
    (root / "CLAUDE.md").write_text("# vault", encoding="utf-8")
    (root / "AGENTS.md").write_text("# vault", encoding="utf-8")
    _write_binding_registry(
        tmp_path,
        {
            "claude": {"instruction_file": "CLAUDE.md"},
            "codex": {"instruction_file": "AGENTS.md"},
            "chatgpt_web": {"instruction_file": None},
        },
    )
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry))
    result = _adapter().domain_project_status("vault", workspace_root=tmp_path)
    assert result["status"] == "ok"
    assert result["summary"] == {"ok": 1, "degraded": 0, "unavailable": 0}
    assert [row["status"] for row in result["domains"][0]["gateways"]] == ["present", "present"]
    assert result["domains"][0]["facts"]["status"] == "missing"


def test_domain_project_status_degraded_for_missing_binding_or_gateway(tmp_path, monkeypatch):
    registry = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry))
    assert _adapter().domain_project_status("vault", workspace_root=tmp_path)["status"] == "degraded"
    _write_binding_registry(tmp_path, {"claude": {"instruction_file": "CLAUDE.md"}})
    result = _adapter().domain_project_status("vault", workspace_root=tmp_path)
    assert result["status"] == "degraded"
    assert result["domains"][0]["gateways"][0]["status"] == "missing"


def test_domain_project_status_rejects_symlink_and_fifo_gateway(tmp_path, monkeypatch):
    # Prepare valid registry/binding, then make CLAUDE.md a static symlink.
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (tmp_path / "domains" / "vault" / "CLAUDE.md").symlink_to(outside)
    assert (
        _adapter().domain_project_status("vault", workspace_root=tmp_path)["domains"][0]["gateways"][0]["status"]
        == "invalid"
    )
    # On platforms with os.mkfifo(), replace the path with a FIFO and retain invalid/degraded.


def test_domain_project_status_unavailable_for_unknown_domain_or_bad_registry(tmp_path, monkeypatch):
    registry = _write_domain_registry(tmp_path)
    monkeypatch.setenv("L4_DOMAIN_REGISTRY", str(registry))
    assert _adapter().domain_project_status("unknown", workspace_root=tmp_path)["status"] == "unavailable"
    registry.write_text("manifests: [", encoding="utf-8")
    assert _adapter().domain_project_status("vault", workspace_root=tmp_path)["status"] == "unavailable"
```

- [ ] **Step 2: Prove the tests are red**

Run: `uv run pytest src/cockpit/tests/test_governance_context_adapter.py -q`

Expected: FAIL because `domain_project_status` does not exist.

- [ ] **Step 3: Implement the minimal adapter**

Add `os` and `stat` imports. Create `_artifact_status(root: Path, relative: Path) -> dict[str, str]` with this exact decision order:

```python
if relative.is_absolute() or ".." in relative.parts:
    return {"status": "invalid", "path": str(root / relative)}
path = root.joinpath(*relative.parts)
try:
    for candidate in (root, *[root.joinpath(*relative.parts[:index]) for index in range(1, len(relative.parts))]):
        if not stat.S_ISDIR(os.lstat(candidate).st_mode):
            return {"status": "invalid", "path": str(path)}
    file_stat = os.lstat(path)
except FileNotFoundError:
    return {"status": "missing", "path": str(path)}
except OSError:
    return {"status": "unreadable", "path": str(path)}
if not stat.S_ISREG(file_stat.st_mode):
    return {"status": "invalid", "path": str(path)}
```

Open only a regular file with `os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))`, read at most one byte, close it in `finally`, and return `present`; any `OSError` from this probe is `unreadable`.

Implement `domain_project_status()` by loading domains once, selecting all or one requested ID, retrieving every selected manifest from the same registry, and calling `_binding_context()` exactly once per selected domain. Build `identity` with `id`, `name`, `path`, `exists`, `lifecycle`, and `authority_policy`. For every `clients` mapping whose `instruction_file` is a non-empty string, call `_artifact_status`; malformed client declarations become an `invalid` gateway. Call the same probe for `_entities/facts.md` but do not include its status in domain status. Return exactly:

```python
{
    "schema": "cockpit.domain-project-status.v1",
    "status": overall_status,
    "available": overall_status != "unavailable",
    "requested_domain_id": requested,
    "total": len(items),
    "summary": {"ok": ok_count, "degraded": degraded_count, "unavailable": unavailable_count},
    "domains": items,
    "sources": {"domain_registry": str(source), "binding_registry": str(binding_path)},
}
```

An L4 loader failure, unknown requested ID, no selected item, or absent expected manifest returns a zero-item `unavailable` envelope with `error`. A valid identity with missing root/binding/gateway stays `degraded` and `available=True`.

- [ ] **Step 4: Prove the adapter is green**

Run: `uv run pytest src/cockpit/tests/test_governance_context_adapter.py -q`

Expected: PASS; the FIFO case completes without opening its writer end.

- [ ] **Step 5: Commit the adapter unit**

```bash
git add src/cockpit/adapters/governance_context.py src/cockpit/tests/test_governance_context_adapter.py
git commit -m "feat(cockpit): project Documents domain status"
```

### Task 2: Expose CLI and MCP from one envelope

**Files:**
- Modify: `src/cockpit/commands/l4bridge.py`
- Modify: `src/cockpit/_subcommands.py`
- Modify: `src/cockpit/cli.py`
- Modify: `src/cockpit/agent_runtime_mcp_server.py`
- Modify: `src/cockpit/tests/test_cli.py`
- Modify: `src/cockpit/tests/test_agent_runtime_mcp_server.py`

**Interfaces:**
- Consumes: `governance_context.domain_project_status(domain_id: str = "") -> dict[str, Any]`.
- Produces: `cockpit domain-status [DOMAIN_ID] --json`, plus `domain_project_status(domain_id: str = "") -> str` over MCP.

- [ ] **Step 1: Write failing CLI/MCP tests**

Add this MCP test and assert its tool registration:

```python
def test_domain_project_status_is_registered_and_forwards_argument(monkeypatch):
    payload = {"schema": "cockpit.domain-project-status.v1", "status": "ok", "available": True}
    seen = []
    monkeypatch.setattr(
        agent_runtime_mcp_server.governance_context,
        "domain_project_status",
        lambda domain_id="": seen.append(domain_id) or payload,
    )
    tools = asyncio.run(agent_runtime_mcp_server.mcp.list_tools())
    assert "domain_project_status" in {tool.name for tool in tools}
    assert json.loads(agent_runtime_mcp_server.domain_project_status("vault")) == payload
    assert seen == ["vault"]
```

In CLI tests patch `cockpit.commands.l4bridge.governance_context.domain_project_status`, invoke `main()` with `sys.argv`, parse `capsys.readouterr().out` for `--json`, and assert `ok` gives `0`, `degraded` gives `1`, and `unavailable` gives `2` for both all-domain and selected-domain argv forms.

- [ ] **Step 2: Prove the surfaces are red**

Run: `uv run pytest src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py -q`

Expected: FAIL because the parser, handler and MCP tool do not exist.

- [ ] **Step 3: Wire only the shared surfaces**

In `_subcommands.py`, immediately after `domains`, add:

```python
domain_status_p = sub.add_parser("domain-status", help="显示 Documents 域项目绑定与引导状态")
domain_status_p.add_argument("domain_id", nargs="?", default="", help="可选 L4 域 ID")
domain_status_p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")
```

In `l4bridge.py`, add `cmd_domain_status(args: Namespace) -> int`: call the adapter exactly once; for `args.json`, print `json.dumps(result, ensure_ascii=False, default=str)`; otherwise render only the envelope's summary, item ID/status, gateway statuses and facts status. Finish with:

```python
return {"ok": 0, "degraded": 1, "unavailable": 2}.get(result.get("status"), 2)
```

In `cli.py`, add a lazy `_c_domain_status()` wrapper and the sole `"domain-status": _c_domain_status` dispatch entry. In `agent_runtime_mcp_server.py`, add:

```python
@mcp.tool()
def domain_project_status(domain_id: str = "") -> str:
    """Read one or all Documents domain project bindings and gateway files."""
    return _json_envelope(governance_context.domain_project_status(domain_id))
```

Do not add a web route, Runtime call, action tool, or a second YAML/manifest parser.

- [ ] **Step 4: Prove the surfaces are green**

Run: `uv run pytest src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py -q`

Expected: PASS; JSON is parseable and `unavailable` is exit code `2`, never a false success.

- [ ] **Step 5: Commit the surface unit**

```bash
git add src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py
git commit -m "feat(cockpit): expose domain project status"
```

### Task 3: Validate the feature package and live readonly projection

**Files:**
- Modify: no source files expected.

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces: review-ready test, lint and live-read evidence only.

- [ ] **Step 1: Run focused contracts**

Run: `uv run pytest src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py -q`

Expected: PASS.

- [ ] **Step 2: Run static checks**

Run: `uv run ruff check src/cockpit/adapters/governance_context.py src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py`

Run: `uv run ruff format --check src/cockpit/adapters/governance_context.py src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py`

Expected: both commands exit `0`.

- [ ] **Step 3: Run a live read-only all-domain smoke**

Run: `L4_DOCUMENTS_ROOT="/Users/xiamingxing/Documents" WORKSPACE_ROOT="/Users/xiamingxing/Workspace" uv run cockpit domain-status --json`

Expected: parseable `cockpit.domain-project-status.v1` output. Record the actual status/summary; a degraded status is evidence, not a reason to mutate source data.

- [ ] **Step 4: Inspect the review diff**

Run: `git diff origin/main...HEAD --check && git diff --stat origin/main...HEAD && git status --short`

Expected: no whitespace errors and no changed Documents paths. Cockpit code, focused tests, spec and plan only.
