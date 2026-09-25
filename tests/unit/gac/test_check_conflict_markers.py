"""check-conflict-markers 回归测试.

对应 2026-09-25 事故: staged 二进制文件 (.pyc/sqlite-wal) 使
`git show :<path>` 的严格 UTF-8 解码抛 UnicodeDecodeError (非
CalledProcessError, 未被捕获), hook 以 traceback 失败并阻断无关提交。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _load():
    spec = importlib.util.spec_from_file_location("ccm", ROOT / "bin" / "gac" / "check-conflict-markers.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ccm"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_run_text_tolerates_non_utf8():
    """二进制输出不得抛 UnicodeDecodeError (事故根因)."""
    mod = _load()
    out = mod._run_text([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'\\xef\\x28\\n')"])
    assert "\udffd" in out or "\ufffd" in out  # replace 占位, 不抛错即过


def test_scan_ignores_replacement_chars():
    mod = _load()
    assert mod._scan("binary \ufffd\udffd garbage\nno markers here\n") == []


def test_scan_still_catches_real_markers():
    mod = _load()
    hits = mod._scan("<<<<<<< HEAD\nfoo\n=======\nbar\n>>>>>>> main\n")
    kinds = {k for _, k in hits}
    assert {"head", "separator", "tail"} <= kinds


def test_scan_separator_alone_is_not_a_hit():
    mod = _load()
    assert mod._scan("a\n=======\nb\n") == []


def test_staged_blob_gitlink_returns_none_without_crash():
    """gitlink (`git show :path` 报 bad object) 返回 None, 不抛错."""
    mod = _load()
    assert mod._staged_blob("projects/aetherforge") is None


def test_script_entrypoint_clean_tree():
    """脚本主体在干净树可运行 (只读 git show, 可并行)."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "bin" / "gac" / "check-conflict-markers.py"), "--file", "README.md"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr[-500:]
