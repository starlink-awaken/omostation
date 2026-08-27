# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
from ontoderive.foundation.utils import all_md, detect_cycles, load_json, rf, save_json, wf


def test_rf_file_exists(z_park_path):
    assert len(rf(z_park_path / "facts" / "data.md")) > 0


def test_rf_file_not_exists(tmp_path):
    assert rf(tmp_path / "nonexistent.md") == ""


def test_wf_and_rf(tmp_path):
    wf(tmp_path / "test.md", "hello")
    assert rf(tmp_path / "test.md") == "hello"


def test_wf_creates_parent(tmp_path):
    wf(tmp_path / "deep" / "nested" / "file.md", "test")
    assert (tmp_path / "deep" / "nested" / "file.md").exists()


def test_all_md(z_park_path):
    assert len(all_md(z_park_path / "facts")) >= 1


def test_all_md_empty(tmp_path):
    assert all_md(tmp_path / "nonexistent") == []


def test_load_json_success(tmp_path):
    (tmp_path / "test.json").write_text('{"key":"value"}')
    assert load_json(tmp_path / "test.json") == {"key": "value"}


def test_load_json_fail(tmp_path):
    (tmp_path / "bad.json").write_text("not json")
    assert load_json(tmp_path / "bad.json") is None


def test_load_json_not_exists(tmp_path):
    assert load_json(tmp_path / "nonexistent.json") is None


def test_save_json(tmp_path):
    save_json(tmp_path / "out.json", {"a": 1})
    assert load_json(tmp_path / "out.json") == {"a": 1}


def test_roundtrip(tmp_path):
    data = {"facts": 10, "entities": 5}
    save_json(tmp_path / "rt.json", data)
    assert load_json(tmp_path / "rt.json") == data


def test_detect_cycles_empty():
    assert detect_cycles({}, {}) == []


def test_detect_cycles_no_cycle():
    nodes = {"A": {}, "B": {}}
    edges = {"A": ["B"]}
    assert detect_cycles(nodes, edges) == []


def test_detect_cycles_with_cycle():
    nodes = {"A": {}, "B": {}}
    edges = {"A": ["B"], "B": ["A"]}
    cycles = detect_cycles(nodes, edges)
    assert len(cycles) >= 1
