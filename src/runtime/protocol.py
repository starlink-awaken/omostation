"""L0 Protocol Registry — protocol definitions for the eCOS protocol weave."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


# ─── Protocol Types ────────────────────────────────────────────────────────
ProtocolCategory = Literal[
    "agent-communication", "model-access", "service-discovery",
    "state-sync", "identity-auth", "data-exchange", "orchestration"
]

ProtocolStatus = Literal["active", "draft", "deprecated", "planned"]


@dataclass
class ProtocolEntry:
    """A single protocol in the L0 weave."""
    name: str
    version: str
    category: ProtocolCategory
    status: ProtocolStatus
    description: str
    spec_url: str | None = None
    port_range: str | None = None
    transport: list[str] = field(default_factory=lambda: ["stdio", "http"])
    implementations: list[str] = field(default_factory=list)
    notes: str = ""


# ─── L0 Registry ───────────────────────────────────────────────────────────
# Source of truth for all protocols in the eCOS stack.
# This lives in the Runtime project repo (version controlled).

L0_PROTOCOLS: list[ProtocolEntry] = [
    # ── Agent Communication ─────────────────────────────────────────────
    ProtocolEntry(
        name="MCP",
        version="2025-03-26",
        category="agent-communication",
        status="active",
        description="Model Context Protocol — tool/resource/prompt discovery for LLMs",
        spec_url="https://modelcontextprotocol.io",
        port_range="7420-7425",
        transport=["stdio", "http", "websocket"],
        implementations=["kairon/packages/agora (MCP server)", "native-mcp (Hermes client)"],
    ),
    ProtocolEntry(
        name="ACP",
        version="0.1",
        category="agent-communication",
        status="active",
        description="Agent Communication Protocol — stdin/stdout JSON-RPC for multi-agent",
        port_range="—",
        transport=["stdio"],
        implementations=["Hermes ACP client (hermes_cli.acp.*)"],
        notes="Used by Hermes subagent delegation. Pipeline-based communication.",
    ),
    ProtocolEntry(
        name="A2A",
        version="0.1",
        category="agent-communication",
        status="planned",
        description="Agent-to-Agent — direct inter-agent messaging (Google A2A inspired)",
        port_range="7430-7435",
        transport=["http", "websocket"],
        implementations=[""],
        notes="Not yet implemented. Planned for cross-machine agent orchestration.",
    ),

    # ── Service Discovery ──────────────────────────────────────────────
    ProtocolEntry(
        name="Agora Discovery",
        version="1",
        category="service-discovery",
        status="active",
        description="Agora service registration and routing",
        port_range="7426, 7430-7431",
        transport=["http", "mcp"],
        implementations=["kairon/packages/agora"],
        notes="Docker container integration-agora-1. MCP on :7431, HTTP on :7430, API on :7426.",
    ),
    ProtocolEntry(
        name="Runtime Matrix",
        version="2",
        category="service-discovery",
        status="active",
        description="Service registry YAML at $RUNTIME_HOME/matrix.yaml",
        port_range="—",
        transport=["file"],
        implementations=["runtime CLI (runtime matrix get/list)", "runtime/scripts/matrix.sh"],
        notes="Human-readable SSOT for all services. Env-var-based paths.",
    ),

    # ── State Sync ─────────────────────────────────────────────────────
    ProtocolEntry(
        name="KOS State",
        version="1",
        category="state-sync",
        status="active",
        description="Knowledge Operating System — capture/ingest/search pipeline",
        port_range="—",
        transport=["file", "mcp", "http"],
        implementations=["kairon/packages/kos", "kos capture/ingest/search CLI"],
        notes="LanceDB vector search, full-text index. MCP server on port TBD.",
    ),
    ProtocolEntry(
        name="GBrain State",
        version="1",
        category="state-sync",
        status="active",
        description="Postgres+pgvector knowledge graph. Semantic + relational storage.",
        port_range="5433",
        transport=["postgres wire", "http"],
        implementations=["gbrain-postgres (Docker)", "gbrain-index (daily batch)"],
    ),

    # ── Model Access ───────────────────────────────────────────────────
    ProtocolEntry(
        name="Ollama API",
        version="1",
        category="model-access",
        status="active",
        description="Local LLM inference via Ollama (OpenAI-compatible API)",
        port_range="11434",
        transport=["http"],
        implementations=["ollama serve", "nomic-embed-text (embeddings)", "qwen3.6:35b-a3b"],
        notes="Required by gbrain for embeddings. Currently idle.",
    ),

    # ── Identity & Auth ────────────────────────────────────────────────
    ProtocolEntry(
        name="OMO Governance",
        version="4.0",
        category="identity-auth",
        status="active",
        description="OMO v4 Governance — truth mutation lifecycle, debt registry, phase system",
        port_range="—",
        transport=["cli", "file"],
        implementations=["projects/omo/ (kairon)", "omo-cli", ".omo/ truth data plane"],
        notes="KEI contract for kernel extension. L2 kernel governance.",
    ),

    # ── Orchestration ──────────────────────────────────────────────────
    ProtocolEntry(
        name="Cron Scheduler",
        version="2",
        category="orchestration",
        status="active",
        description="cron-service: 37 scheduled jobs with MCP, HTTP API, launchd integration",
        port_range="7450-7451",
        transport=["http", "mcp"],
        implementations=["kairon/packages/cron-service"],
        notes="launchd label: com.user.cron-service. tick_interval=15s.",
    ),
    ProtocolEntry(
        name="Agent Runtime API",
        version="1",
        category="orchestration",
        status="active",
        description="Agent lifecycle management HTTP API",
        port_range="9876",
        transport=["http"],
        implementations=["kairon/packages/agent-runtime"],
        notes="Health endpoint: GET /health. PID 86924.",
    ),
]


def registry_path() -> Path:
    """Path to the YAML protocol registry file."""
    return Path(__file__).parent.parent.parent / "protocols" / "L0-registry.yaml"


def get_protocol(name: str) -> ProtocolEntry | None:
    """Find a protocol by name."""
    for p in L0_PROTOCOLS:
        if p.name.lower() == name.lower():
            return p
    return None


def by_category(cat: ProtocolCategory) -> list[ProtocolEntry]:
    """Filter protocols by category."""
    return [p for p in L0_PROTOCOLS if p.category == cat]


def active_protocols() -> list[ProtocolEntry]:
    """Return only active protocols."""
    return [p for p in L0_PROTOCOLS if p.status == "active"]
