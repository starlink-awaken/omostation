"""Help/discover SSOT: catalog top-level names ⊆ CLI parsers; discover uses help_map."""

from __future__ import annotations

import argparse
from io import StringIO

from rich.console import Console

from cockpit.commands.discover import _cmd_discover
from cockpit.commands.help_map import (
    GROUPS,
    all_command_names,
    render_discover_map,
    top_level_cli_names_from_source,
)


def test_catalog_commands_are_registered_in_cli():
    """Every help_map catalog name must be registered (cli.py/_subcommands.py 源码或委派组).

    Phase B 起薄委派命令经组模块运行时注册 (delegation.register_all → add_parser),
    源码 regex 集合并入 delegation 派生键集; 不变量意图不变: catalog ⊆ 实际注册。
    """
    from cockpit.commands.delegation import ensure_delegated_catalog

    catalog = set(all_command_names())
    registered = top_level_cli_names_from_source()
    registered |= set(ensure_delegated_catalog().keys())  # 委派组模块派生键集 (同源)
    missing = sorted(catalog - registered)
    assert not missing, f"help_map catalog lists commands not registered as sub.add_parser in cli.py: {missing}"
    # Sanity: memory must be in both
    assert "memory" in catalog
    assert "memory" in registered


def test_groups_nonempty_and_include_memory_group():
    titles = [t for t, _, _ in GROUPS]
    assert any("记忆" in t or "Memory" in t for t in titles) or any(
        r.name == "memory" for _, _, rows in GROUPS for r in rows
    )
    assert any(r.name == "memory" for _, _, rows in GROUPS for r in rows)


def test_discover_renders_shared_catalog_and_memory():
    """discover must mention Memory OS and use shared catalog (not the old 39/6 fixed list)."""
    buf = StringIO()
    c = Console(file=buf, force_terminal=True, width=120, record=False)
    render_discover_map(c)
    text = buf.getvalue()
    assert "Memory OS" in text or "memory" in text.lower()
    assert "help_map" in text or "同源" in text or "cockpit help" in text
    # Old fixed copy must not be the sole map — look for a catalog command only in GROUPS
    assert "swarm" in text or "agent-onboard" in text or "knowledge" in text
    # Explicitly reject the outdated "39 个, 分 6 组" string if someone reverts discover
    out = StringIO()
    _c2 = Console(file=out, force_terminal=True, width=120)
    # Full discover command path
    # Patch Console used inside _cmd_discover
    import cockpit.commands.discover as disc

    class _C(Console):
        def __init__(self, *a, **k):
            super().__init__(file=out, force_terminal=True, width=120)

    orig = disc.Console
    disc.Console = _C  # type: ignore[misc, assignment]
    try:
        code = _cmd_discover(argparse.Namespace())
    finally:
        disc.Console = orig  # type: ignore[misc]
    full = out.getvalue()
    assert code == 0
    assert "39 个, 分 6 组" not in full
    assert "memory" in full.lower()
    assert "Memory OS" in full or "memory/" in full
