"""cockpit.commands.docs — CLI reference documentation generator (BET-Y1Q4-T8-16).

Generates standard, comprehensive GitHub Markdown CLI reference manual (docs/CLI-REFERENCE.md),
covering the 8 orthogonal domains, global flags, exit codes, telemetry, and shell completion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from cockpit import __version__
from cockpit.domain.exit_codes import ExitCode
from cockpit.commands.registry import (
    ORTHOGONAL_DOMAINS,
    LEGACY_COMMAND_MAPPING,
    COMMAND_CATALOG,
    CATEGORY_GROUPS,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_OUTPUT_PATH = WORKSPACE_ROOT / "docs" / "CLI-REFERENCE.md"


def generate_cli_reference_markdown() -> str:
    """Generate comprehensive Markdown documentation from active registry and parser."""
    md = []

    # Title & Metadata Header
    md.append("# Cockpit CLI Reference Manual")
    md.append("")
    md.append(f"> **Version**: v{__version__} | **Standard**: Tier-1 Open Source CLI Specification (gh / kubectl compatible)")
    md.append("> **Generated**: Automatic via `cockpit docs export`")
    md.append("")
    md.append("---")
    md.append("")

    # Table of Contents
    md.append("## Table of Contents")
    md.append("1. [Global Flags & Universal Contract](#1-global-flags--universal-contract)")
    md.append("2. [Standard Exit Codes](#2-standard-exit-codes)")
    md.append("3. [The 8 Orthogonal Domains (Dual-Track Architecture)](#3-the-8-orthogonal-domains-dual-track-architecture)")
    md.append("4. [Command Catalog](#4-command-catalog)")
    md.append("5. [Observability & Prometheus Telemetry](#5-observability--prometheus-telemetry)")
    md.append("6. [Shell Auto-completion](#6-shell-auto-completion)")
    md.append("")
    md.append("---")
    md.append("")

    # Section 1: Global Flags
    md.append("## 1. Global Flags & Universal Contract")
    md.append("Cockpit implements universal flags across all subcommands. Output purity is strictly guaranteed: `--json` guarantees 100% pure JSON without ANSI color escape codes.")
    md.append("")
    md.append("| Flag | Alias | Description | Output Mode |")
    md.append("| :--- | :--- | :--- | :--- |")
    md.append("| `--help` | `-h` | Display contextual help and subcommands | Text |")
    md.append("| `--version` | `-V` | Print version string with <40ms fast-path | Text |")
    md.append("| `--json` | - | Output pure structured JSON (disables Rich ANSI) | JSON |")
    md.append("| `--dry-run` | - | Preflight check without side effects or disk writes | JSON / Text |")
    md.append("| `--quiet` | `-q` | Suppress non-essential informational banners | Quiet |")
    md.append("| `--verbose` | `-v` | Output execution trace and diagnostic details | Verbose |")
    md.append("| `--output` | `-o` | Select format: `text`, `json`, `tui`, `markdown` | Formatted |")
    md.append("| `--trace-id` | - | Explicit distributed trace ID for OpenTelemetry/Langfuse | - |")
    md.append("")
    md.append("---")
    md.append("")

    # Section 2: Standard Exit Codes
    md.append("## 2. Standard Exit Codes")
    md.append("All cockpit commands return POSIX-compliant exit codes according to the `ExitCode` contract:")
    md.append("")
    md.append("| Code | Name | Semantic Description |")
    md.append("| :---: | :--- | :--- |")
    md.append("| `0` | `SUCCESS` | Normal execution completed successfully |")
    md.append("| `1` | `GENERAL_FAILURE` | Assertion failed or general business logic error |")
    md.append("| `2` | `USAGE_ERROR` | Command-line argument error, invalid choice, typo |")
    md.append("| `3` | `PERMISSION_DENIED` | Authentication failure or RBAC domain restriction |")
    md.append("| `4` | `RESOURCE_NOT_FOUND` | Target resource, task, or file not found |")
    md.append("| `5` | `UPSTREAM_ERROR` | Downstream service timeout, circuit breaker open, or unreachable |")
    md.append("")
    md.append("---")
    md.append("")

    # Section 3: 8 Orthogonal Domains
    md.append("## 3. The 8 Orthogonal Domains (Dual-Track Architecture)")
    md.append("Commands are organized into 8 orthogonal top-level domains. Both hierarchical calls (`cockpit <domain> <subcommand>`) and legacy flat calls (`cockpit <subcommand>`) are 100% equivalent and supported.")
    md.append("")
    md.append("| Domain | Icon | Description | Core Subcommands | Example |")
    md.append("| :--- | :---: | :--- | :--- | :--- |")

    domain_subs: dict[str, list[str]] = {d: [] for d in ORTHOGONAL_DOMAINS}
    for cmd, (d, _) in LEGACY_COMMAND_MAPPING.items():
        if d in domain_subs:
            domain_subs[d].append(cmd)

    for dom, desc in ORTHOGONAL_DOMAINS.items():
        subs = sorted(domain_subs.get(dom, []))
        subs_preview = ", ".join(f"`{s}`" for s in subs[:6])
        if len(subs) > 6:
            subs_preview += f" (+{len(subs)-6} more)"
        ex = f"`cockpit {dom} {subs[0]}`" if subs else f"`cockpit {dom}`"
        md.append(f"| `{dom}` | {desc.split()[0]} | {desc} | {subs_preview} | {ex} |")

    md.append("")
    md.append("---")
    md.append("")

    # Section 4: Command Catalog
    md.append("## 4. Command Catalog")
    md.append("Complete inventory of supported subcommands grouped by category:")
    md.append("")

    by_category: dict[str, list[tuple[str, Any]]] = {}
    for cmd_name, meta in sorted(COMMAND_CATALOG.items()):
        cat = meta.category or "🔧 通用 (General)"
        by_category.setdefault(cat, []).append((cmd_name, meta))

    for cat_name, _ in sorted(CATEGORY_GROUPS.items(), key=lambda x: x[1][0]):
        cmds = by_category.get(cat_name, [])
        if not cmds:
            continue
        md.append(f"### {cat_name}")
        md.append("")
        md.append("| Subcommand | Summary | Example Usage |")
        md.append("| :--- | :--- | :--- |")
        for name, meta in cmds:
            summary = meta.summary or "-"
            example = f"`cockpit {name}`"
            md.append(f"| `{name}` | {summary} | {example} |")
        md.append("")

    md.append("---")
    md.append("")

    # Section 5: Telemetry & Prometheus
    md.append("## 5. Observability & Prometheus Telemetry")
    md.append("Cockpit tracks command execution latency, counts, and error rates using an atomic local ring buffer (`~/.workspace/telemetry/cockpit_metrics.json`) with zero external daemon requirements.")
    md.append("")
    md.append("```bash")
    md.append("# View telemetry summary table")
    md.append("cockpit telemetry")
    md.append("")
    md.append("# Export standard Prometheus exposition text")
    md.append("cockpit telemetry export")
    md.append("")
    md.append("# Export structured JSON")
    md.append("cockpit telemetry --json")
    md.append("```")
    md.append("")
    md.append("---")
    md.append("")

    # Section 6: Shell Completion
    md.append("## 6. Shell Auto-completion")
    md.append("Cockpit generates native auto-completion scripts for Bash, Zsh, and Fish shells.")
    md.append("")
    md.append("### Bash")
    md.append("```bash")
    md.append("source <(cockpit completion bash)")
    md.append("# Persist to ~/.bashrc:")
    md.append("cockpit completion bash > ~/.cockpit-completion.bash")
    md.append("echo 'source ~/.cockpit-completion.bash' >> ~/.bashrc")
    md.append("```")
    md.append("")
    md.append("### Zsh")
    md.append("```zsh")
    md.append("# Add to fpath or source directly:")
    md.append("source <(cockpit completion zsh)")
    md.append("```")
    md.append("")
    md.append("### Fish")
    md.append("```fish")
    md.append("cockpit completion fish > ~/.config/fish/completions/cockpit.fish")
    md.append("```")
    md.append("")

    return "\n".join(md) + "\n"


def cmd_docs(args: argparse.Namespace) -> int:
    """CLI entrypoint for `cockpit docs`."""
    action = getattr(args, "docs_action", "export") or "export"
    is_json = getattr(args, "json", False)
    is_dry_run = getattr(args, "dry_run", False)
    output_path = Path(getattr(args, "output", None) or DEFAULT_OUTPUT_PATH)

    content = generate_cli_reference_markdown()

    if action == "show":
        if is_json:
            print(json.dumps({"markdown": content, "lines": len(content.splitlines())}, ensure_ascii=False))
        else:
            print(content, end="")
        return int(ExitCode.SUCCESS)

    # Action: export (write to disk)
    if is_dry_run:
        if is_json:
            print(json.dumps({
                "dry_run": True,
                "target_file": str(output_path),
                "bytes_to_write": len(content.encode("utf-8")),
                "ready": True,
            }))
        else:
            print(f"[DRY-RUN] 预检: 即将向 {output_path} 写入 {len(content.encode('utf-8'))} 字节的参考手册。")
        return int(ExitCode.SUCCESS)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        if is_json:
            print(json.dumps({
                "ok": True,
                "target_file": str(output_path),
                "bytes_written": len(content.encode("utf-8")),
                "lines": len(content.splitlines()),
            }))
        else:
            print(f"✓ 已成功生成 CLI 参考手册: {output_path} ({len(content.splitlines())} 行)")
        return int(ExitCode.SUCCESS)
    except Exception as e:
        if is_json:
            print(json.dumps({
                "ok": False,
                "error": str(e),
                "exit_code": int(ExitCode.GENERAL_FAILURE),
            }))
        else:
            print(f"❌ 写入参考手册失败: {e}", file=sys.stderr)
        return int(ExitCode.GENERAL_FAILURE)
