"""CR-X4-MESH-ROUTING-CONSISTENCY 的启发式必须只认代码, 不认字符串。

缺陷（2026-11-11 实测）：判据对**全文**跑 `route|dispatch|forward|send|publish`
正则，而 `bin/ssot/mesh-iris-executor.py` 把工作流生命周期状态名写在字符串里
（`"StepDispatched"`、seed 链 `"Requested→Admitted→Dispatched→Started"`）。
于是本机恒报一条 WARN —— 一个**纯工作流编排**文件被当成 mesh 路由文件，
advisory 长期噪音会教人忽略整条检查。

判据：把 docstring / 字符串常量 / 注释抹掉后再匹配；真正的路由调用是标识符
或调用表达式，不受影响。BOS URI 仍在字符串里，那条判据必须继续扫全文。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-mesh-routing-consistency.py"


def _load(monkeypatch, tmp_path: Path):
    spec = importlib.util.spec_from_loader(
        "mesh_routing_under_test",
        importlib.machinery.SourceFileLoader("mesh_routing_under_test", str(SCRIPT)),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(module, "MESH_DIRS", ["bin/mesh", "bin/ssot"])
    (tmp_path / "bin" / "mesh").mkdir(parents=True, exist_ok=True)
    (tmp_path / "bin" / "ssot").mkdir(parents=True, exist_ok=True)
    return module


def _write(tmp_path: Path, rel: str, text: str) -> None:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_string_state_names_are_not_routing(capsys, monkeypatch, tmp_path) -> None:
    """工作流状态名只出现在字符串里 ⇒ 不得报「包含路由逻辑」。"""
    _write(tmp_path, "bin/ssot/mesh-iris-executor.py", '''\
"""executor."""
STATE = "StepDispatched"
CHAIN = "Requested→Admitted→Dispatched→Started"
try:
    pass
except Exception:
    pass
''')
    module = _load(monkeypatch, tmp_path)

    assert module.main() == 0
    out = capsys.readouterr().out
    assert "WARN" not in out, f"纯字符串状态名被误判成路由: {out}"


def test_real_routing_code_is_still_detected(capsys, monkeypatch, tmp_path) -> None:
    """反例保护: 代码里真有 dispatch 调用且无 BOS 注册 ⇒ 必须报。"""
    _write(tmp_path, "bin/mesh/mesh-real-router.py", '''\
def run(packet):
    dispatch_to_backend(packet)
    try:
        return None
    except Exception:
        return None
''')
    module = _load(monkeypatch, tmp_path)

    assert module.main() == 0
    out = capsys.readouterr().out
    assert "mesh-real-router.py" in out and "无 BOS URI 注册" in out, out


def test_bos_uri_in_string_counts(capsys, monkeypatch, tmp_path) -> None:
    """BOS URI 在字符串里, 那条判据必须继续扫全文, 不得被 code-only 误伤。"""
    _write(tmp_path, "bin/mesh/mesh-registered.py", '''\
BOS = "bos://mesh/route/run"

def run(packet):
    dispatch_to_backend(packet)
    try:
        return None
    except Exception:
        return None
''')
    module = _load(monkeypatch, tmp_path)

    assert module.main() == 0
    out = capsys.readouterr().out
    assert "mesh-registered.py" not in out, f"有 BOS 注册却被报: {out}"
