"""配置系统测试"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from ontoderive.foundation.config import Config


def test_config_defaults():
    cfg = Config(".")
    assert cfg.get("toolforge_mode") == "keyword"
    assert cfg.get("toolforge_top_n") == 5


def test_config_getitem():
    cfg = Config(".")
    assert cfg["toolforge_mode"] == "keyword"


def test_config_contains():
    cfg = Config(".")
    assert "toolforge_mode" in cfg
    assert "nonexistent" not in cfg


def test_config_to_dict():
    cfg = Config(".")
    d = cfg.to_dict()
    assert "toolforge_mode" in d
    assert "toolforge_top_n" in d


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("ONTO_TOOLFORGE_MODE", "hybrid")
    cfg = Config(".")
    assert cfg.get("toolforge_mode") == "hybrid"
    monkeypatch.delenv("ONTO_TOOLFORGE_MODE", raising=False)
    monkeypatch.setenv("ONTO_TOOLFORGE_TOP_N", "10")
    cfg2 = Config(".")
    assert cfg2.get("toolforge_top_n") == 10
    monkeypatch.delenv("ONTO_TOOLFORGE_TOP_N", raising=False)


def test_config_cli_override():
    import argparse

    ns = argparse.Namespace(toolforge_mode="tfidf", toolforge_top_n=None, derive_iterations=None)
    cfg = Config(".", cli_args=ns)
    assert cfg.get("toolforge_mode") == "tfidf"


def test_config_nonexistent_project():
    cfg = Config("/nonexistent/path")
    assert cfg.get("toolforge_mode") == "keyword"
