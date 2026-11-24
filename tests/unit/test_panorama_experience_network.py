"""Tests for collect_experience_network() pitfall ingestion and edge linking."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_exp_net_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_experience_network_reads_real_categorized_pitfalls() -> None:
    module = _module()
    res = module.collect_experience_network()
    assert res["pitfall_count"] >= 50, res
    assert res["parse_errors"] == [], res["parse_errors"]
    pitfall_nodes = [n for n in res["nodes"] if n["type"] == "pitfall"]
    assert pitfall_nodes, res
    assert all(n["id"] != "PIT-" and n["name"] for n in pitfall_nodes), pitfall_nodes


def test_collect_experience_network_parses_nested_yaml_surfaces_errors_and_edges(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)

    cat_dir = tmp_path / ".omo/_knowledge/pitfalls/gate"
    cat_dir.mkdir(parents=True)
    (cat_dir / "PITFALL-GAT-001.yaml").write_text(
        "schema: agent-error/v1\n"
        "id: PITFALL-GAT-001\n"
        "title: Shell word split trap\n"
        "note: See ADR-0456 and P75\n",
        encoding="utf-8",
    )
    (cat_dir / "PITFALL-GAT-999.yaml").write_text(
        "broken: [\n",
        encoding="utf-8",
    )

    dec_dir = tmp_path / ".omo/_knowledge/decisions"
    dec_dir.mkdir(parents=True)
    (dec_dir / "0456-example.md").write_text(
        "# ADR-0456\nResolves PITFALL-GAT-001.\n",
        encoding="utf-8",
    )

    res = module.collect_experience_network()
    node_ids = {n["id"] for n in res["nodes"]}
    assert "PITFALL-GAT-001" in node_ids, res["nodes"]
    assert "DEC-0456-example" in node_ids, res["nodes"]
    assert "PIT-" not in node_ids
    assert len(res["parse_errors"]) == 1 and "PITFALL-GAT-999.yaml" in res["parse_errors"][0]
    assert {
        "from": "DEC-0456-example",
        "to": "PITFALL-GAT-001",
        "rel": "resolves",
    } in res["edges"]
