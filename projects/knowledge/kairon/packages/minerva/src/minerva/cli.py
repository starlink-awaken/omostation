"""Minerva CLI — entry point for deep research commands."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

import httpx


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="minerva",
        description="Minerva — Local-First Deep Research System",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # init
    sub.add_parser("init", help="First-time setup wizard")

    # research
    r = sub.add_parser("research", help="Execute deep research")
    r.add_argument("query", nargs="?", help="Research question (or use --template)")
    r.add_argument("--json", action="store_true", help="JSON output")
    r.add_argument(
        "--level",
        default="auto",
        choices=["auto", "L0", "L1", "L2", "L3", "L4"],
        help="Pipeline level (default: auto)",
    )
    r.add_argument("--max-cost", type=float, default=1.0, help="Max cost in USD")
    r.add_argument("--to-kos", action="store_true", help="同时导出到 KOS")
    r.add_argument(
        "--template",
        choices=["competitor-analysis", "literature-review", "policy-audit"],
        help="Use a research template",
    )
    r.add_argument("--target", help="Template target (replaces {{target}}, {{topic}}, {{policy}} in template)")
    r.add_argument("--eidos-output", type=str, help="导出为 Eidos KnowledgeCard 的目录路径")
    r.add_argument("--pipeline-input", help="pipeline input file")
    r.add_argument("--pipeline-output", help="pipeline output file")
    r.add_argument("--vault-sink", action="store_true", help="开启 Vault 归档 (research → L4 Markdown)")

    # mcp
    sub.add_parser("mcp", help="Start MCP server for agent integration")

    # check
    sub.add_parser("check", help="Health check — verify all services are running")

    # daemon
    sub.add_parser("daemon", help="Start background daemon")

    # web
    sub.add_parser("web", help="Start FastAPI web server (http://localhost:8765)")

    # results
    results_p = sub.add_parser("results", help="Manage saved research results")
    results_sub = results_p.add_subparsers(dest="results_cmd")
    results_sub.add_parser("list", help="List all saved results")
    results_show = results_sub.add_parser("show", help="Show a saved result")
    results_show.add_argument("result_id", help="Result ID (from results list)")
    results_delete = results_sub.add_parser("delete", help="Delete a saved result")
    results_delete.add_argument("result_id", help="Result ID to delete")
    results_sub.add_parser("stats", help="Storage statistics")

    # audit
    audit_p = sub.add_parser("audit", help="View audit log")
    audit_p.add_argument("--limit", type=int, default=20, help="Number of entries")
    audit_p.add_argument("--action", default="", help="Filter by action")
    audit_p.add_argument("--json", action="store_true", help="JSON output")

    # maintenance
    mt = sub.add_parser("maintenance", help="Knowledge base maintenance — staleness, gaps, contradictions")
    mt.add_argument(
        "--action",
        default="all",
        choices=["all", "staleness", "gaps", "contradictions", "cleanup-temp"],
        help="Maintenance action to run (default: all)",
    )
    mt.add_argument(
        "--path",
        default=".",
        help="Cleanup root for maintenance actions that operate on local files (default: current directory)",
    )
    mt.add_argument(
        "--older-than-hours",
        type=int,
        default=24,
        help="Only remove MinerU temp outputs older than this many hours (default: 24)",
    )

    return parser


async def _run_research(args: Any) -> int:
    """Execute a research query."""
    from minerva.config import MinervaConfig
    from minerva.llm.client import OpenAICompatibleClient
    from minerva.pipeline.engine import create_default_pipeline
    from minerva.search.engine import SearchEngine
    from minerva.triage.router import ResearchLevel, TriageRouter
    from minerva.utils.terminal import (
        print_banner,
        print_pipeline_header,
        print_summary_table,
    )

    config = MinervaConfig.load()
    print_banner()
    llm = OpenAICompatibleClient(
        base_url=config.llm.base_url,
        model=config.llm.models["agent"],
    )
    # Cloud API Key 状态（信息提示，非阻塞）
    cloud_env = {
        "DeepSeek V4 Pro": "DEEPSEEK_API_KEY",
        "GLM (128K ctx)": "GLM_API_KEY",
        "LongCat (backup)": "LONGCAT_API_KEY",
    }
    available_cloud = [name for name, env in cloud_env.items() if os.environ.get(env)]
    if available_cloud:
        sys.stderr.write(f"[LLM] Cloud keys found: {', '.join(available_cloud)}\n")
    else:
        sys.stderr.write("[LLM] No cloud API keys — L3/L4 research unavailable\n")

    # Cloud reasoning — opencode-go (zen/go, 套餐内) primary, DeepSeek 官方 fallback
    cloud_llm = None
    _og_key_path = os.path.expanduser("~/.config/opencode/keys/opencodego-xiaweizhen.txt")
    _og_key = ""
    try:
        with open(_og_key_path) as _f:
            _og_key = _f.read().strip()
    except OSError:
        _og_key = ""
    if _og_key:
        cloud_llm = OpenAICompatibleClient(
            base_url="https://opencode.ai/zen/go/v1",
            api_key=_og_key,
            model="deepseek-v4-flash",
            timeout=180,
        )
    elif os.environ.get("DEEPSEEK_API_KEY"):
        cloud_llm = OpenAICompatibleClient(
            base_url=os.environ.get("AETHERFORGE_URL", "http://127.0.0.1:9290/v1"),
            api_key=os.environ["DEEPSEEK_API_KEY"],
            model="deepseek-v4-pro",
            timeout=180,
        )
    elif os.environ.get("LONGCAT_API_KEY"):
        cloud_llm = OpenAICompatibleClient(
            base_url="https://api.longcat.chat/openai",
            api_key=os.environ["LONGCAT_API_KEY"],
            model="LongCat-Flash-Thinking",
            timeout=180,
        )
    # 1M context for DeepRead — V4 Pro priority, GLM free fallback
    long_context = cloud_llm  # V4 Pro has 1M ctx
    if not long_context and os.environ.get("GLM_API_KEY"):
        long_context = OpenAICompatibleClient(
            base_url="https://open.bigmodel.cn/api/paas/v4",
            api_key=os.environ["GLM_API_KEY"],
            model="glm-4.7-flash",
            timeout=120,
        )
    search = SearchEngine(
        {
            "searxng_url": config.search.searxng_url,
            "metaso_api_key": config.search.metaso_api_key,
            "exa_api_key": config.search.exa_api_key,
            "zhipu_api_key": os.environ.get("ZHIPU_API_KEY", ""),
        }
    )

    # Load spaCy NLP pipelines for entity extraction
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

    # Template support: load template and interpolate {{variables}}
    if args.template and args.target:
        from pathlib import Path as _Path

        tpl_path = _Path(__file__).parent / "templates" / f"{args.template}.md"
        if tpl_path.exists():
            template_content = tpl_path.read_text()
            template_content = template_content.replace("{{target}}", args.target)
            template_content = template_content.replace("{{topic}}", args.target)
            template_content = template_content.replace("{{policy}}", args.target)
            print(f"Using template: {args.template} (target: {args.target})")
            if not args.query:
                args_query = template_content.split("\n")[0].lstrip("# ").strip()
                args = argparse.Namespace(**{**vars(args), "query": args_query})
            print(f"Template sub-questions loaded: {template_content.count('What ')} questions")

    level = ResearchLevel(args.level) if args.level != "auto" else None
    if level is None:
        router = TriageRouter(llm)
        triage = await router.classify(args.query)
        level = triage.level
        print(f"Auto-routed to {level.value} (cost est: ${triage.cost_estimate:.2f})")
        triage_obj = triage
    else:
        router = TriageRouter(llm)
        triage_obj = await router.classify(args.query)

    print_pipeline_header(args.query, level.value)

    # Research Paradigm — classify problem type → apply framework
    from minerva.paradigm.router import classify_paradigm
    from minerva.paradigm.types import PARADIGMS

    paradigm_result = await classify_paradigm(llm, args.query)
    paradigm_def = PARADIGMS[paradigm_result.paradigm]
    print(f"\n  [bold cyan]Paradigm:[/bold cyan] {paradigm_def.name} ({paradigm_result.confidence:.0%} confidence)")
    print(f"  [dim]Reasoning: {paradigm_result.reasoning}[/dim]")
    print(f"  [dim]Stages: {' → '.join(paradigm_def.stages)}[/dim]")
    print(f"  [dim]Verification: {paradigm_def.verification_mode.value.upper()}[/dim]")

    pipeline = create_default_pipeline(
        llm,
        search,
        nlp,
        None,
        nlp_pipeline_zh=nlp_zh,
        cloud_llm_client=cloud_llm,
        glm_llm_client=long_context,
        vault_sink_enabled=getattr(args, "vault_sink", False),
    )
    ctx = await pipeline.run(args.query, level, triage_obj)
    results = getattr(ctx, "search_results", []) or []

    if hasattr(args, "to_kos") and args.to_kos:
        from minerva.knowledge.eidos_adapter import (
            export_to_kos,
            research_result_to_card,
        )

        cards = []
        for r in results if isinstance(results, list) else [results]:
            card = research_result_to_card(r)
            if card:
                cards.append(card)
        if cards:
            kos_result = export_to_kos(cards)
            print(f"KOS export: {kos_result['status']} ({kos_result.get('count', 0)} cards)")

    if hasattr(args, "eidos_output") and args.eidos_output:
        try:
            from minerva.knowledge.eidos_adapter import (
                export_cards_to_json,
                research_result_to_card,
            )

            cards = []
            for result in results:
                card = research_result_to_card(result)
                if card:
                    cards.append(card)
            count = export_cards_to_json(cards, args.eidos_output)
            print(f"Exported {count} Eidos KnowledgeCards to {args.eidos_output}")
        except ImportError:
            print("Eidos not available. Install eidos or check PYTHONPATH")
        except Exception as e:
            print(f"Eidos export failed: {e}")

    if hasattr(args, "json") and args.json:
        import json

        print(json.dumps({"tool": "minerva", "command": "research", "data": results}, indent=2, ensure_ascii=False))
        return 0

    if ctx.report:
        quality_score: str = "N/A"
        zh_path = None
        for r in ctx.relations or []:
            if "quality_score" in r:
                quality_score = str(r["quality_score"])
            if "zh_report_path" in r:
                zh_path = r["zh_report_path"]
        print_summary_table(
            ctx.stage_timings,
            quality_score,
            len(ctx.search_results),
            len(ctx.entities),
            sum(ctx.stage_timings.values()),
        )
        print(ctx.report)
        print("\n[bold]Reports saved:[/bold]")
        print(f"  EN: {ctx.report_path}")
        if zh_path:
            print(f"  ZH: {zh_path}")
    else:
        print("Research completed but no report generated.")

    # -- Default persist: save research result to ~/.minerva/research/ --
    _result_id: str | None = None
    if hasattr(ctx, "report") and ctx.report:
        from minerva.persistence import save_research

        quality_val = quality_score if quality_score != "N/A" else 0  # type: ignore[reportPossiblyUnboundVariable]
        _result_id = save_research(
            query=args.query,
            level=level.value if hasattr(level, "value") else str(level),
            quality_score=quality_val,
            source_count=len(ctx.search_results) if hasattr(ctx, "search_results") else 0,
            entity_count=len(ctx.entities) if hasattr(ctx, "entities") else 0,
            cost_usd=0.0,  # minerva doesn't track cost in ctx yet
            elapsed_s=sum(ctx.stage_timings.values()) if hasattr(ctx, "stage_timings") else 0,
            paradigm_name=paradigm_def.name if "paradigm_def" in dir() else "",
            stage_timings=ctx.stage_timings if hasattr(ctx, "stage_timings") else {},
            report=ctx.report,
            report_path=ctx.report_path,
            search_results=results,
        )
        print(f"\n  [green]✓ Result saved:[/green] ~/.minerva/research/{_result_id}/")

        # -- P0-1 知识回流: 研究结果写回 kos 知识中枢 (markdown + Mem0 双写) --
        try:
            from kos.ingest import ingest_text

            _kos_title = f"[minerva] {args.query[:80]}"
            _kos_result = ingest_text(ctx.report, title=_kos_title)
            _kos_id = _kos_result.get("note_id") or _kos_result.get("id") or "?"
            print(f"  [blue]↳ 知识回流 kos: ✓ (note_id={_kos_id})[/blue]")
        except Exception as _kos_exc:
            # 降级: kos 不可用时静默跳过, 不阻塞研究主流程 (复用 llm-router 降级哲学)
            print(f"  [yellow]↳ 知识回流 kos 跳过: {_kos_exc}[/yellow]")

        # -- P1-2 统一记忆: 研究摘要写入 mos (Memory OS), 消除第三套存储 --
        try:
            from mos.service import MemoryOS

            _mos = MemoryOS()
            _mos.write(
                {
                    "type": "working",
                    "agent_profile": "minerva",
                    "content": f"[minerva] {args.query[:80]} — {ctx.report[:400]}",
                    "metadata": {"query": args.query, "kind": "research"},
                },
                role="agent",
            )
            print("  [blue]↳ 研究记忆写入 mos: ✓[/blue]")
        except Exception as _mos_exc:
            # 降级: mos 不可用时静默跳过
            print(f"  [yellow]↳ 研究记忆 mos 跳过: {_mos_exc}[/yellow]")

    quality_score = locals().get("quality_score", "N/A")
    # -- Audit log --
    from minerva.audit_store import log_operation

    log_operation(
        actor="cli",
        action="research.run",
        resource=args.query[:200],
        result="success",
        detail=f"level={level.value if hasattr(level, 'value') else level} "
        f"quality={quality_score}_entities={len(ctx.entities) if hasattr(ctx, 'entities') else 0}",
        duration_ms=sum(ctx.stage_timings.values()) * 1000 if hasattr(ctx, "stage_timings") else 0,
    )

    if hasattr(args, "pipeline_output") and args.pipeline_output:
        import json
        from pathlib import Path

        output = {
            "tool": "minerva",
            "action": "research",
            "results": results if isinstance(results, list) else [results],
        }
        Path(args.pipeline_output).write_text(json.dumps(output, indent=2, ensure_ascii=False))
        if not getattr(args, "verbose", False):
            return 0

    return 0


def _run_init() -> int:
    """First-time setup wizard."""
    import os
    from pathlib import Path as _Path

    print("\n  ⚡ Minerva — First-Time Setup\n")
    checks = []

    # 1. Ollama
    try:
        import httpx

        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"  ✅ Ollama running ({len(models)} models)")
            checks.append(("Ollama", True))
        else:
            raise Exception("not ok")
    except Exception:
        print("  ⚠️  Ollama not detected. Install: brew install ollama && ollama serve")
        checks.append(("Ollama", False))

    # 2. Config
    config_path = _Path(__file__).parent.parent.parent / "config" / "minerva.yaml"
    if config_path.exists():
        print(f"  ✅ Config found: {config_path}")
        checks.append(("Config", True))
    else:
        print(f"  ⚠️  Config not found at {config_path}")
        checks.append(("Config", False))

    # 3. Knowledge dirs
    for d in ["~/knowledge/reports", "~/minerva/state"]:
        _Path(d).expanduser().mkdir(parents=True, exist_ok=True)
    print("  ✅ Knowledge directories created")
    checks.append(("Storage", True))

    # 4. API keys
    keys = {
        "DEEPSEEK_API_KEY": "DeepSeek",
        "GLM_API_KEY": "GLM",
        "EXA_API_KEY": "Exa",
        "METASO_API_KEY": "Metaso",
    }
    for env, name in keys.items():
        if os.environ.get(env):
            print(f"  ✅ {name} API key configured")
        else:
            print(f"  ⚠️  {name} API key not set (optional)")

    # 5. spaCy
    try:
        import spacy

        spacy.load("en_core_web_lg")
        print("  ✅ spaCy en_core_web_lg available")
    except Exception:
        print("  ⚠️  spaCy model not found. Run: python -m spacy download en_core_web_lg")

    # Audit
    from minerva.audit_store import log_operation

    log_operation("cli", "init", "minerva", "success", f"{sum(1 for _, ok in checks if ok)}/{len(checks)} checks")

    print(f"\n  Setup complete. {sum(1 for _, ok in checks if ok)}/{len(checks)} checks passed.")
    print("  Run: minerva web    → start the dashboard")
    print('  Run: minerva research "your question" → test the pipeline\n')
    return 0


def _run_check() -> int:
    """Health check — verify all services and dependencies."""
    print("\n  ⚡ Minerva Health Check\n")
    passed = 0
    failed = 0

    # 1. Ollama
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            print(f"  ✅ Ollama running ({len(models)} models: {', '.join(models[:3])}...)")
            passed += 1
        else:
            raise Exception("not ok")
    except Exception:
        print("  ❌ Ollama not reachable (brew install ollama && ollama serve)")
        failed += 1

    # 2. SearXNG — prefer /health, fall back to / (upstream image often 404s /health)
    try:
        port = os.environ.get("ONTODERIVE_WEB_PORT", "8080")
        base = f"http://localhost:{port}"
        ok = False
        for path in ("/health", "/", "/search?q=ping&format=json"):
            try:
                r = httpx.get(f"{base}{path}", timeout=5)
            except Exception as exc:
                # Probe next endpoint; connection errors are expected when down.
                _ = exc
                continue
            if r.status_code == 200:
                ok = True
                break
        if ok:
            print(f"  ✅ SearXNG running (localhost:{port})")
            passed += 1
        else:
            raise Exception("not ok")
    except Exception:
        print("  ⚠️  SearXNG not running (docker compose up -d searxng)")
        failed += 1

    # 3. Neo4j
    try:
        password = os.environ.get("NEO4J_PASSWORD", "changeme")
        r = httpx.get("http://localhost:7474", auth=("neo4j", password), timeout=5)
        if r.status_code == 200:
            print("  ✅ Neo4j running (localhost:7474)")
            passed += 1
        else:
            raise Exception("not ok")
    except Exception:
        print("  ⚠️  Neo4j not running (docker compose --profile full up -d neo4j)")
        failed += 1

    # 4. Configuration
    keys_found = sum(
        1 for k in ["DEEPSEEK_API_KEY", "LONGCAT_API_KEY", "GLM_API_KEY", "EXA_API_KEY"] if os.environ.get(k)
    )
    if keys_found > 0:
        print(f"  ✅ API keys configured ({keys_found}/4)")
        passed += 1
    else:
        print("  ⚠️  No cloud API keys set (L0-L1 work locally, L2+ need keys)")
        failed += 1

    # 5. Python deps
    import importlib

    deps = {"spacy": "spaCy", "structlog": "structlog", "lancedb": "LanceDB", "httpx": "httpx"}
    for mod, name in deps.items():
        try:
            importlib.import_module(mod)
        except ImportError:
            print(f"  ❌ {name} not installed (pip install {mod})")
            failed += 1

    # 6. Storage
    from pathlib import Path

    db_path = Path.home() / "knowledge" / "minerva.db"
    if db_path.exists():
        print(f"  ✅ SQLite database ({db_path})")
        passed += 1
    else:
        print("  ℹ️  SQLite DB not yet created (auto-created on first use)")
        passed += 1

    total = passed + failed
    print(f"\n  Results: {passed}/{total} checks passed")
    if failed == 0:
        print("  🎉 All systems ready!")
    else:
        print(f"  {failed} issue(s) found. Run 'minerva init' for setup help.")

    # Audit
    from minerva.audit_store import log_operation

    log_operation(
        "cli", "check", "minerva:health", "success" if failed == 0 else "degraded", f"{passed}/{total} checks passed", 0
    )

    print()
    return 0 if failed == 0 else 1


def main() -> Any:
    print("⚠️ Minerva 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "init":
        return _run_init()
    elif args.command == "research":
        return asyncio.run(_run_research(args))
    elif args.command == "mcp":
        from minerva.mcp_server.server import main as mcp_main

        return mcp_main()
    elif args.command == "check":
        return _run_check()
    elif args.command == "web":
        import uvicorn

        from minerva.web.app import app

        print("Minerva Web → http://localhost:8765")
        uvicorn.run(app, host="127.0.0.1", port=8765, log_level=os.environ.get("MINERVA_LOG_LEVEL", "info"))
        return 0
    elif args.command == "daemon":
        from minerva.executor.daemon import main as daemon_main

        return daemon_main()
    elif args.command == "maintenance":
        return _run_maintenance(args)
    elif args.command == "results":
        return _run_results(args)
    elif args.command == "audit":
        return _run_audit(args)

    return 0


def _run_results(args: Any) -> int:
    """List/show/delete saved research results."""
    from minerva.persistence import (
        delete_result,
        get_result,
        get_storage_stats,
        list_results,
    )

    cmd = args.results_cmd

    if cmd == "list":
        results = list_results()
        if not results:
            print("No saved research results found.")
            return 0
        print(f"\n  Saved Research Results ({len(results)})\n")
        for r in results:
            has = "📄" if r.get("has_report") else "  "
            ts = r.get("timestamp", "?")[:19]
            quality = r.get("quality_score", "?")
            print(f"  {has} {r['id']}")
            print(f"      Q: {r['query'][:70]}")
            print(
                f"      {ts} | level={r.get('level', '?')} | quality={quality} | "
                f"sources={r.get('source_count', 0)} | ${r.get('cost_usd', 0):.2f}"
            )
            print()
        if args.json:
            import json

            print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    elif cmd == "show":
        result = get_result(args.result_id)
        if not result:
            print(f"Result '{args.result_id}' not found.")
            print("  Run 'minerva results list' to see available results.")
            return 1
        report = result.pop("report", "")
        result.pop("search_results", None)
        import json

        print(json.dumps(result, ensure_ascii=False, indent=2))
        if report:
            print(f"\n{'=' * 60}\nREPORT\n{'=' * 60}\n")
            print(report[:2000])
            if len(report) > 2000:
                print(f"\n... ({len(report) - 2000} more chars)")
        return 0

    elif cmd == "delete":
        if delete_result(args.result_id):
            print(f"Deleted: {args.result_id}")
            return 0
        else:
            print(f"Result '{args.result_id}' not found.")
            return 1

    elif cmd == "stats":
        stats = get_storage_stats()
        print("\n  Research Storage Stats")
        print(f"  Total results: {stats['total_results']}")
        print(f"  Total size:    {stats['total_size_mb']} MB")
        print(f"  Location:      {stats['storage_dir']}\n")
        if args.json:
            import json

            print(json.dumps(stats, indent=2))
        return 0

    return 0


def _run_audit(args: Any) -> int:
    """View audit log."""
    from minerva.audit_store import get_logger

    logger = get_logger()

    if args.json:
        import json

        entries = logger.query(
            limit=args.limit,
            action=args.action or None,
        )
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    else:
        entries = logger.query(limit=args.limit)
        if not entries:
            print("No audit entries found.")
            return 0
        print(f"\n  Audit Log ({len(entries)} entries)\n")
        for e in entries:
            print(f"  [{e['timestamp'][:19]}] {e['action']:25s} {e['result']:10s} | {e['resource'][:60]}")
        print(f"\n  Stats: {logger.stats()['total_entries']} total entries\n")
    return 0


def _run_maintenance(args: Any) -> int:
    """Run knowledge base maintenance."""

    from minerva.knowledge.mineru_adapter import cleanup_stale_mineru_outputs
    from minerva.maintenance.contradiction import detect_contradictions_rule_based
    from minerva.maintenance.gap_analyzer import get_improvement_suggestions
    from minerva.maintenance.staleness import StalenessChecker

    action = args.action
    report_dir = "~/knowledge/reports"

    if action in ("all", "staleness"):
        print("=== Staleness Check ===")
        checker = StalenessChecker(report_dir=report_dir)
        report = checker.scan()
        print(report.summary)
        if report.stale_entries:
            for e in report.stale_entries[:5]:
                print(f"  [{e.age_days}d] {e.title[:60]} — {e.reason[:80]}")

    if action in ("all", "gaps"):
        print("\n=== Gap Analysis ===")
        suggestions = get_improvement_suggestions(report_dir=report_dir)
        for s in suggestions:
            print(f"  - {s}")

    if action in ("all", "contradictions"):
        print("\n=== Contradiction Detection ===")
        from minerva.maintenance.contradiction import extract_claims

        all_entries = extract_claims(report_dir, limit=20)
        if all_entries:
            contradictions = detect_contradictions_rule_based(all_entries)
            print(f"Scanned {len(all_entries)} claims from reports.")
            if contradictions:
                print(f"Found {len(contradictions)} potential contradictions:")
                for c in contradictions[:5]:
                    print(f"  [{c.severity}] {c.claim_a[:50]} vs {c.claim_b[:50]}")
            else:
                print("No contradictions detected.")
        else:
            print("No claims found to analyze.")

    if action in ("all", "cleanup-temp"):
        print("\n=== MinerU Temp Cleanup ===")
        removed = cleanup_stale_mineru_outputs(args.path, older_than_hours=args.older_than_hours)
        print(f"Removed {removed} stale MinerU output directories from {args.path}.")

    print("\nMaintenance complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
