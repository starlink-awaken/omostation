"""规约检查模块测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.core.check import run_check


def test_run_check_zpark(z_park_path):
    root = z_park_path
    results, counts = run_check(
        root,
        root / "facts",
        root / "entities",
        root / "inferences",
        root / "scheme",
        root / "_derivation_logs",
    )
    assert len(results) == 13
    assert counts["PASS"] >= 8


def test_run_check_empty(tmp_path):
    (tmp_path / "facts").mkdir()
    (tmp_path / "entities").mkdir()
    (tmp_path / "inferences").mkdir()
    (tmp_path / "scheme").mkdir()
    (tmp_path / "_derivation_logs").mkdir()
    results, counts = run_check(
        tmp_path,
        tmp_path / "facts",
        tmp_path / "entities",
        tmp_path / "inferences",
        tmp_path / "scheme",
        tmp_path / "_derivation_logs",
    )
    assert len(results) == 13
    # 空项目应有BLOCKER
    assert counts["BLOCKER"] >= 1


def test_check_result_format(z_park_path):
    root = z_park_path
    results, _ = run_check(
        root, root / "facts", root / "entities", root / "inferences", root / "scheme", root / "_derivation_logs"
    )
    for r in results:
        assert "protocol_id" in r
        assert "passed" in r
        assert "severity" in r
        assert "detail" in r
        assert "file" in r
        assert "line" in r


def test_c07_uses_typevalidator(z_park_path):
    """ISC-3: C-07 使用 TypeValidator"""
    root = z_park_path
    results, _ = run_check(
        root, root / "facts", root / "entities", root / "inferences", root / "scheme", root / "_derivation_logs"
    )
    c07 = [r for r in results if r["protocol_id"] == "C-07"]
    assert len(c07) == 1
    # C-07 应该包含类型相关细节
    assert "v2前缀" in c07[0]["detail"] or "类型" in c07[0]["detail"]


def test_derive_delegates_to_check(z_park_path):
    """ISC-2: derive.py check()委托给check.py"""
    from ontoderive.core.derive import OntoDerive

    od = OntoDerive(z_park_path)
    results = od.check()
    assert len(results) == 13
