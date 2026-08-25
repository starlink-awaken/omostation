"""Test cockpit knowledge search direct in-process retrieval fallback."""

import argparse

from cockpit.commands.knowledge import cmd_knowledge_search


def test_cmd_knowledge_search_inprocess(capsys):
    """Verify cmd_knowledge_search succeeds even when KOS server is offline."""
    args = argparse.Namespace(query="良乡医院", limit=3)
    exit_code = cmd_knowledge_search(args)
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "知识复合体搜索" in captured.out or "Unified Hybrid" in captured.out
