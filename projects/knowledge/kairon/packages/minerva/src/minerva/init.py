"""Shared initialization — factory functions for executor and components.

Replaces the triple-duplicated init pattern in daemon, MCP server, and web app.
All three now call ``create_default_executor()`` instead of copy-pasting
the same 30-line initialization sequence.
"""

from __future__ import annotations

from minerva.config import MinervaConfig
from minerva.executor.executor import CostGuard, ResearchExecutor
from minerva.knowledge.store import SQLiteKnowledgeStore
from minerva.llm.client import OpenAICompatibleClient
from minerva.pipeline.engine import create_default_pipeline
from minerva.search.engine import SearchEngine
from minerva.triage.router import TriageRouter


def create_default_executor(
    config_path: str | None = None,
    kos_save_enabled: bool = False,
    immune_audit_enabled: bool = False,
) -> ResearchExecutor:
    """Create a fully initialized ResearchExecutor with default components.

    Loads config, instantiates LLM client, search engine, pipeline, triage
    router, knowledge store, and cost guard into a ready-to-run executor.

    Args:
        config_path: Optional custom config path (default: MinervaConfig.load())
        kos_save_enabled: Append KOSSaveStage to pipeline stages.
        immune_audit_enabled: Insert ImmuneAuditStage before quality gate.

    Returns:
        Configured ResearchExecutor with research/search/ingest capabilities.
    """
    config = MinervaConfig.load(config_path)

    llm = OpenAICompatibleClient(
        base_url=config.llm.base_url,
        model=config.llm.models["agent"],
    )
    search = SearchEngine(
        {
            "searxng_url": config.search.searxng_url,
            "metaso_api_key": config.search.metaso_api_key,
            "exa_api_key": config.search.exa_api_key,
            "zhipu_api_key": getattr(config.search, "zhipu_api_key", ""),
        }
    )

    # Load spaCy NLP pipelines if available
    nlp = None
    nlp_zh = None
    try:
        import spacy

        nlp = spacy.load(config.nlp.spacy_model)
    except Exception:
        pass
    try:
        import spacy

        nlp_zh = spacy.load(config.nlp.spacy_model_zh)
    except Exception:
        pass

    pipeline = create_default_pipeline(
        llm,
        search,
        nlp,
        None,
        nlp_pipeline_zh=nlp_zh,
        kos_save_enabled=kos_save_enabled,
        immune_audit_enabled=immune_audit_enabled,
    )
    triage = TriageRouter(llm)
    kb = SQLiteKnowledgeStore()
    cost_guard = CostGuard(monthly_budget=config.execution.monthly_budget_usd)

    return ResearchExecutor(
        triage_router=triage,
        pipeline=pipeline,
        knowledge_store=kb,
        cost_guard=cost_guard,
        state_dir=config.state_dir,
    )
