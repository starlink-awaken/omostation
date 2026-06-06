import subprocess
import json
from pathlib import Path
from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional

mcp = FastMCP("omo")

OMO_ROOT = Path(__file__).resolve().parents[1]

class BridgeRequest(BaseModel):
    spec_path: str

class DispatchRequest(BaseModel):
    task_id: str
    worker_id: str

class ReclaimRequest(BaseModel):
    task_id: str
    worker_id: str

class DebtListRequest(BaseModel):
    omo_dir: str = ".omo"
    status: Optional[str] = None  # filter: open, closed, or None for all

class DebtSummaryRequest(BaseModel):
    omo_dir: str = ".omo"

class MetacognitionRequest(BaseModel):
    command: str = "baseline"
    lens: Optional[str] = None  # X1, X2, X3, or None/empty for all

@mcp.tool()
async def omo_bridge(req: BridgeRequest) -> str:
    """Import a markdown spec into OMO tasks."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.cli", "bridge", req.spec_path, "--sequential"],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error bridging spec: {e.stderr}"

@mcp.tool()
async def omo_worker_dispatch(req: DispatchRequest) -> str:
    """Dispatch an OMO task to a worker."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.cli", "worker", "dispatch", req.task_id, "--worker", req.worker_id],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error dispatching task: {e.stderr}"

@mcp.tool()
async def omo_worker_reclaim(req: ReclaimRequest) -> str:
    """Reclaim a completed or failed OMO task."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.cli", "worker", "reclaim", req.task_id, "--worker", req.worker_id],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error reclaiming task: {e.stderr}"

@mcp.tool()
async def omo_gc() -> str:
    """Run garbage collection on stale OMO drafts."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.cli", "worker", "gc"],
            capture_output=True, text=True, check=True
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
            if req.status and req.status.lower() == "open" and item.lifecycle_state == "closed":
                continue
            if req.status and req.status.lower() == "closed" and item.lifecycle_state != "closed":
                continue
            items.append({
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
            })

        return json.dumps({"count": len(items), "items": items}, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool()
async def omo_debt_summary(req: DebtSummaryRequest) -> str:
    """Run debt report and return a summary with X3 weight breakdown."""
    try:
        debt_script = OMO_ROOT / "scripts" / "omo_debt.py"
        result = subprocess.run(
            ["python3", str(debt_script), "report", "--omo-dir", req.omo_dir],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error generating debt report: {e.stderr}"

@mcp.tool()
async def omo_metacognition(req: MetacognitionRequest) -> str:
    """Run metacognition with optional lens parameter (X1/X2/X3) for filtered baseline."""
    try:
        cmd = [
            "python3", "-m", "omo.omo_metacognition",
            req.command,
        ]
        if req.lens:
            cmd.extend(["--lens", req.lens])

        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True,
            cwd=str(OMO_ROOT)
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
            capture_output=True, text=True, check=True, cwd=str(OMO_ROOT)
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
async def cards_search(req: CardsSearchRequest) -> str:
    """Search cards by keyword in title, summary, content, and tags."""
    try:
        result = subprocess.run(
            ["python3", "-m", "omo.omo_cards", "search", req.query, "--limit", str(req.limit)],
            capture_output=True, text=True, check=True, cwd=str(OMO_ROOT)
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
            capture_output=True, text=True, cwd=str(OMO_ROOT)
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return e.stdout or f"Error: {e.stderr}"


@mcp.tool()
async def cards_create(req: CardsCreateRequest) -> str:
    """Create a new card (idea, task, debt, or delivery)."""
    try:
        cmd = [
            "python3", "-m", "omo.omo_cards", "create",
            req.card_type, req.title,
            "--domain", req.domain,
            "--priority", req.priority,
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
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=str(OMO_ROOT))
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.tool()
async def cards_update(req: CardsUpdateRequest) -> str:
    """Update a card's status, summary, content, or priority."""
    try:
        cmd = [
            "python3", "-m", "omo.omo_cards", "update",
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
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=str(OMO_ROOT))
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr}"


@mcp.resource("bos://omo/debt")
def read_omo_debt() -> str:
    """Dynamically generate the debt list as markdown."""
    try:
        import os
        workspace_root = Path(os.environ.get("WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"))
        debt_script = workspace_root / "projects" / "omo" / "scripts" / "omo_debt.py"
        result = subprocess.run(
            ["python3", str(debt_script), "report", "--omo-dir", str(workspace_root / ".omo")],
            capture_output=True, text=True, check=True, cwd=str(workspace_root)
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error generating debt report: {e.stderr}"

@mcp.resource("bos://omo/tasks/active")
def read_omo_active_tasks() -> str:
    """Dynamically fetch the active tasks."""
    try:
        import os
        workspace_root = Path(os.environ.get("WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"))
        result = subprocess.run(
            ["python3", "-m", "omo.omo_cards", "list", "--limit", "20"],
            capture_output=True, text=True, check=True, cwd=str(workspace_root / "projects" / "omo")
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error fetching active tasks: {e.stderr}"

@mcp.resource("bos://omo/standards/{rule}")
def read_omo_standard(rule: str) -> str:
    """Read static standard rules from .omo/standards/."""
    try:
        import urllib.parse
        import os
        workspace_root = Path(os.environ.get("WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"))
        
        rule = urllib.parse.unquote(rule)
        # Ensure it has .md extension
        if not rule.endswith('.md'):
            rule += '.md'
            
        omo_root = workspace_root / ".omo"
        target_path = (omo_root / "standards" / rule).resolve()
        
        if not str(target_path).startswith(str(omo_root / "standards")):
            return "Error: Path traversal detected."
            
        if not target_path.exists() or not target_path.is_file():
            return f"Error: Standard not found at {rule}"
            
        with open(target_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading standard: {str(e)}"

def main():
    mcp.run()

if __name__ == "__main__":
    main()

