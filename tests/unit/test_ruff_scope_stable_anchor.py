"""ruff scope 判据必须锚在 ruff-lint job 内，不是全文第一个 `src:`。

缺陷（2026-11-11 自证）：`check-ruff-scope-stable.py` 的自述是「查找 **ruff-lint
job 中**的 src 参数」，实现却是 `re.search(r'^\\s+src:...', text, re.MULTILINE)`
在**整个 quality.yml** 上取首个匹配。今天该文件只有一处 `src:`（恰好就在
ruff-lint 里）所以读数正确，但判据并未锚定 —— 将来任何 job 只要在 ruff-lint
之前加一行 `src:`，本检查就会静默改判那一行，而 ruff-lint 的真实 scope 漂移
将不再被看见（`check-ruff-scope-stable` 正是为防「X-Plane 意外扩展 ruff 检查面」
而设）。

判据：先切出 `  ruff-lint:` 的 job 块，再在块内找 `src:`。
"""

from __future__ import annotations

import importlib.util
import io
import contextlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-ruff-scope-stable.py"

GOOD = 'src: "projects/omo/src projects/ecos/src"'


def _load():
    spec = importlib.util.spec_from_file_location("ruff_scope_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _run(monkeypatch, tmp_path: Path, body: str) -> tuple[int, str]:
    wf = tmp_path / "quality.yml"
    wf.write_text(body, encoding="utf-8")
    monkeypatch.setattr(MODULE, "WORKFLOW", wf)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = MODULE.main()
    return rc, buf.getvalue()


def test_scope_is_read_from_ruff_lint_job(monkeypatch, tmp_path) -> None:
    body = (
        f"jobs:\n  ruff-lint:\n    steps:\n      - with:\n          {GOOD}\n  prettier:\n    runs-on: ubuntu-latest\n"
    )
    rc, out = _run(monkeypatch, tmp_path, body)
    assert rc == 0, out
    assert "projects/omo/src" in out


def test_src_outside_ruff_lint_job_is_ignored(monkeypatch, tmp_path) -> None:
    """别的 job 里更早出现的 `src: "."` 不得被当成 ruff scope（那是无界值, 会 FAIL）。"""
    body = (
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - with:\n"
        '          src: "."\n'
        "  ruff-lint:\n"
        "    steps:\n"
        "      - with:\n"
        f"          {GOOD}\n"
        "  prettier:\n"
        "    runs-on: ubuntu-latest\n"
    )
    rc, out = _run(monkeypatch, tmp_path, body)
    assert rc == 0, f"锚到了 ruff-lint 之外的 src: {out}"
    assert "projects/omo/src" in out


def test_missing_ruff_lint_job_fails(monkeypatch, tmp_path) -> None:
    rc, out = _run(monkeypatch, tmp_path, "jobs:\n  prettier:\n    runs-on: ubuntu-latest\n")
    assert rc == 1, out


def test_missing_src_in_ruff_lint_job_fails(monkeypatch, tmp_path) -> None:
    body = "jobs:\n  ruff-lint:\n    runs-on: ubuntu-latest\n  prettier:\n    runs-on: ubuntu-latest\n"
    rc, out = _run(monkeypatch, tmp_path, body)
    assert rc == 1, out


def test_unbounded_scope_fails(monkeypatch, tmp_path) -> None:
    rc, out = _run(monkeypatch, tmp_path, 'jobs:\n  ruff-lint:\n    src: "."\n')
    assert rc == 1, out
    assert "无界值" in out
