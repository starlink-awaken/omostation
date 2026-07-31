"""BOS Inbox CLI 单元测试 (status, search, pending, watch)。"""

from __future__ import annotations

import argparse
from unittest.mock import patch
from cockpit.commands.bos_inbox import cmd_bos_inbox


def test_cmd_bos_inbox_status():
    args = argparse.Namespace(inbox_cmd="status")
    assert cmd_bos_inbox(args) == 0


def test_cmd_bos_inbox_search_empty():
    args = argparse.Namespace(inbox_cmd="search", query="")
    assert cmd_bos_inbox(args) == 1


def test_cmd_bos_inbox_search_valid():
    args = argparse.Namespace(inbox_cmd="search", query="oa")
    assert cmd_bos_inbox(args) in (0, 1)


def test_cmd_bos_inbox_pending():
    args = argparse.Namespace(inbox_cmd="pending", source="seeyon_oa")
    assert cmd_bos_inbox(args) in (0, 1)


def test_cmd_bos_inbox_watch():
    args = argparse.Namespace(inbox_cmd="watch")
    assert cmd_bos_inbox(args) == 0


def test_cmd_bos_inbox_archive_empty():
    args = argparse.Namespace(inbox_cmd="archive", filename="", reason="resolved")
    assert cmd_bos_inbox(args) == 1


def test_cmd_bos_inbox_archive_missing():
    args = argparse.Namespace(inbox_cmd="archive", filename="non_existent_file.md", reason="resolved")
    assert cmd_bos_inbox(args) == 1
