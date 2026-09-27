"""CR-LLM-GATEWAY-ONLY 检查器: 严格规则(裸运行时推理端点 / `ollama run`)与扫描范围。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_llm_gateway_only",
    Path(__file__).resolve().parents[2] / "bin" / "gac" / "check-llm-gateway-only.py",
)
assert _SPEC and _SPEC.loader
guard = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(guard)


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "ROOT", tmp_path)
    return tmp_path


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _files(findings: list[dict]) -> set[str]:
    return {f["file"] for f in findings}


def test_env_default_pointing_at_raw_runtime_is_flagged(root):
    # .get(默认值) 原本整行豁免; 默认值本身指向裸运行时推理端点 = 默认绕过网关
    _write(root, "projects/demo/src/demo/a.py", 'URL = os.environ.get("X", "http://localhost:11434/api/generate")\n')
    _write(root, "projects/demo/src/demo/b.py", 'base_url=cfg.get("base_url", "http://localhost:1234/v1"),\n')
    assert _files(guard.scan()) == {"projects/demo/src/demo/a.py", "projects/demo/src/demo/b.py"}


def test_ollama_run_subprocess_is_flagged(root):
    _write(root, "projects/demo/src/demo/c.py", 'subprocess.run(["ollama", "run", model, prompt])\n')
    assert _files(guard.scan()) == {"projects/demo/src/demo/c.py"}


def test_nested_monorepo_packages_and_bin_are_scanned(root):
    _write(
        root,
        "projects/knowledge/kairon/packages/kronos/src/kronos/x.py",
        'requests.post("http://127.0.0.1:8000/v1/chat/completions")\n',
    )
    _write(root, "bin/tool.py", 'httpx.post("http://localhost:11434/api/chat")\n')
    assert _files(guard.scan()) == {
        "projects/knowledge/kairon/packages/kronos/src/kronos/x.py",
        "bin/tool.py",
    }


def test_comments_health_probes_and_archive_are_not_flagged(root):
    _write(root, "projects/demo/src/demo/d.py", "# 旧实现直连 http://localhost:11434/api/generate, 已迁到网关\n")
    _write(root, "projects/demo/src/demo/e.py", 'httpx.get("http://localhost:11434/api/tags")\n')
    _write(root, "bin/_archive/old.py", 'subprocess.run(["ollama", "run", m, p])\n')
    _write(root, "projects/demo/src/demo/f.py", 'httpx.get("http://127.0.0.1:8000/api/status")\n')
    assert guard.scan() == []


def test_runtime_control_plane_is_allowed(root):
    _write(root, "projects/omlxc/src/omlxc/adapter.py", 'httpx.post("http://127.0.0.1:1234/v1/chat/completions")\n')
    assert guard.scan() == []
