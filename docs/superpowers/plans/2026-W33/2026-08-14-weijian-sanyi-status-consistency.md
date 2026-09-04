---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
title: 卫健委 CR08 三医态势一致性审计 Implementation Plan
type: doc
---
# 卫健委 CR08 三医态势一致性审计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个由 Workspace Runtime 执行、Cockpit 与受控客户 MCP 可发现的卫健委 CR08 只读三医态势一致性审计。

**Architecture:** Runtime 只读取仪表盘和一个结构化 Facts YAML，比较严格日期后写入受控 state receipt。Cockpit 只验证并投影 receipt，根 binding 同时声明 job、工具和客户 read profile，Documents 从始至终不被写入。

**Tech Stack:** Python 3.13、PyYAML、pytest、Ruff、Runtime Documents Plane、Cockpit FastMCP、GitHub PR/CI。

## Global Constraints

- 只读取 `@工作文档/卫健委/_control/三医态势仪表盘.md` 与 `@工作文档/卫健委/_entities/facts/01-progress.yaml`；禁止 mtime、关键词或全域扫描。
- 范围实体只允许且必须按顺序为 `proj-syld`、`proj-jingbao`、`proj-emr-quality`；根 binding 是其声明 SSOT，Runtime/Cockpit 严格验证。
- Documents 永远只读，job `writes` 必须是 `[]`；唯一写入位置是 `OMOSTATION_RUNTIME_STATE_ROOT` 中的 receipt。
- owner JSON、receipt、CLI 和 MCP 不得暴露事实正文、`fid`、实体外原始字段、文件名、Documents 路径或凭据。
- `ok=0`、`attention=1`、`unavailable=2`；隔离、超时或 receipt I/O 失败必须非零且不可假绿。
- job 固定 `manual`；不改仪表盘、Facts、`controller.py`、域内 Runtime/KEMS，也不宣称任一客户端已经重载或安装。
- Runtime、Cockpit、根绑定各自独立 PR/审查/CI；根 gitlink 只可移动到已合入对应子仓 `origin/main` 的 commit。

---

## File Map

| 文件 | 职责 |
| --- | --- |
| `projects/runtime/src/runtime/documents_plane/sanyi_status.py` | 两个受控输入的解析、聚合状态和无身份 owner JSON。 |
| `projects/runtime/src/runtime/documents_plane/cli.py` | 精确 binding→`JobSpec`→owner command 注册。 |
| `projects/runtime/src/runtime/documents_plane/jobs.py` | 允许并验证 `sanyi-status-consistency-v1` evidence projection。 |
| `projects/runtime/tests/test_documents_plane_sanyi_status.py` | owner 的日期、结构、非法输入和不泄露契约。 |
| `projects/runtime/tests/test_documents_plane_jobs.py` | job/receipt/退出码/Documents 零写集成测试。 |
| `projects/cockpit/src/cockpit/adapters/governance_context.py` | pathless receipt 验证与 `domain_sanyi_status_consistency_status`。 |
| `projects/cockpit/src/cockpit/commands/l4bridge.py` | `cockpit sanyi-status` 输出和状态码。 |
| `projects/cockpit/src/cockpit/_subcommands.py`、`src/cockpit/cli.py` | CLI parser 和 dispatch。 |
| `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py` | 主 Cockpit MCP read tool。 |
| `projects/cockpit/src/cockpit/documents_read_mcp_server.py` | Secure MCP Tunnel read tool 集合。 |
| `projects/cockpit/src/cockpit/tests/test_governance_context_adapter.py` | binding/receipt/pathless 投影测试。 |
| `projects/cockpit/src/cockpit/tests/test_cli.py`、`test_agent_runtime_mcp_server.py`、`test_documents_read_mcp_server.py` | CLI、主 MCP、Secure MCP 测试。 |
| `.omo/_truth/registry/documents-domain-projects.yaml` | job/tool/profile 唯一声明。 |
| `bin/gac/documents_domain_jobs.py` | 根 binding 的 fail-closed schema validator。 |
| `bin/gac/documents-chatgpt-tunnel.py` | Secure MCP profile allowlist validator。 |
| `tests/test_documents_domain_project_check.py`、`tests/test_documents_chatgpt_tunnel.py` | 根 binding/Tunnel 的回归。 |
| `docs/reports/2026-08-14-weijian-sanyi-status-audit-retrospective.md` | 安装态证据与下一阶段决策。 |

### Task 1: Runtime owner、binding loader 与安全 receipt

**Files:**

- Create: `projects/runtime/src/runtime/documents_plane/sanyi_status.py`
- Modify: `projects/runtime/src/runtime/documents_plane/cli.py`
- Modify: `projects/runtime/src/runtime/documents_plane/jobs.py`
- Create: `projects/runtime/tests/test_documents_plane_sanyi_status.py`
- Modify: `projects/runtime/tests/test_documents_plane_jobs.py`

**Interfaces:**

- Consumes: `documents-weijian-sanyi-status-audit` binding，action `audit_sanyi_status_consistency`，两个 exact reads、`scope_entity_ids`、`writes: []`、`manual`、schema `runtime.documents-sanyi-status-consistency.evidence.v1`。
- Produces: `runtime.documents-sanyi-status-consistency.v1` owner JSON with exactly `schema`, `status`, `checked_on`, `dashboard_last_reviewed`, `latest_verified_at`, `relevant_fact_count`, `error`; evidence projection `sanyi-status-consistency-v1`。

- [ ] **Step 1: 写 owner 的 RED 测试。**

```python
def test_inspect_sanyi_status_reports_aggregate_attention_only(tmp_path: Path) -> None:
    domain = _write_domain(
        tmp_path,
        dashboard_last_reviewed="2026-08-05",
        facts=[("proj-jingbao", "2026-08-12"), ("proj-syld", "2026-08-13")],
    )
    result = inspect_sanyi_status(domain, today=date(2026, 8, 14))
    assert result.as_dict() == {
        "schema": "runtime.documents-sanyi-status-consistency.v1",
        "status": "attention", "checked_on": "2026-08-14",
        "dashboard_last_reviewed": "2026-08-05", "latest_verified_at": "2026-08-13",
        "relevant_fact_count": 2, "error": None,
    }
    assert "fact-private" not in json.dumps(result.as_dict(), ensure_ascii=False)


@pytest.mark.parametrize("mutation", ["dashboard_symlink", "facts_fifo", "invalid_yaml", "invalid_verified_at", "empty_scope"])
def test_inspect_sanyi_status_fails_closed_without_identity(tmp_path: Path, mutation: str) -> None:
    result = inspect_sanyi_status(_mutate_domain(tmp_path, mutation), today=date(2026, 8, 14))
    assert result.status == "unavailable"
    assert result.latest_verified_at is None and result.relevant_fact_count == 0
```

- [ ] **Step 2: 运行 RED 测试。**

Run from `projects/runtime`:

```bash
uv run --no-sync python -m pytest tests/test_documents_plane_sanyi_status.py -q
```

Expected: FAIL during collection because `runtime.documents_plane.sanyi_status` does not exist.

- [ ] **Step 3: 实现最小、受限 owner。**

```python
_SCHEMA = "runtime.documents-sanyi-status-consistency.v1"
_SCOPE_ENTITY_IDS = frozenset({"proj-syld", "proj-jingbao", "proj-emr-quality"})
_EXIT_CODES = {"ok": 0, "attention": 1, "unavailable": 2}


@dataclass(frozen=True)
class SanyiStatusConsistency:
    status: str
    checked_on: str
    dashboard_last_reviewed: str | None
    latest_verified_at: str | None
    relevant_fact_count: int
    error: str | None


def inspect_sanyi_status(domain_root: Path, *, today: date | None = None) -> SanyiStatusConsistency:
    """Compare declared CR08 facts with dashboard frontmatter only."""
    checked_on = today or datetime.now(UTC).date()
    dashboard_date = _dashboard_last_reviewed(domain_root / "_control" / "三医态势仪表盘.md")
    verified_dates = _relevant_verified_dates(domain_root / "_entities" / "facts" / "01-progress.yaml")
    latest = max(verified_dates)
    return SanyiStatusConsistency(
        status="attention" if latest > dashboard_date else "ok",
        checked_on=checked_on.isoformat(), dashboard_last_reviewed=dashboard_date.isoformat(),
        latest_verified_at=latest.isoformat(), relevant_fact_count=len(verified_dates), error=None,
    )
```

`_dashboard_last_reviewed` must accept only a regular, non-symlink Markdown file with exactly one strict ISO `last-reviewed` inside initial YAML frontmatter. `_relevant_verified_dates` must accept only a regular, non-symlink YAML file with a `facts` list; every fact whose `entity_ids` intersects `_SCOPE_ENTITY_IDS` needs strict ISO `verified_at`; zero matching facts is unavailable. Catch each input/parse issue in `main()` and emit a stable category with all aggregate data `None`/`0`; never interpolate a path, `fid`, statement or YAML error. `main()` accepts only `inspect --domain-relative @工作文档/卫健委`, prints sorted JSON, and returns `_EXIT_CODES[result.status]`.

- [ ] **Step 4: 加载 binding、注册命令并验证 owner payload。**

```python
# cli.py
_SANYI_ACTION = "audit_sanyi_status_consistency"
_SANYI_SCHEMA = "runtime.documents-sanyi-status-consistency.evidence.v1"
_SANYI_READS = (
    "@工作文档/卫健委/_control/三医态势仪表盘.md",
    "@工作文档/卫健委/_entities/facts/01-progress.yaml",
)
_SANYI_SCOPE = ("proj-syld", "proj-jingbao", "proj-emr-quality")
_SANYI_EVIDENCE = "control/evidence/documents-weijian-sanyi-status-audit/documents-weijian-sanyi-status-audit.json"
_SANYI_COMMAND = (
    sys.executable, "-m", "runtime.documents_plane.sanyi_status",
    "inspect", "--domain-relative", "@工作文档/卫健委",
)
_SANYI_PROJECTION = "sanyi-status-consistency-v1"
```

Implement `_sanyi_status_job_spec(environ)` beside the existing model-freshness loader. It must load exactly one binding job whose complete mapping equals the constants above plus `id`, `domain_id`, `owner`, `schedule`, `timeout_seconds`, `reads`, `scope_entity_ids`, `writes`, `evidence_relative_path`, `evidence_schema`, and `fail_closed`; unknown, missing, duplicate, reordered-scope, or changed values raise the existing binding-contract error before any owner process starts. Build `JobSpec` from that exact declaration and register `_SANYI_COMMAND` only if the declaration validates.

Extend `jobs.py::_EVIDENCE_PROJECTIONS` with `_SANYI_PROJECTION`, then implement the corresponding receipt projector. It accepts exactly these seven owner fields: `schema`, `status`, `checked_on`, `dashboard_last_reviewed`, `latest_verified_at`, `relevant_fact_count`, `error`. `ok` and `attention` require strict ISO dates, `relevant_fact_count >= 1`, `error is None`, and their respective `latest_verified_at <= dashboard_last_reviewed` / `>` relationship. `unavailable` requires an allowed stable error, no aggregate dates, and count `0`. Any extra, missing, malformed, or contradictory field is an evidence error and the receipt does not become a successful projection.

- [ ] **Step 5: 写并运行 owner→receipt GREEN 测试。**

```python
def test_sanyi_status_job_persists_bounded_attention_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    environ = _sanyi_environ(tmp_path, dashboard="2026-08-05", latest="2026-08-13")
    assert main(["documents", "run", "documents-weijian-sanyi-status-audit", "--json"], environ=environ) == 1
    receipt = json.loads(Path(json.loads(capsys.readouterr().out)["evidence_path"]).read_text())
    assert set(receipt["owner_evidence"]) == {
        "schema", "status", "checked_on", "dashboard_last_reviewed",
        "latest_verified_at", "relevant_fact_count", "error",
    }
    assert receipt["owner_evidence"]["status"] == "attention"
    assert "statement" not in json.dumps(receipt, ensure_ascii=False)

def test_sanyi_status_dry_run_and_real_run_never_write_documents(tmp_path: Path) -> None:
    documents_root = _write_sanyi_documents(tmp_path)
    environ = _sanyi_environ(tmp_path, documents_root=documents_root)
    before = _documents_digest(documents_root)
    assert main(["documents", "run", "documents-weijian-sanyi-status-audit", "--dry-run", "--json"], environ=environ) == 0
    assert main(["documents", "run", "documents-weijian-sanyi-status-audit", "--json"], environ=environ) in {0, 1, 2}
    assert _documents_digest(documents_root) == before
```

Run:

```bash
uv run --no-sync python -m pytest tests/test_documents_plane_sanyi_status.py tests/test_documents_plane_jobs.py -q
uv run --no-sync ruff check src/runtime/documents_plane tests/test_documents_plane_sanyi_status.py tests/test_documents_plane_jobs.py
uv run --no-sync ruff format --check src/runtime/documents_plane tests/test_documents_plane_sanyi_status.py tests/test_documents_plane_jobs.py
```

Expected: PASS; `attention` is exit 1 with a valid receipt, all Documents digests match.

- [ ] **Step 6: 独立提交、PR、审查、CI、合并 Runtime。**

```bash
git add src/runtime/documents_plane/sanyi_status.py src/runtime/documents_plane/cli.py src/runtime/documents_plane/jobs.py tests/test_documents_plane_sanyi_status.py tests/test_documents_plane_jobs.py
git commit -m "feat(runtime): add Weijian sanyi status audit"
git push -u origin work/documents-weijian-sanyi-status-runtime
gh pr create --base main --title "feat(runtime): add Weijian sanyi status audit"
```

Do not change root pointers, lockfile, or Documents in this PR. Merge only after focused/full Runtime CI and reviewer approval.

### Task 2: Cockpit projection、CLI 与两种 MCP

**Files:**

- Modify: `projects/cockpit/src/cockpit/adapters/governance_context.py`
- Modify: `projects/cockpit/src/cockpit/commands/l4bridge.py`
- Modify: `projects/cockpit/src/cockpit/_subcommands.py`
- Modify: `projects/cockpit/src/cockpit/cli.py`
- Modify: `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py`
- Modify: `projects/cockpit/src/cockpit/documents_read_mcp_server.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_governance_context_adapter.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_cli.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_agent_runtime_mcp_server.py`
- Modify: `projects/cockpit/src/cockpit/tests/test_documents_read_mcp_server.py`

**Interfaces:**

- Consumes: Task 1 receipt and the exact root binding declaration.
- Produces: schema `cockpit.domain-sanyi-status-consistency.v1`, adapter/MCP `domain_sanyi_status_consistency_status(domain_id)`, and `cockpit sanyi-status <domain-id> [--json]`.

- [ ] **Step 1: 写 Cockpit RED 测试。**

```python
def test_domain_sanyi_status_projects_only_valid_runtime_receipt(tmp_path: Path) -> None:
    state_root = _write_runtime_sanyi_receipt(tmp_path, status="attention", dashboard="2026-08-05", latest="2026-08-13", count=3)
    result = gc.domain_sanyi_status_consistency_status("work-weijian", workspace_root=tmp_path, runtime_state_root=state_root)
    assert result["schema"] == "cockpit.domain-sanyi-status-consistency.v1"
    assert result["status"] == "attention"
    assert "/Users/" not in json.dumps(result, ensure_ascii=False)


def test_documents_read_server_matches_declared_profile_tools() -> None:
    names = {tool.name for tool in asyncio.run(_server().mcp.list_tools())}
    assert {"domain_model_freshness_status", "domain_sanyi_status_consistency_status"} <= names


def test_sanyi_status_cli_maps_attention_to_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gc, "domain_sanyi_status_consistency_status", lambda _: _attention_envelope())
    with patch("sys.argv", ["cockpit", "sanyi-status", "work-weijian", "--json"]):
        assert cockpit.cli.main() == 1
```

- [ ] **Step 2: 运行 Cockpit RED 测试。**

```bash
uv run --no-sync python -m pytest src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py src/cockpit/tests/test_documents_read_mcp_server.py -q
```

Expected: FAIL for absent adapter/parser/MCP tools.

- [ ] **Step 3: 增加 pathless receipt projection 与 CLI。**

```python
_SANYI_EVIDENCE_SCHEMA = "runtime.documents-sanyi-status-consistency.evidence.v1"
_SANYI_EVIDENCE_AUTHORITY = "runtime-sanyi-status-consistency-evidence"
_SANYI_ALLOWED_STATUSES = frozenset({"ok", "attention", "unavailable"})
_SANYI_SOURCES = (
    "l4-domain-registry", "workspace-documents-domain-projects",
    _SANYI_EVIDENCE_AUTHORITY,
)

def cmd_sanyi_status(args: Namespace) -> int:
    result = governance_context.domain_sanyi_status_consistency_status(args.domain_id)
    return {"ok": 0, "attention": 1, "unavailable": 2}.get(result["status"], 2)
```

Add `sanyi_status_unavailable_envelope(domain_id, error_category, include_runtime_evidence=False)` and `domain_sanyi_status_consistency_status(domain_id, *, workspace_root=None, registry_path=None, documents_root=None, runtime_state_root=None)` beside the model-freshness equivalents. The adapter must demand one `audit_sanyi_status_consistency` job with exact owner/schema/path/read/scope/write contract and use `_read_bounded_runtime_receipt`. Validate receipt identity, `timed_out is False`, `evidence_error is None`, exact owner fields, strict ISO dates, non-negative count, and status/date agreement. All registry, binding, state-root, receipt, JSON, symlink and size failures return a pathless envelope whose `sources` contains only the names in `_SANYI_SOURCES`; omit the Runtime evidence authority when it was never reached.

- [ ] **Step 4: 接通 parser、主 MCP 和 Secure MCP。**

```python
# _subcommands.py
p = sub.add_parser("sanyi-status", help="读取 Runtime 三医态势一致性审计回执")
p.add_argument("domain_id", help="L4 document 域 ID")
p.add_argument("--json", action="store_true", help="输出稳定 JSON envelope")

# agent_runtime_mcp_server.py and documents_read_mcp_server.py
@mcp.tool()
def domain_sanyi_status_consistency_status(domain_id: str) -> str:
    return _json_envelope(governance_context.domain_sanyi_status_consistency_status(domain_id))
```

Add the already profile-declared `domain_model_freshness_status` to `documents_read_mcp_server.py` too. The Secure MCP tool set must exactly equal the root `content-domain` allowlist after CR08 is added; no tool is advertised only in YAML.

- [ ] **Step 5: 运行 Cockpit GREEN 与静态检查。**

```bash
uv run --no-sync python -m pytest src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py src/cockpit/tests/test_documents_read_mcp_server.py -q
uv run --no-sync ruff check src/cockpit/adapters/governance_context.py src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/documents_read_mcp_server.py src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py src/cockpit/tests/test_documents_read_mcp_server.py
uv run --no-sync ruff format --check src/cockpit/adapters/governance_context.py src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/documents_read_mcp_server.py src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py src/cockpit/tests/test_documents_read_mcp_server.py
```

Expected: PASS; `attention` exits 1; adapter/CLI/MCP envelopes do not leak Documents paths or fact content.

- [ ] **Step 6: 独立提交、PR、审查、CI、合并 Cockpit。**

```bash
git add src/cockpit/adapters/governance_context.py src/cockpit/commands/l4bridge.py src/cockpit/_subcommands.py src/cockpit/cli.py src/cockpit/agent_runtime_mcp_server.py src/cockpit/documents_read_mcp_server.py src/cockpit/tests/test_governance_context_adapter.py src/cockpit/tests/test_cli.py src/cockpit/tests/test_agent_runtime_mcp_server.py src/cockpit/tests/test_documents_read_mcp_server.py
git commit -m "feat(cockpit): expose Weijian sanyi status audit"
git push -u origin work/documents-weijian-sanyi-status-cockpit
gh pr create --base main --title "feat(cockpit): expose Weijian sanyi status audit"
```

Merge only after its CI/review is green. The root gitlink remains untouched here.

### Task 3: Root binding、Secure MCP profile 与 gitlink

**Files:**

- Modify: `.omo/_truth/registry/documents-domain-projects.yaml`
- Modify: `bin/gac/documents_domain_jobs.py`
- Modify: `bin/gac/documents-chatgpt-tunnel.py`
- Modify: `tests/test_documents_domain_project_check.py`
- Modify: `tests/test_documents_chatgpt_tunnel.py`
- Modify: `projects/runtime` and `projects/cockpit` gitlinks after both PRs merge.

**Interfaces:**

- Consumes: merged Runtime/Cockpit `origin/main` commits and Tasks 1–2 public contracts.
- Produces: job/tool/profile SSOT that every declared Cowork client receives from the same Cockpit binding.

- [ ] **Step 1: 写根 binding RED 测试。**

```python
def test_workspace_binding_declares_weijian_sanyi_status_owner() -> None:
    assert _runtime_job("documents-weijian-sanyi-status-audit") == {
        "id": "documents-weijian-sanyi-status-audit", "domain_id": "work-weijian",
        "owner": "runtime-control", "action": "audit_sanyi_status_consistency",
        "schedule": "manual", "timeout_seconds": 30,
        "reads": ["@工作文档/卫健委/_control/三医态势仪表盘.md", "@工作文档/卫健委/_entities/facts/01-progress.yaml"],
        "scope_entity_ids": ["proj-syld", "proj-jingbao", "proj-emr-quality"], "writes": [],
        "evidence_relative_path": "control/evidence/documents-weijian-sanyi-status-audit/documents-weijian-sanyi-status-audit.json",
        "evidence_schema": "runtime.documents-sanyi-status-consistency.evidence.v1", "fail_closed": True,
    }


def test_sanyi_binding_rejects_scope_drift(tmp_path: Path) -> None:
    raw = _binding_with(_weijian_sanyi_job(scope_entity_ids=["proj-syld"]))
    assert _run_binding(raw, tmp_path).returncode == 1
```

- [ ] **Step 2: 运行 root RED 测试。**

```bash
uv run --with pytest --with pyyaml python -m pytest tests/test_documents_domain_project_check.py tests/test_documents_chatgpt_tunnel.py -q
```

Expected: FAIL because CR08 job and read tool are absent.

- [ ] **Step 3: 添加精确 binding 和校验器。**

```yaml
- id: documents-weijian-sanyi-status-audit
  domain_id: work-weijian
  owner: runtime-control
  action: audit_sanyi_status_consistency
  schedule: manual
  timeout_seconds: 30
  reads: ["@工作文档/卫健委/_control/三医态势仪表盘.md", "@工作文档/卫健委/_entities/facts/01-progress.yaml"]
  scope_entity_ids: [proj-syld, proj-jingbao, proj-emr-quality]
  writes: []
  evidence_relative_path: control/evidence/documents-weijian-sanyi-status-audit/documents-weijian-sanyi-status-audit.json
  evidence_schema: runtime.documents-sanyi-status-consistency.evidence.v1
  fail_closed: true
```

Append `domain_sanyi_status_consistency_status` once to `workspace_mcp.read_tools`, `profiles.content-domain.allowed_workspace_tools`, and `documents-chatgpt-tunnel.py::EXPECTED_TOOLS`. Add `_validate_sanyi_status_job()` in `documents_domain_jobs.py` to require this exact field set and values; change neither client configuration generator nor client installation state.

- [ ] **Step 4: 移动仅已合并的子模块指针。**

```bash
git -C projects/runtime fetch origin main
git -C projects/cockpit fetch origin main
git -C projects/runtime merge-base --is-ancestor <runtime-merged-sha> origin/main
git -C projects/cockpit merge-base --is-ancestor <cockpit-merged-sha> origin/main
bash bin/gac/gac-worktree.sh bump-pointer documents-weijian-sanyi-status-root projects/runtime
bash bin/gac/gac-worktree.sh bump-pointer documents-weijian-sanyi-status-root projects/cockpit
```

Expected: both ancestry checks exit 0. If either does not, stop; do not point root at agent branches.

- [ ] **Step 5: 运行 root GREEN、创建并合并 root PR。**

```bash
uv run --with pytest --with pyyaml python -m pytest tests/test_documents_domain_project_check.py tests/test_documents_chatgpt_tunnel.py -q
uv run --with pyyaml python bin/gac/documents-domain-project-check.py --domain-registry "$L4_DOMAIN_REGISTRY" --project-registry .omo/_truth/registry/documents-domain-projects.yaml --gateway-domain work-weijian --json
uv run --with pyyaml python bin/gac/documents-chatgpt-tunnel.py render --project-registry .omo/_truth/registry/documents-domain-projects.yaml --domain-registry "$L4_DOMAIN_REGISTRY"
git diff --check
```

Expected: PASS and Tunnel render lists `domain_sanyi_status_consistency_status` once. Commit only five root contract/test files plus two verified gitlinks in change-lane-compliant commits; PR, wait for CI/review, then merge.

### Task 4: Clean-main installed smoke and retrospective

**Files:**

- Create: `docs/reports/2026-08-14-weijian-sanyi-status-audit-retrospective.md`
- Modify: `docs/SYSTEM-INDEX.md`

**Interfaces:**

- Consumes: clean root main with all three merged layers.
- Produces: evidence of real Runtime/Cockpit/MCP behavior and Documents non-mutation, without asserting client UI reload.

- [ ] **Step 1: 用真实输入运行 owner 并证明 Documents 未写。**

```bash
documents_root="/Users/xiamingxing/Documents"
state_root="$(mktemp -d /tmp/documents-weijian-sanyi-status.XXXXXX)"
before="$(mktemp /tmp/documents-before.XXXXXX)"; after="$(mktemp /tmp/documents-after.XXXXXX)"
find "$documents_root" -type f -exec shasum -a 256 {} + | LC_ALL=C sort > "$before"
DOCUMENTS_CONTENT_ROOT="$documents_root" OMOSTATION_RUNTIME_STATE_ROOT="$state_root" runtime documents run documents-weijian-sanyi-status-audit --json
find "$documents_root" -type f -exec shasum -a 256 {} + | LC_ALL=C sort > "$after"
cmp -s "$before" "$after"
```

Expected: current input may correctly return `attention`/exit 1; `cmp` exits 0. Record only status, aggregate dates/count and receipt schema.

- [ ] **Step 2: Smoke Cockpit CLI and both MCP servers.**

```bash
WORKSPACE_ROOT="$PWD" OMOSTATION_RUNTIME_STATE_ROOT="$state_root" cockpit sanyi-status work-weijian --json
WORKSPACE_ROOT="$PWD" OMOSTATION_RUNTIME_STATE_ROOT="$state_root" cockpit-documents-mcp
WORKSPACE_ROOT="$PWD" OMOSTATION_RUNTIME_STATE_ROOT="$state_root" cockpit-mcp
```

Use the existing stdio harness to send `initialize`, `tools/list`, `domain_context(work-weijian)`, and `domain_sanyi_status_consistency_status(work-weijian)` to both servers. Assert discoverability, agreement with Runtime status, and no absolute Documents path/`fid`/statement/source content in any envelope.

- [ ] **Step 3: 写只追加的复盘。**

```markdown
## Installed CR08 audit result

- Merged-main Runtime, Cockpit CLI, agent Runtime MCP and Secure Documents MCP were exercised.
- Evidence was written only under the supplied Runtime state root; Documents before/after digests matched.
- The observed result is recorded as returned, without altering Facts or the dashboard to obtain green.

## Limits and next decision

- This owner remains manual and read-only.
- Profile declarations prove discoverability, not each client reload/UI installation state.
- Legacy `controller.py` reclassification and automatic Documents edits require a separate approved design.
```

Add one `SYSTEM-INDEX.md` pointer. Do not rewrite historical reports.

- [ ] **Step 4: 验证、PR、合并 closeout。**

```bash
uv run --with pyyaml python bin/ssot/doc-ssot-lint.py --json
uv run --with pyyaml python bin/ssot/doc-governance-check.py --no-new-warnings
git diff --check
```

Expected: PASS. Commit only the new retrospective and index pointer, PR, wait for CI, merge, and link final merged PRs/commits in the report.

## Plan Self-review

| Required outcome | Plan task |
| --- | --- |
| Two bounded CR08 inputs and explicit scope | Task 1 owner + Task 3 binding validator |
| Correct 0/1/2 semantics | Task 1 evidence tests + Task 2 CLI/MCP tests |
| Documents remains unchanged | Task 1 digest regression + Task 4 installed digest |
| Cockpit/domain context/client discovery | Task 2 both MCP surfaces + Task 3 profile/Tunnel allowlist |
| One Workspace SSOT | Task 3 exact binding and strict consumers |
| No auto-maintenance or controller rewrite | Global constraints + Task 4 limits |
| Iterative PR/CI/merge evidence | Task 1–4 independent integration stages |
