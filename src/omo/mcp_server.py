import json
import os
import subprocess
from pathlib import Path

from fastmcp import FastMCP
from pydantic import BaseModel

mcp = FastMCP("omo")

OMO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(OMO_ROOT.parents[1])))


class BridgeRequest(BaseModel):
    spec_path: str


class DispatchRequest(BaseModel):
    task_id: str
    worker_id: str


class ReclaimRequest(BaseModel):
    task_id: str
    worker_id: str


class YieldRequest(BaseModel):
    task_id: str
    reason: str


class DebtListRequest(BaseModel):
    omo_dir: str = ".omo"
    status: str | None = None  # filter: open, closed, or None for all


class DebtSummaryRequest(BaseModel):
    omo_dir: str = ".omo"


class MetacognitionRequest(BaseModel):
    command: str = "baseline"
    lens: str | None = None  # X1, X2, X3, or None/empty for all


class ValidateTaskRequest(BaseModel):
    task_data: dict
    group: str | None = "planned"


# ── Advisory Lock (TASK-94BB9C70, 防 concurrent-agent-contention) ──


class AcquireLockRequest(BaseModel):
    resource: str  # 被锁资源 (文件路径或逻辑名)
    holder: str  # 持有者标识 (session_id / agent_id)
    ttl: int = 300  # 锁有效期秒 (过期可抢占, 防死锁)
    omo_dir: str = ".omo"


class ReleaseLockRequest(BaseModel):
    resource: str
    holder: str
    omo_dir: str = ".omo"


class CheckLockRequest(BaseModel):
    resource: str
    omo_dir: str = ".omo"


class ListLocksRequest(BaseModel):
    omo_dir: str = ".omo"


class CheckGacRuleRequest(BaseModel):
    resource: str  # 文件路径
    content: str  # 待检查内容
    omo_dir: str = ".omo"


@mcp.tool()
async def validate_task(req: ValidateTaskRequest) -> str:
    """Validate a task data dict against the OMO task schema. Returns {"valid": bool, "errors": [...]}."""
    try:
        from .omo_task_schema import validate_task_data

        errors = validate_task_data(req.task_data, group=req.group)
        return json.dumps(
            {"valid": len(errors) == 0, "errors": errors}, ensure_ascii=False
        )
    except Exception as e:  # defensive fallback
        return json.dumps({"valid": False, "errors": [str(e)]}, ensure_ascii=False)


@mcp.tool()
async def omo_bridge(req: BridgeRequest) -> str:
    """Import a markdown spec into OMO tasks."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.cli", "bridge", req.spec_path, "--sequential"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error bridging spec: {e.stderr}"


@mcp.tool()
async def omo_worker_dispatch(req: DispatchRequest) -> str:
    """Dispatch an OMO task to a worker."""
    try:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "omo.cli",
                "worker",
                "dispatch",
                req.task_id,
                "--worker",
                req.worker_id,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error dispatching task: {e.stderr}"


@mcp.tool()
async def omo_worker_reclaim(req: ReclaimRequest) -> str:
    """Reclaim a completed or failed OMO task."""
    try:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "omo.cli",
                "worker",
                "reclaim",
                req.task_id,
                "--worker",
                req.worker_id,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error reclaiming task: {e.stderr}"


@mcp.tool()
async def omo_yield_task(req: YieldRequest) -> str:
    """[C2G v2] Abort and yield an active OMO task back to the ideation sandbox."""
    try:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "omo.cli",
                "worker",
                "yield",
                req.task_id,
                "--reason",
                req.reason,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error yielding task: {e.stderr}"


@mcp.tool()
async def omo_gc() -> str:
    """Run garbage collection on stale OMO drafts."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.cli", "worker", "gc"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error running GC: {e.stderr}"


@mcp.tool()
async def omo_debt_list(req: DebtListRequest) -> str:
    """List all debt items with X1/X2/X3 metadata. Filters by status (open/closed) if provided."""
    try:
        from .omo_debt_registry import load_debt_ledger

        omo_path = Path(req.omo_dir)
        if not omo_path.is_absolute():
            omo_path = OMO_ROOT / req.omo_dir

        ledger = load_debt_ledger(omo_path)

        items = []
        for item in ledger.items:
            if (
                req.status
                and req.status.lower() == "open"
                and item.lifecycle_state == "closed"
            ):
                continue
            if (
                req.status
                and req.status.lower() == "closed"
                and item.lifecycle_state != "closed"
            ):
                continue
            items.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "dimension": item.dimension,
                    "subdimension": item.subdimension,
                    "severity": item.severity,
                    "weight": item.weight,
                    "lifecycle_state": item.lifecycle_state,
                    "owner": item.owner,
                    "x1_policy_ref": item.x1_policy_ref or "",
                    "x2_freshness": item.x2_freshness or "",
                    "x3_tier": item.x3_tier or "",
                    "gate_level": item.gate_level,
                    "opened_at": item.opened_at,
                }
            )

        return json.dumps(
            {"count": len(items), "items": items}, indent=2, ensure_ascii=False
        )
    except Exception as e:  # defensive fallback
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def omo_debt_summary(req: DebtSummaryRequest) -> str:
    """Run debt report and return a summary with X3 weight breakdown."""
    try:
        debt_script = OMO_ROOT / "scripts" / "omo_debt.py"
        result = subprocess.run(
            ["python3", str(debt_script), "report", "--omo-dir", req.omo_dir],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error generating debt report: {e.stderr}"


@mcp.tool()
async def omo_metacognition(req: MetacognitionRequest) -> str:
    """Run metacognition with optional lens parameter (X1/X2/X3) for filtered baseline."""
    try:
        cmd = [
            "python3",
            "-m",
            "omo.omo_metacognition",
            req.command,
        ]
        if req.lens:
            cmd.extend(["--lens", req.lens])

        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=str(OMO_ROOT)
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error running metacognition: {e.stderr}"


# ── CARDS tools ───────────────────────────────────────────


class CardsStatusRequest(BaseModel):
    limit: int = 15


class CardsSearchRequest(BaseModel):
    query: str
    limit: int = 20


class CardsCreateRequest(BaseModel):
    card_type: str  # idea|task|debt|delivery|research
    title: str
    domain: str = "meta"
    priority: str = "P2"
    summary: str = ""
    content: str = ""
    parent: str = ""
    deadline: str = ""
    severity: str = ""
    tags: str = ""


class CardsUpdateRequest(BaseModel):
    card_id: str
    status: str = ""
    summary: str = ""
    content: str = ""
    priority: str = ""
    note: str = "updated via mcp"


@mcp.tool()
async def cards_status(req: CardsStatusRequest) -> str:
    """Get all active cards sorted by priority. Use this on every session startup to recover task context."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.omo_cards", "list", "--limit", str(req.limit)],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(OMO_ROOT),
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
async def cards_search(req: CardsSearchRequest) -> str:
    """Search cards by keyword in title, summary, content, and tags."""
    try:
        result = subprocess.run(
            [
                "python3",
                "-m",
                "omo.omo_cards",
                "search",
                req.query,
                "--limit",
                str(req.limit),
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(OMO_ROOT),
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
async def cards_check() -> str:
    """Check constraint violations: overdue deadlines, idea pool overflow, review reminders."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.omo_cards", "check"],
            capture_output=True,
            text=True,
            cwd=str(OMO_ROOT),
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return e.stdout or f"Error: {e.stderr}"


@mcp.tool()
async def cards_create(req: CardsCreateRequest) -> str:
    """Create a new card (idea, task, debt, or delivery)."""
    try:
        cmd = [
            "python3",
            "-m",
            "omo.omo_cards",
            "create",
            req.card_type,
            req.title,
            "--domain",
            req.domain,
            "--priority",
            req.priority,
        ]
        if req.summary:
            cmd.extend(["--summary", req.summary])
        if req.content:
            cmd.extend(["--content", req.content])
        if req.parent:
            cmd.extend(["--parent", req.parent])
        if req.deadline:
            cmd.extend(["--deadline", req.deadline])
        if req.severity:
            cmd.extend(["--severity", req.severity])
        if req.tags:
            cmd.extend(["--tags"] + req.tags.split(","))
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=str(OMO_ROOT)
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
async def cards_update(req: CardsUpdateRequest) -> str:
    """Update a card's status, summary, content, or priority."""
    try:
        cmd = [
            "python3",
            "-m",
            "omo.omo_cards",
            "update",
            req.card_id,
        ]
        if req.status:
            cmd.extend(["--status", req.status])
        if req.summary:
            cmd.extend(["--summary", req.summary])
        if req.content:
            cmd.extend(["--content", req.content])
        if req.priority:
            cmd.extend(["--priority", req.priority])
        if req.note:
            cmd.extend(["--note", req.note])
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, cwd=str(OMO_ROOT)
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
async def acquire_lock(req: AcquireLockRequest) -> str:
    """获取 advisory lock — agent 编辑共享文件前调用 (TASK-94BB9C70).

    防 concurrent-agent-contention: 多 agent 并发改同文件, 第二个被拒.
    返回 {"status": "ok"} (获取/reentrant) 或 {"status": "locked", "holder": ...} (被拒).
    拿到 ok 才编辑, 编辑完调 release_lock.
    """
    from omo._shared.advisory_lock import AdvisoryLock

    lock = AdvisoryLock(WORKSPACE_ROOT / req.omo_dir / "state" / "locks")
    return json.dumps(
        lock.acquire(req.resource, req.holder, req.ttl), ensure_ascii=False
    )


@mcp.tool()
async def release_lock(req: ReleaseLockRequest) -> str:
    """释放 advisory lock — agent 编辑完后调用 (TASK-94BB9C70).

    验证 holder (B 不能释放 A 的锁). 返回 {"status": "ok"} 或 {"status": "forbidden"}.
    """
    from omo._shared.advisory_lock import AdvisoryLock

    lock = AdvisoryLock(WORKSPACE_ROOT / req.omo_dir / "state" / "locks")
    return json.dumps(lock.release(req.resource, req.holder), ensure_ascii=False)


@mcp.tool()
async def check_lock(req: CheckLockRequest) -> str:
    """查询锁状态 (不获取). agent 编辑前 peek. 返回 free/locked/stale."""
    from omo._shared.advisory_lock import AdvisoryLock

    lock = AdvisoryLock(WORKSPACE_ROOT / req.omo_dir / "state" / "locks")
    return json.dumps(lock.check(req.resource), ensure_ascii=False)


@mcp.tool()
async def list_locks(req: ListLocksRequest) -> str:
    """列出所有 advisory lock (含过期, 供审计/dashboard)."""
    from omo._shared.advisory_lock import AdvisoryLock

    lock = AdvisoryLock(WORKSPACE_ROOT / req.omo_dir / "state" / "locks")
    return json.dumps(lock.list_locks(), ensure_ascii=False)


@mcp.tool()
async def check_gac_rule(req: "CheckGacRuleRequest") -> str:
    """检查内容是否违反 GaC 规则 (机制 3 跨工具主力, ADR-0106).

    agent 经 MCP 调 (Cursor/Codex/Devin), 编辑前检查 SSOT drift.
    与 gac-hook-pre-edit.py (Claude Code 通道) + CI gate (兜底) 多通道.
    支持 5 种 check_type: ssot_pointer / port_hardcode / import_nucleus / direct_omo_io / broad_except.
    """
    import fnmatch
    import re

    reg = (
        WORKSPACE_ROOT / req.omo_dir / "_truth" / "registry" / "governance-checks.yaml"
    )
    if not reg.exists():
        return json.dumps(
            {"status": "ok", "warnings": [], "reason": "registry not found"}
        )

    import yaml

    docs = [d for d in yaml.safe_load_all(reg.read_text(encoding="utf-8")) if d]
    rules = docs[-1].get("gac", {}).get("rules", []) if docs else []
    active_rules = [r for r in rules if r.get("lifecycle") == "active"]

    HOOKABLE = {
        "ssot_pointer",
        "port_hardcode",
        "import_nucleus",
        "direct_omo_io",
        "broad_except",
    }

    try:
        rel = str(Path(req.resource).resolve().relative_to(WORKSPACE_ROOT))
    except (ValueError, OSError):
        rel = req.resource

    is_py = rel.endswith(".py")
    is_yaml = rel.endswith((".yaml", ".yml"))
    content = req.content
    warnings = []

    for rule in active_rules:
        ct = rule.get("check_type", "")
        if ct not in HOOKABLE:
            continue
        rid = rule.get("id", "?")

        if ct == "ssot_pointer":
            target = rule.get("target", "")
            if "::" not in target:
                continue
            field = target.split("::", 1)[1]
            forbid = rule.get("forbid_copy_in", [])
            matched = any(
                fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, f"**/{p}")
                for p in forbid
            )
            if not matched:
                continue
            pattern = re.compile(rf"(?<![\[\.]){re.escape(field)}\s*:\s*\d")
            for m in pattern.finditer(content):
                ctx = content[max(0, m.start() - 40) : m.end() + 80]
                if any(
                    kw in ctx
                    for kw in [
                        "_ref",
                        "见 ",
                        "see ",
                        "指向",
                        "指针",
                        "SSOT",
                        "system.yaml",
                        "示例值",
                    ]
                ):
                    continue
                warnings.append(
                    f"{rid}: {rel} 硬编码 {field} 值 (违反 SSOT, 应用指针引用)"
                )

        elif ct == "port_hardcode" and (is_py or is_yaml):
            pattern = re.compile(r"(?<!\w)[:=](\d{4,5})(?!\d)")
            for m in pattern.finditer(content):
                port = int(m.group(1))
                if 1024 < port < 65536:
                    ctx = content[max(0, m.start() - 30) : m.end() + 30]
                    if any(
                        kw in ctx.lower()
                        for kw in ["env", "os.environ", "getenv", "default", "registry"]
                    ):
                        continue
                    warnings.append(
                        f"{rid}: {rel} 疑似端口硬编码 :{port} (应走 port-registry + env)"
                    )

        elif ct == "import_nucleus" and is_py:
            pattern = re.compile(r"^from\s+nucleus\b|^import\s+nucleus\b", re.MULTILINE)
            for m in pattern.finditer(content):
                ctx = content[max(0, m.start() - 20) : m.end() + 20]
                if "type: ignore" in ctx or "TYPE_CHECKING" in ctx:
                    continue
                warnings.append(
                    f"{rid}: {rel} 顶层 import nucleus (已废弃, 改为 lazy import)"
                )

        elif ct == "direct_omo_io" and is_py:
            pattern = re.compile(
                r'(open|write_text|mkdir|Path)\s*\(\s*["\'].*\.omo/', re.IGNORECASE
            )
            for m in pattern.finditer(content):
                warnings.append(
                    f"{rid}: {rel} 疑似 direct .omo I/O (应走 omo CLI / broker)"
                )

        elif ct == "broad_except" and is_py:
            pattern = re.compile(r"except\s*(\s*:|\s+Exception\s*:)", re.MULTILINE)
            count = len(pattern.findall(content))
            if count > 3:
                warnings.append(
                    f"{rid}: {rel} 有 {count} 处 broad except (建议细化异常类型)"
                )

    return json.dumps(
        {
            "status": "ok" if not warnings else "warn",
            "warnings": warnings,
            "rules_checked": len(
                [r for r in active_rules if r.get("check_type", "") in HOOKABLE]
            ),
        },
        ensure_ascii=False,
    )


@mcp.resource("bos://omo/debt")
def read_omo_debt() -> str:
    """Dynamically generate the debt list as markdown."""
    try:
        debt_script = WORKSPACE_ROOT / "projects" / "omo" / "scripts" / "omo_debt.py"
        result = subprocess.run(
            [
                "python3",
                str(debt_script),
                "report",
                "--omo-dir",
                str(WORKSPACE_ROOT / ".omo"),
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(WORKSPACE_ROOT),
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error generating debt report: {e.stderr}"


@mcp.resource("bos://omo/tasks/active")
def read_omo_active_tasks() -> str:
    """Dynamically fetch the active tasks."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.omo_cards", "list", "--limit", "20"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(WORKSPACE_ROOT / "projects" / "omo"),
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error fetching active tasks: {e.stderr}"


@mcp.resource("bos://omo/standards/{rule}")
def read_omo_standard(rule: str) -> str:
    """Read static standard rules from .omo/standards/."""
    try:
        import urllib.parse

        rule = urllib.parse.unquote(rule)
        # Ensure it has .md extension
        if not rule.endswith(".md"):
            rule += ".md"

        omo_root = WORKSPACE_ROOT / ".omo"
        target_path = (omo_root / "standards" / rule).resolve()

        if not str(target_path).startswith(str(omo_root / "standards")):
            return "Error: Path traversal detected."

        if not target_path.exists() or not target_path.is_file():
            return f"Error: Standard not found at {rule}"

        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:  # defensive fallback
        return f"Error reading standard: {e!s}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
