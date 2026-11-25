#!/usr/bin/env python3
"""`bin/ssot/_shared.check_evidence` 遇坏 evidence_ref 不得中断整扫.

钉的是**覆盖面**而不是返回值: `verify.py:scan()` 逐条目调 `check_evidence`, 一个
坏 ref 抛异常 → 整个 task 门禁死在肇事条目上, 它之后的终态项**根本没被校验**。
2026-11-25 CI 实证 (gac-gate `[WARN] task-verify`):

    OSError: [Errno 36] File name too long: '<root>/bin/agent-workflow.py:738-773
    `_assert_packet_sources_at_ref` —— :744-745 把 ledger 列为比对源…'

散文注解写进 `evidence_refs` 是既有用法 (见 OMO-DEBT-EVIDENCE-REF-ACCEPTANCE-TWO-JUDGES),
Linux 侧 `stat()` 对超长名单段抛 ENAMETOOLONG, 非 str 条目抛 TypeError。

**为什么两套用例**: 本机 macOS 对超长名/NUL 的 `stat()` 一律返回 ENOENT (实测
300/1024/2000/5000 字符与 `a\\0b` 全不 raise), 所以 ENAMETOOLONG 只能在 CI 侧真实触发
—— 那条用桩还原 Linux 语义; TypeError 那类本机就抛, 走**真实入口** `verify.py --mode task`,
免得接线死了全程绿 (同 test_gac_guard_submodules 的教训)。

Run: python3 tests/bin/test_ssot_check_evidence_uncaught_oserror.py
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "bin" / "ssot" / "_shared.py"
VERIFY = ROOT / "bin" / "ssot" / "verify.py"
# 排在 items/ 首字母最前, 保证「中断」一定发生在另一个条目之前
OFFENDER_ID = "AAA-MALFORMED-REF"
VICTIM_ID = "ZZZ-UNVERIFIED-TASK"


def _load_shared():
    sys.path.insert(0, str(SHARED.parent))
    spec = importlib.util.spec_from_file_location("ssot_shared", SHARED)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _tree(tmp_path: Path) -> Path:
    """一棵最小工作区: 一个带坏 ref 的已核实条目 + 一个真虚假完成条目."""
    items = tmp_path / ".omo" / "debt" / "items"
    items.mkdir(parents=True)
    prose = "bin/agent-workflow.py:738-773 注解 —— 把 ledger 列为比对源, 读工作树字节即拦" * 12
    (items / f"{OFFENDER_ID}.yaml").write_text(
        f"""id: {OFFENDER_ID}
title: 散文注解 + 非 str 条目混进 evidence_refs
lifecycle_state: resolved
evidence_refs:
  - "{prose}"
  - 12345
resolution_evidence: 已核实修复, 见 PR。
""",
        encoding="utf-8",
    )
    (items / f"{VICTIM_ID}.yaml").write_text(
        f"""id: {VICTIM_ID}
title: 标了 resolved 但什么证据都没有
lifecycle_state: resolved
evidence_refs: []
""",
        encoding="utf-8",
    )
    return tmp_path


def _run_task_verify(ws: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VERIFY), "--mode", "task", "--root", str(ws)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_real_entry_survives_malformed_refs(tmp_path):
    """真实入口: 坏 ref 条目不得让整扫崩掉, 后面的虚假完成仍要被点名."""
    ws = _tree(tmp_path)
    run = _run_task_verify(ws)
    combined = run.stdout + run.stderr
    assert "Traceback" not in combined, f"check_evidence 上抛中断整扫:\n{combined[-600:]}"
    # 两个条目都进了判定 (中断的话只会剩肇事条目之前的一半)
    assert "completed: 2" in combined, combined
    # 且坏 ref 条目按文本证据判为已核实, 空证据条目判为虚假完成
    assert "unverified: 1" in combined, combined
    assert VICTIM_ID in combined, f"虚假完成条目没被点名 (覆盖面丢失):\n{combined}"
    assert OFFENDER_ID not in combined.split("RED FLAG")[-1], "有 resolution_evidence 文字却判虚假完成"
    assert run.returncode == 1, f"存在虚假完成却放行:\n{combined}"


def test_non_str_ref_does_not_raise():
    m = _load_shared()
    count, found = m.check_evidence(
        {"evidence_refs": [12345, None, "", {"a": 1}], "resolution_evidence": "文字证据"},
        ROOT,
    )
    assert count == 4
    assert found is True


def test_enametoolong_ref_is_miss_not_crash(monkeypatch):
    """Linux 语义桩: 本机 macOS 的 stat() 对超长名返回 ENOENT, 只能造出 errno 36."""
    m = _load_shared()
    real_path = m.Path

    class _BoomPath:
        def __init__(self, *parts):
            self._s = str(parts[-1]) if parts else "."

        def is_absolute(self):
            return self._s.startswith("/")

        def __truediv__(self, other):
            return _BoomPath(f"{self._s}/{other}")

        def exists(self):
            if len(self._s) > 255:
                raise OSError(36, "File name too long")
            return False

    # 先证桩本身会抛 —— 否则这条用例是空转 (仪器阴性得先证明仪器能响)
    try:
        _BoomPath("x" * 300).exists()
    except OSError as e:
        assert e.errno == 36, e
    else:
        raise AssertionError("桩没有抛 ENAMETOOLONG, 用例无法钉住 CI 形态")

    boom_root = _BoomPath(str(ROOT))
    monkeypatch.setattr(m, "Path", _BoomPath)
    try:
        prose = "bin/x.py:1-9 —— 散文注解" * 30
        count, found = m.check_evidence({"evidence_refs": [prose]}, boom_root)
        assert count == 1
        assert found is False, "读不出的 ref 应为未命中, 不得抛出"
        # 有文本证据时仍判已核实 (不被坏 ref 连坐)
        _, found2 = m.check_evidence(
            {"evidence_refs": [prose], "closed_evidence": "PR #1 合并"}, boom_root
        )
        assert found2 is True
    finally:
        monkeypatch.setattr(m, "Path", real_path)


if __name__ == "__main__":
    import inspect
    from tempfile import mkdtemp

    failures = []
    tests = [(n, o) for n, o in globals().items() if n.startswith("test_") and callable(o)]
    for name, fn in tests:
        kwargs = {}
        params = inspect.signature(fn).parameters
        if "tmp_path" in params:
            kwargs["tmp_path"] = Path(mkdtemp())
        if "monkeypatch" in params:
            import _pytest.monkeypatch as mp

            kwargs["monkeypatch"] = mp.MonkeyPatch()
        try:
            fn(**kwargs)
            print(f"  PASS {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failures.append(name)
    if failures:
        sys.exit(1)
    print(f"\n{len(tests)} tests passed")
