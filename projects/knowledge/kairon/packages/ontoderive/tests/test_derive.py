# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
import json

from ontoderive.core.derive import OntoDerive


def test_init_project(tmp_path):
    od = OntoDerive(tmp_path)
    assert od.log_dir.exists()


def test_derive(z_park_path):
    od = OntoDerive(z_park_path)
    s = od.derive()
    assert s["facts"] >= 2
    assert "derived_at" in s


def test_check(z_park_path):
    od = OntoDerive(z_park_path)
    results = od.check()
    assert len(results) == 13


def test_generate_report(z_park_path):
    od = OntoDerive(z_park_path)
    od.derive()
    od.check()
    report = od.generate_report()
    assert "事实数" in report


def test_resolve_new(tmp_path):
    od = OntoDerive(tmp_path)
    od.log_dir.mkdir(parents=True, exist_ok=True)
    (od.log_dir / "check-result.json").write_text(
        json.dumps({"details": [{"protocol_id": "C-01", "passed": False, "fixes": ["创建 facts/data.md"]}]})
    )
    assert od.resolve() >= 1


def test_run_rounds(z_park_path):
    od = OntoDerive(z_park_path)
    od.run_rounds(rounds=2)


def test_empty_project_derive(tmp_path):
    od = OntoDerive(tmp_path)
    assert od.derive()["facts"] == 0


def test_empty_project_check(tmp_path):
    od = OntoDerive(tmp_path)
    c01 = [r for r in od.check() if r["protocol_id"] == "C-01"]
    assert not c01[0]["passed"]
