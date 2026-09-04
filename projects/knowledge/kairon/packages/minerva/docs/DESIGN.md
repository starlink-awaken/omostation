---
title: DESIGN
type: doc
---

# Minerva — Detailed Technical Design

## 1. Component Design

### 1.1 Triage Router (`minerva.triage`)

**Purpose:** Classify incoming research queries into L0-L4 execution levels. Runs locally on Qwen3.6-35B-A3B, <1s latency.

**Input:** Natural language research query
**Output:** `TriageResult { level: L0|L1|L2|L3|L4, scores: {domain, timeliness, depth, multi_source, privacy}, cost_estimate: float, model_plan: {...}, search_plan: [...], warnings: [...] }`

**Scoring Dimensions (1-5):**
| Dimension | Weight | Description |
|-----------|--------|-------------|
| domain_complexity | 0.30 | Domain knowledge depth required |
| timeliness | 0.15 | How time-sensitive the query is |
| depth_required | 0.30 | Analysis depth needed |
| multi_source | 0.15 | Number/type of sources needed |
| privacy_sensitivity | 0.10 | Data privacy requirements |

**Routing Rules:**
```
total = Σ(dim_i × weight_i)
privacy ≥ 4 → force L0/L1 (local only, block cloud APIs)
total ≤ 1.5 → L0 | ≤ 2.5 → L1 | ≤ 3.5 → L2 | ≤ 4.2 → L3 | > 4.2 → L4
```

**Keyword Boosts:**
- Contains "compare/vs/diff" → depth += 1.0
- Contains "latest/today/breaking" → timeliness += 1.0
- Contains "paper/academic/scholar" → multi_source += 1.0
- Contains "code/implement/repo" → domain += 1.0

**LLM Prompt Strategy:**
```python
TRIAGE_SYSTEM_PROMPT = """You are a research task classifier. Analyze the user's query and output JSON with scores for 5 dimensions.

Scoring guidelines:
- domain_complexity: 1=common knowledge, 2=single domain, 3=2-3 domains, 4=deep technical + cross-domain, 5=frontier/no standard answer
- timeliness: 1=timeless, 2=yearly, 3=quarterly, 4=monthly/weekly, 5=real-time/daily
- depth_required: 1=one sentence, 2=brief overview, 3=structured answer, 4=causal+comparative, 5=original insight+verification
- multi_source: 1=single page, 2=2-3 pages, 3=5-10 sources, 4=papers+code+multi-type, 5=all types+paid databases
- privacy_sensitivity: 1=public info, 2=work docs, 3=internal business, 4=confidential/PII, 5=legal/medical/compliance

Output ONLY valid JSON, no other text."""
```

### 1.2 Pipeline Engine (`minerva.pipeline`)

**Purpose:** Execute tiered research pipelines with pluggable stages.

Each pipeline level is a sequence of stages. Stages are composable and can be:
- `SearchStage` — query search backends
- `ExtractStage` — extract content from URLs
- `EntityStage` — extract entities via NLP/LLM
- `AnalyzeStage` — cross-reference and analyze
- `ReasonStage` — deep reasoning (contradiction detection, temporal analysis)
- `OutputStage` — generate reports, update knowledge base

**Pipeline Level Definitions:**
```
L0_QUICK = [SearchStage(basic=True), OutputStage(format="concise")]
L1_STANDARD = [DecomposeStage, ParallelSearchStage, CrossAnalyzeStage, OutputStage(format="structured")]
L2_DEEP = [DecomposeStage, MultiSourceSearchStage, EntityStage, DeepReadStage, CrossAnalyzeStage, QualityGateStage, OutputStage(format="report")]
L3_COMPREHENSIVE = L2_DEEP + [AcademicDeepDiveStage, CounterArgumentStage, ExpertReviewStage]
L4_MAX = L3_COMPREHENSIVE + [MultiModelVotingStage, HumanCheckpointStage]
```

### 1.3 Knowledge Store (`minerva.knowledge`)

**Purpose:** Multi-backend knowledge storage with tiered fallback.

**Tier 1 Backends (always available):**
```
MarkdownStore     — llm-wiki-agent managed wiki files
SQLiteStore       — FTS5 full-text search + structured entity tables
LanceDBStore      — vector embeddings (384d all-MiniLM-L6-v2)
```

**Tier 2 Backends (gracefully degraded):**
```
Neo4jStore        — property graph database (via Graphiti)
SemanticaStore    — SHACL ontology + Allen temporal + Datalog reasoning
```

**Entity Schema (SQLite + optional Neo4j):**
```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,           -- UUID
    type TEXT NOT NULL,            -- Person|Org|Product|Publication|Concept|Metric|Event|Claim|Task|Timeline
    name TEXT NOT NULL,
    aliases TEXT,                  -- JSON array
    properties TEXT,               -- JSON object, type-specific
    valid_from TEXT,               -- ISO-8601
    valid_until TEXT,              -- ISO-8601, NULL = still valid
    superseded_by TEXT,            -- entity ID
    recorded_at TEXT NOT NULL,
    last_verified TEXT,
    source_ids TEXT,               -- JSON array of source document hashes
    confidence TEXT                -- HIGH|MEDIUM|LOW
);

CREATE VIRTUAL TABLE entities_fts USING fts5(name, aliases, content='entities');

CREATE TABLE relations (
    id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES entities(id),
    predicate TEXT NOT NULL,       -- CREATED_BY|CITES|COMPETES_WITH|ENABLES|IMPROVES|OBSOLETES|...
    object_id TEXT NOT NULL REFERENCES entities(id),
    valid_from TEXT,
    valid_until TEXT,
    confidence TEXT,
    source_ids TEXT,
    recorded_at TEXT NOT NULL
);
```

### 1.4 Search Engine (`minerva.search`)

**Purpose:** Unified search across multiple backends with RRF fusion.

**Search Modes:**
```
fulltext   → SQLite FTS5 (keyword)
semantic   → LanceDB (vector similarity)
graph      → Graphiti MCP / SQLite RECURSIVE CTE (entity traversal)
hybrid     → All three, RRF fused
timeline   → Entities filtered by valid_from/valid_until range
```

**Backend Priority:**
```
1. SearXNG (self-hosted, free, unlimited)
2. 秘塔AI搜索 (Chinese content, paid credits)
3. Exa API (semantic web search, $7/1K)
4. Semantic Scholar (academic, free)
5. arXiv API (preprints, free)
6. DuckDuckGo (fallback, free)
```

### 1.5 Executor (`minerva.executor`)

**Purpose:** Orchestrate research execution in three modes.

**Execution Modes:**
```
Immediate   — research_now():  execute pipeline immediately, return result
Scheduled   — research_schedule(): register cron task, execute on schedule
Watch       — research_watch():  poll sources, execute on new content
```

**State Persistence:**
```
~/minerva/state/
├── scheduled_tasks.json    # [{id, query, cron, level, ...}]
├── watch_configs.json      # [{id, topic, sources, interval, ...}]
├── execution_log.jsonl     # [{task_id, level, start, end, cost, ...}]
├── notifications.json      # [{task_id, status, summary, timestamp}]
├── cost_ledger.jsonl       # [{date, service, amount, task_id}]
└── budget.json             # {monthly_limit, current_spend, alerts}
```

### 1.6 MCP Server (`minerva.mcp_server`)

**Purpose:** Expose Minerva as 5 Super Tools via Model Context Protocol.

**Why Super Tools (not 15+ individual tools):**
Following Dropbox Dash's 2026 best practice: individual MCP tool definitions consume context window tokens. Combining related operations into "Super Tools" dramatically reduces overhead while maintaining full functionality.

**Tool Definitions:**
```python
SUPER_TOOLS = {
    "research_now": {
        "description": "Execute deep research immediately. Auto-routes to appropriate pipeline level.",
        "parameters": {
            "query": "string (required) — research question",
            "level": "string (optional) — auto|L0|L1|L2|L3|L4, default auto",
            "max_cost": "float (optional) — max cost in USD, default by level",
        },
    },
    "research_schedule": {
        "description": "Schedule recurring research. Supports cron expressions.",
        "parameters": {
            "query": "string (required)",
            "cron": "string (required) — e.g., '0 8 * * *'",
            "level": "string (optional)",
            "notify": "string (optional) — mcp|none",
        },
    },
    "research_watch": {
        "description": "Watch topics for new content. Triggers research automatically.",
        "parameters": {
            "topic": "string (required)",
            "sources": "list[string] — arxiv,github_trending,reddit,zhihu,...",
            "check_interval": "string — hourly|daily|weekly",
            "max_cost_per_run": "float (optional)",
        },
    },
    "knowledge_search": {
        "description": "Search existing knowledge base.",
        "parameters": {"query": "string (required)", "mode": "string — hybrid|fulltext|semantic|graph|timeline"},
    },
    "knowledge_ingest": {
        "description": "Ingest new content into knowledge base.",
        "parameters": {"source": "string — URL or file path", "source_type": "string — auto|url|pdf|markdown|code"},
    },
}
```

## 2. Interface Contracts

### 2.1 TriageRouter Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ResearchLevel(Enum):
    L0 = "L0"  # Quick: <30s, $0
    L1 = "L1"  # Standard: <3min, $0
    L2 = "L2"  # Deep: 5-15min, ~$0.30
    L3 = "L3"  # Comprehensive: 10-30min, ~$2
    L4 = "L4"  # Max: 30min+, $2-10


@dataclass
class TriageResult:
    level: ResearchLevel
    scores: dict[str, int]  # {domain, timeliness, depth, multi_source, privacy}
    cost_estimate: float
    model_plan: dict  # {agent_model, reasoning_model, writer_model}
    search_plan: list[str]  # ["searxng", "exa", "scholar", ...]
    warnings: list[str]


class ITriageRouter(ABC):
    @abstractmethod
    async def classify(self, query: str) -> TriageResult:
        """Classify query and return routing decision."""
        ...
```

### 2.2 Pipeline Interface

```python
@dataclass
class ResearchContext:
    query: str
    level: ResearchLevel
    triage: TriageResult
    sub_questions: list[str] = None
    search_results: list[dict] = None
    extracted_content: list[str] = None
    entities: list[dict] = None
    relations: list[dict] = None
    analysis: dict = None
    contradictions: list[dict] = None
    report: str = None
    cost: float = 0.0
    started_at: str = None
    completed_at: str = None


class IPipelineStage(ABC):
    @abstractmethod
    async def execute(self, ctx: ResearchContext) -> ResearchContext:
        """Execute this stage, mutating context."""
        ...


class IPipeline(ABC):
    @abstractmethod
    async def run(self, query: str, level: ResearchLevel) -> ResearchContext:
        """Execute full pipeline at given level."""
        ...
```

### 2.3 Knowledge Store Interface

```python
@dataclass
class Entity:
    id: str
    type: str
    name: str
    properties: dict
    valid_from: str
    valid_until: str | None
    source_ids: list[str]
    confidence: str


@dataclass
class Relation:
    id: str
    subject_id: str
    predicate: str
    object_id: str
    valid_from: str
    valid_until: str | None
    confidence: str
    source_ids: list[str]


class IKnowledgeStore(ABC):
    @abstractmethod
    async def upsert_entity(self, entity: Entity) -> str: ...
    @abstractmethod
    async def upsert_relation(self, rel: Relation) -> str: ...
    @abstractmethod
    async def get_entity(self, id: str) -> Entity | None: ...
    @abstractmethod
    async def search(self, query: str, mode: str) -> list[dict]: ...
    @abstractmethod
    async def get_timeline(self, entity_id: str, from_dt: str, to_dt: str) -> list[dict]: ...
    @abstractmethod
    async def get_contradictions(self, entity_id: str) -> list[dict]: ...
```

### 2.4 Search Engine Interface

```python
@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str  # searxng|exa|scholar|arxiv|metaso|ddg
    full_text: str | None
    published_date: str | None
    rank_score: float


class ISearchEngine(ABC):
    @abstractmethod
    async def search(self, query: str, backends: list[str], max_results: int = 10) -> list[SearchResult]:
        """Search across specified backends, deduplicate, RRF fuse."""
        ...

    @abstractmethod
    async def extract_content(self, url: str) -> str:
        """Extract clean text from URL."""
        ...
```

### 2.5 Executor Interface

```python
@dataclass
class ResearchTask:
    id: str
    query: str
    mode: str  # immediate|scheduled|watch
    level: str
    max_cost: float
    cron_expr: str | None = None
    topic: str | None = None
    sources: list[str] | None = None
    check_interval: str | None = None


@dataclass
class ResearchResult:
    task_id: str
    context: ResearchContext
    summary: str
    report_path: str
    cost: float
    completed_at: str


class IExecutor(ABC):
    @abstractmethod
    async def execute_now(self, task: ResearchTask) -> ResearchResult: ...
    @abstractmethod
    async def schedule(self, task: ResearchTask) -> str: ...  # returns task_id
    @abstractmethod
    async def watch(self, task: ResearchTask) -> str: ...  # returns task_id
    @abstractmethod
    async def cancel(self, task_id: str) -> bool: ...
    @abstractmethod
    async def get_status(self, task_id: str) -> dict: ...
    @abstractmethod
    async def list_tasks(self, mode: str | None = None) -> list[dict]: ...
```

## 3. Data Flow

### 3.1 Immediate Research Flow

```
User/Agent
    │ research_now(query="What is MoE?")
    ▼
MCP Server
    │ deserialize, validate
    ▼
Executor.execute_now()
    │ create ResearchTask(mode=immediate)
    ▼
TriageRouter.classify(query)
    │ → TriageResult(level=L2, cost_estimate=0.30, ...)
    ▼
CostGuard.check(0.30)
    │ ✓ under budget
    ▼
Pipeline.run(query, L2)
    │
    ├── L2DecomposeStage:
    │   Qwen3.6-35B decomposes into sub-questions
    │
    ├── MultiSourceSearchStage:
    │   Parallel: SearXNG + Exa + Semantic Scholar
    │   Deduplicate by URL → 25 unique results
    │
    ├── EntityStage:
    │   spaCy NER on each result snippet
    │   Low-confidence entities → Qwen3.6 confirmation
    │   Upsert to KnowledgeStore
    │
    ├── DeepReadStage:
    │   Jina Reader extracts full text from top 15
    │   V4-Flash 1M ctx: cross-analyze all 15 documents
    │
    ├── CrossAnalyzeStage:
    │   R1-70B: find contradictions, consensus, gaps
    │   Update KnowledgeStore with new relations
    │
    ├── QualityGateStage:
    │   Check: every claim has source?
    │   Check: any contradiction found?
    │   Check: any "studies show" without citation?
    │   Fail → retry DeepRead with broader sources
    │
    └── OutputStage:
        Qwen3.5-122B: structured report
        NotebookLM: create mind map + audio overview (optional)
        Write to ~/knowledge/reports/
        Update knowledge base with new entities/relations
    │
    ▼
ResearchResult { report_path, summary, cost=0.28 }
    │
    ▼
MCP Response → Agent/User
```

## 4. Degradation Paths

Each Tier 2 component has a concrete Tier 1 fallback:

| Component | Tier 2 (Full) | Tier 1 (Degraded) | Impact |
|-----------|---------------|-------------------|--------|
| Graph DB | Neo4j + Graphiti | SQLite RECURSIVE CTE | No graph traversal queries |
| Temporal Reasoning | Semantica Allen Algebra | SQL valid_from/until WHERE clauses | No interval algebra |
| Ontology Validation | Semantica SHACL | YAML schema + Python checks | Manual schema enforcement |
| Semantic Search | Exa API | SearXNG (keyword) | No embedding-based discovery |
| Content Extraction | Jina Reader | BeautifulSoup + readability | Lower extraction quality |
| Creative Output | NotebookLM | Qwen3.5-122B text generation | No mind maps/audio |
| Chinese Search | 秘塔AI搜索 | SearXNG (Google/Bing backends) | Less Chinese coverage |

## 5. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| MCP as only integration protocol | Agent-agnostic, industry standard, already adopted by Claude Code/Codex/Cursor |
| Super Tools (5) vs many tools (15+) | Dropbox Dash verified: tool definitions consume context, Super Tools reduce overhead |
| spaCy NLP for entity extraction by default | KGGPT verified: NLP 100-1000x cheaper than LLM for basic NER; LLM only for low-confidence cases |
| SQLite as primary store | Zero ops, embedded, FTS5 for full-text, RECURSIVE CTE for graph queries <100K entities |
| LanceDB for vectors | Embedded, columnar, faster than ChromaDB, file-based |
| Markdown + Git for source files | Karpathy LLM Wiki verified: plain text, version control, Obsidian compatible |
| Async Python throughout | Non-blocking for multi-source parallel search; same paradigm as SharedBrain |
| Cost guard as separate component | Single responsibility, easy to disable for local-only users |
