#!/usr/bin/env python3
# ruff: noqa
"""KOS CLI Help System."""

import sys

HELP = {
    "search": {
        "syntax": "kos search <query> [--domains X] [--limit N] [--web] [--templates]",
        "description": "Cross-domain full-text search across all indexed documents. Use --web for Minerva-powered web search.",
        "examples": [
            "kos search '信息化'",
            "kos search '考核方案' --domains gongwen",
            "kos search '发言稿' --templates",
            "kos search 'MoE架构' --web",
            "kos search '平台' --domains gongwen,guozhuan --limit 5",
            "kos search '数字化平台' --kind note --zone guozhuan",
        ],
        "flags": {
            "--domains": "Comma-separated domain filter (e.g. gongwen,obsidian)",
            "--zone": "Single zone filter",
            "--kind": "Filter by document kind (note, reference, index, etc.)",
            "--status": "Filter by document status (active, draft, archived, etc.)",
            "--limit": "Max results (default: 10)",
            "--web": "Search via Minerva web backends (8 engines, requires Minerva installed)",
            "--templates": "Include template/reference documents in search",
            "--format": "Output format: table (default), md (Markdown), json (raw)",
        },
    },
    "status": {
        "syntax": "kos status [--domain NAME]",
        "description": "Show system health overview: domain list, document counts, retrieval DB status.",
        "examples": ["kos status", "kos status --domain gongwen"],
    },
    "domains": {
        "syntax": "kos domains",
        "description": "List all registered knowledge domains with their zones and access policies.",
        "examples": ["kos domains"],
    },
    "index": {
        "syntax": "kos index [--incremental] [--domain NAME] [--jobs N]",
        "description": "Build or update the cross-domain retrieval index. Default: full rebuild. Use --incremental for daily updates.",
        "examples": [
            "kos index",
            "kos index --incremental",
            "kos index --domain gongwen --jobs 8",
        ],
        "flags": {
            "--incremental": "Only process changed files (SHA-256 fingerprint diff)",
            "--domain": "Index only the specified domain",
            "--jobs": "Number of parallel workers (default: 4)",
        },
    },
    "diff": {
        "syntax": "kos diff",
        "description": "Show files changed since the last index run. Useful before running incremental updates.",
        "examples": ["kos diff"],
    },
    "research": {
        "syntax": "kos research <query> [--level L0-L4] [--max-cost N]",
        "description": "Deep research powered by Minerva: 8 web search engines + 4 LLMs. Auto-routes to optimal pipeline level.",
        "examples": [
            "kos research 'transformer architecture'",
            "kos research '数字化平台最新政策' --level L2",
            "kos research 'AI safety both sides' --level L3 --max-cost 2.0",
        ],
        "flags": {
            "--level": "Pipeline level: auto/L0($0,30s)/L1($0,3min)/L2(~$0.30,10min)/L3(~$2,20min)/L4($5+)",
            "--max-cost": "Maximum cost in USD (default: 1.0)",
        },
    },
    "digest": {
        "syntax": "kos digest",
        "description": "Quick knowledge overview: per-domain document counts, entity stats, last index time.",
        "examples": ["kos digest"],
    },
    "report": {
        "syntax": "kos report",
        "description": "Generate a weekly knowledge activity report: recent documents, domain stats, entity count.",
        "examples": ["kos report"],
    },
    "related": {
        "syntax": "kos related <document_title_or_keyword>",
        "description": "Find documents related to a given document via shared entities and keyword overlap.",
        "examples": [
            "kos related '数字化平台'",
            "kos related 'CLAUDE.md'",
        ],
    },
    "onto": {
        "syntax": "kos onto <subcommand> [args]",
        "description": "Ontology operations — entity extraction, relation inference, knowledge graph.",
        "subcommands": {
            "extract": "kos onto extract",
            "card": "kos onto card <entity_id>",
            "path": "kos onto path <from_id> <to_id>",
            "discover": "kos onto discover",
            "graph": "kos onto graph [--type Person|Project|Organization]",
            "rebuild": "kos onto rebuild",
            "list": "kos onto list [--type Person]",
        },
        "examples": [
            "kos onto card P:xia-mingxing",
            "kos onto path P:xia-mingxing P:chai-hua",
            "kos onto rebuild",
            "kos onto graph --type Person",
        ],
    },
    "audit": {
        "syntax": "kos audit",
        "description": "Run quality audit: check for missing tags, stale reviews, unpromoted content.",
        "examples": ["kos audit"],
    },
    "staleness": {
        "syntax": "kos staleness",
        "description": "Check for stale content (>6 months canonical, >90 days ephemeral).",
        "examples": ["kos staleness"],
    },
    "contradict": {
        "syntax": "kos contradict",
        "description": "Cross-domain contradiction detection: find conflicting indicators across zones.",
        "examples": ["kos contradict"],
    },
    "suggest": {
        "syntax": "kos suggest",
        "description": "Generate auto-tag and link suggestions for untagged or orphan documents.",
        "examples": ["kos suggest"],
    },
    "all": {
        "syntax": "kos all",
        "description": "Run all maintenance checks: audit + staleness + contradict + suggest.",
        "examples": ["kos all"],
    },
    "discover": {
        "syntax": "kos discover",
        "description": "Cross-domain association discovery: find entities mentioned across multiple zones.",
        "examples": ["kos discover"],
    },
    "roles": {
        "syntax": "kos roles",
        "description": "Show KOS agent role assignments and routing rules.",
        "examples": ["kos roles"],
    },
    "onboard": {
        "syntax": "kos onboard <path> <name> [--identity ROLE]",
        "description": "Onboard a new domain: register in manifest + generate CLAUDE.md + auto-index.",
        "examples": [
            "kos onboard ~/NewProject 'Research' --identity 'Researcher'",
        ],
    },
    "init": {
        "syntax": "kos init",
        "description": "Initialize a new KOS workspace: auto-discover directories, generate manifest.",
        "examples": ["kos init"],
    },
}

CATEGORIES = {
    "Search & Browse": ["search", "status", "domains", "digest", "report", "related"],
    "Research (Minerva)": ["research"],
    "Indexing": ["index", "diff"],
    "Ontology": ["onto"],
    "Maintenance": ["audit", "staleness", "contradict", "suggest", "all"],
    "Domain Management": ["onboard", "init", "discover", "roles"],
}


def show_general() -> None:  # type: ignore[unknown]
    print("KOS — Knowledge Operating System CLI\n")
    print("Usage: kos <command> [args...]\n")
    for cat, cmds in CATEGORIES.items():
        print(f"  {cat}:")
        for c in cmds:
            info = HELP.get(c, {})
            desc = info.get("description", "")  # type: ignore[attr-defined]
            print(f"    {c:12s}  {desc}")
        print()


def show_command(cmd: str) -> None:
    info = HELP.get(cmd)
    if not info:
        print(f"Unknown command: {cmd}\nRun 'kos help' for available commands.")
        return
    print(f"KOS {cmd}\n")
    print(f"  {info['syntax']}")  # type: ignore[index]
    print(f"\n  {info['description']}\n")  # type: ignore[index]
    if "flags" in info:  # type: ignore[operator]
        print("  Options:")
        for flag, desc in info["flags"].items():  # type: ignore[index]
            print(f"    {flag:18s}  {desc}")
        print()
    if "subcommands" in info:  # type: ignore[operator]
        print("  Subcommands:")
        for sub, syn in info["subcommands"].items():  # type: ignore[index]
            print(f"    {sub:12s}  {syn}")
        print()
    if "examples" in info:  # type: ignore[operator]
        print("  Examples:")
        for ex in info["examples"]:  # type: ignore[index]
            print(f"    $ {ex}")
        print()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if not cmd:
        show_general()
    else:
        show_command(cmd)
