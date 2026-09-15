"""Tests for codeanalyze.analyzers.graphify — _extract_from_results, _map_file_type."""

from codeanalyze.analyzers.graphify import _extract_from_results, _map_file_type


class TestMapFileType:
    def test_known_types(self):
        assert _map_file_type("code") == "Module"
        assert _map_file_type("file") == "File"
        assert _map_file_type("document") == "Document"
        assert _map_file_type("concept") == "Concept"

    def test_unknown_type(self):
        assert _map_file_type("unknown") == "Artifact"
        assert _map_file_type("") == "Artifact"


class TestExtractFromResults:
    def test_empty_data(self):
        result = _extract_from_results({})
        assert result["entities"] == []
        assert result["relations"] == []
        assert result["error"] is None

    def test_with_nodes_and_links(self):
        data = {
            "nodes": [
                {"id": "n1", "label": "Node1", "norm_label": "node-1", "file_type": "code"},
                {"id": "n2", "label": "Node2", "norm_label": "node-2", "file_type": "file"},
            ],
            "links": [
                {"source": "n1", "target": "n2", "type": "IMPORTS"},
            ],
        }
        result = _extract_from_results(data)
        assert len(result["entities"]) == 2
        assert result["entities"][0]["id"] == "code-n1"
        assert result["entities"][0]["type"] == "Module"
        assert len(result["relations"]) == 1
        assert result["relations"][0]["source"] == "code-n1"
        assert result["relations"][0]["target"] == "code-n2"

    def test_duplicate_node_ids_skipped(self):
        data = {
            "nodes": [
                {"id": "n1", "label": "Dup", "norm_label": "dup"},
                {"id": "n1", "label": "Dup2", "norm_label": "dup"},
            ],
        }
        result = _extract_from_results(data)
        # Second node with same id is skipped
        assert len(result["entities"]) == 1

    def test_node_without_id_uses_norm_label(self):
        data = {
            "nodes": [
                {"id": "", "label": "LabelOnly", "norm_label": "norm-label"},
            ],
        }
        result = _extract_from_results(data)
        assert len(result["entities"]) == 1
        assert "norm-label" in result["entities"][0]["id"]

    def test_empty_link_type_defaults(self):
        data = {
            "links": [
                {"source": "a", "target": "b", "type": ""},
            ],
        }
        result = _extract_from_results(data)
        assert result["relations"][0]["type"] == "IMPORTS"
