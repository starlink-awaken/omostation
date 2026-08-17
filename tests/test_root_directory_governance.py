from __future__ import annotations

import importlib.util
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "bin/ssot/root-directory-governance-scan.py"
    spec = importlib.util.spec_from_file_location("root_directory_governance", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_allowed_ignored_pattern_matches() -> None:
    module = load_module()
    policy = {"allowed_ignored_dirs": ["archive-*"]}

    assert module.allowed_ignored_dir("archive-20260817", policy)
    assert not module.allowed_ignored_dir("scripts-fix-ci", policy)


def test_untracked_non_ignored_directory_is_blocking() -> None:
    module = load_module()
    row = {
        "is_tracked": False,
        "is_ignored": False,
        "policy_allowed": False,
    }

    assert module.governance_violation(row)
    tagged = module.rank_and_tag(
        [
            {
                **row,
                "files": 1,
                "kb": 1.0,
                "has_readme": True,
                "has_agents": True,
            }
        ]
    )
    assert tagged[0]["priority"] == "must"


def test_allowed_ignored_directory_is_not_blocking() -> None:
    module = load_module()
    row = {
        "is_tracked": False,
        "is_ignored": True,
        "policy_allowed": True,
    }

    assert not module.governance_violation(row)
