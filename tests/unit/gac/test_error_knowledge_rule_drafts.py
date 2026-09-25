"""事故→规则管道的人审队列必须可扫描、可补齐、可见报（BET-Y2Q3-T10-202）.

Regression guard for the 2026-09-24 measurement: 37 pitfalls, 3 of them past
``ESCALATION_THRESHOLD``, and **zero** drafts in ``.omo/_delivery/rule-drafts/``
— a directory that was itself gitignored, so even the drafts that had been
generated died with their worktree. Promotion was reachable only as a side
effect of the escape feed (which needs a worktree-local escape ledger) or
``record --confirm-dup``, and neither ``stats`` nor ``check`` reported the gap.
Same round found ``feed_from_escapes`` matching across categories, so an escape
on one surface inflated the encounter count that drives rule escalation on an
unrelated pitfall of another category.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "error-knowledge.py"
ARTIFACT_HOOK = ROOT / "bin" / "gac" / "check-runtime-artifacts.py"
ARTIFACT_FAST = ROOT / "bin" / "gac" / "ci-local-fast.py"

# 4 shared distinctive tokens: enough to clear symptom_overlap's >=3 word bar, so
# a miss below is the category filter talking, not the fuzzy matcher being weak.
GATE_SYMPTOM = "gac local gate blocks commit because staged claim is missing owner routing"


def _load_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("error_knowledge_drafts", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _isolate(monkeypatch: pytest.MonkeyPatch, module: types.ModuleType, tmp_path: Path) -> tuple[Path, Path]:
    pitfalls = tmp_path / "pitfalls"
    drafts = tmp_path / "rule-drafts"
    monkeypatch.setattr(module, "PITFALLS_DIR", pitfalls)
    monkeypatch.setattr(module, "RULE_DRAFTS_DIR", drafts)
    pitfalls.mkdir(parents=True)
    return pitfalls, drafts


def _pitfall(
    pitfalls: Path,
    pid: str,
    *,
    category: str,
    count: int,
    symptom: str = GATE_SYMPTOM,
    status: str = "active",
) -> dict:
    entry = {
        "schema": "agent-error/v1",
        "id": pid,
        "category": category,
        "severity": "medium",
        "title": f"{pid} 测试条目",
        "symptom": symptom,
        "root_cause": "test",
        "solution": "test",
        "prevention": "test",
        "tags": ["fixture"],
        "discovered_by": "governance-agent",
        "discovered_at": "2026-09-01",
        "times_encountered": count,
        "last_confirmed_at": "2026-09-20",
        "status": status,
    }
    path = pitfalls / category / f"{pid}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    path.write_text(yaml.dump(entry, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return entry


def _escape(escape_dir: Path, key: str, excerpt: str, *, times: int = 3) -> None:
    """FEED_MIN_COUNT is 3, so a single record would be filtered out before matching."""
    escape_dir.mkdir(parents=True, exist_ok=True)
    stem = key.replace("|", "-")
    for i in range(times):
        (escape_dir / f"{stem}-{i}.json").write_text(
            json.dumps({"fingerprint_key": key, "fingerprints": [{"output_excerpt": excerpt}]}), encoding="utf-8"
        )


def test_overdue_pitfall_is_named_and_then_drained(monkeypatch, tmp_path):
    module = _load_module()
    pitfalls, drafts = _isolate(monkeypatch, module, tmp_path)
    _pitfall(pitfalls, "PITFALL-GAT-901", category="gate", count=module.ESCALATION_THRESHOLD)
    _pitfall(pitfalls, "PITFALL-GAT-902", category="gate", count=module.ESCALATION_THRESHOLD - 1)

    assert module.rule_draft_queue()["overdue"] == ["PITFALL-GAT-901"]
    assert module.rule_draft_queue()["drafted"] == []

    created = module.promote_overdue()
    assert [p.name for p in created] == ["CR-PITFALL-GAT-901.json"]
    after = module.rule_draft_queue()
    assert after["overdue"] == [] and after["drafted"] == ["PITFALL-GAT-901"]
    draft = json.loads((drafts / "CR-PITFALL-GAT-901.json").read_text(encoding="utf-8"))
    assert draft["source_pitfall"] == "PITFALL-GAT-901"
    assert draft["status"] == "awaiting_human_review"


def test_promotion_is_idempotent_and_skips_obsolete(monkeypatch, tmp_path):
    """Re-scan must never clobber a draft a human may already be annotating."""
    module = _load_module()
    pitfalls, drafts = _isolate(monkeypatch, module, tmp_path)
    _pitfall(pitfalls, "PITFALL-GAT-903", category="gate", count=9)
    _pitfall(pitfalls, "PITFALL-GAT-904", category="gate", count=9, status="obsolete")

    assert module.promote_overdue() and not module.promote_overdue()
    assert list(drafts.glob("*.json")) == [drafts / "CR-PITFALL-GAT-903.json"]

    (drafts / "CR-PITFALL-GAT-903.json").write_text('{"hand": "annotated"}', encoding="utf-8")
    module.promote_overdue()
    assert json.loads((drafts / "CR-PITFALL-GAT-903.json").read_text(encoding="utf-8")) == {"hand": "annotated"}


def test_check_reports_overdue_without_changing_exit_code(monkeypatch, tmp_path):
    """check feeds gac-local-gate; a queue awaiting human review is not a red gate."""
    module = _load_module()
    pitfalls, _drafts = _isolate(monkeypatch, module, tmp_path)
    _pitfall(pitfalls, "PITFALL-GAT-905", category="gate", count=6)

    def _run_check() -> tuple[int, dict]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = module.cmd_check(argparse.Namespace(json=True))
        return rc, json.loads(buf.getvalue())

    rc_missing, report_missing = _run_check()
    assert rc_missing == 0 and report_missing["problems"] == []
    assert report_missing["rule_drafts"]["overdue"] == ["PITFALL-GAT-905"]

    module.promote_overdue()
    rc_present, report_present = _run_check()
    assert rc_present == rc_missing
    assert report_present["problems"] == report_missing["problems"]
    assert report_present["rule_drafts"] == {
        **report_missing["rule_drafts"],
        "overdue": [],
        "drafted": ["PITFALL-GAT-905"],
    }


def test_stats_names_overdue_drafts(monkeypatch, tmp_path):
    module = _load_module()
    pitfalls, _drafts = _isolate(monkeypatch, module, tmp_path)
    _pitfall(pitfalls, "PITFALL-GAT-906", category="gate", count=7)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        module.cmd_stats(argparse.Namespace(json=True))
    result = json.loads(buf.getvalue())
    assert result["escalated"] == ["PITFALL-GAT-906"]
    assert result["overdue_rule_drafts"] == ["PITFALL-GAT-906"]
    assert result["rule_drafts_drafted"] == []


def test_feed_cannot_bump_a_pitfall_of_another_category(monkeypatch, tmp_path):
    """G3: the same words must not move an unrelated category's escalation evidence."""
    module = _load_module()
    pitfalls, drafts = _isolate(monkeypatch, module, tmp_path)
    _pitfall(pitfalls, "PITFALL-GAT-907", category="gate", count=2)
    escape_dir = tmp_path / "swarm-escape"
    # pointer-drift maps to category=submodule; symptom deliberately word-identical.
    _escape(escape_dir, "pointer-drift|submodule-ancestry-gate", GATE_SYMPTOM)

    counts = module.feed_from_escapes(escape_dir)
    assert counts == {"fed": 1, "bumped": 0, "promoted": 0}
    gate = yaml_load(pitfalls / "gate" / "PITFALL-GAT-907.yaml")
    assert gate["times_encountered"] == 2, "cross-category escape leaked into escalation evidence"
    created = list((pitfalls / "submodule").glob("*.yaml"))
    assert len(created) == 1
    assert yaml_load(created[0])["category"] == "submodule"
    assert list(drafts.glob("*.json")) == []


def test_feed_still_promotes_within_the_matching_category(monkeypatch, tmp_path):
    module = _load_module()
    pitfalls, drafts = _isolate(monkeypatch, module, tmp_path)
    _pitfall(pitfalls, "PITFALL-GAT-908", category="gate", count=2)
    escape_dir = tmp_path / "swarm-escape"
    # surface = 指纹 key 的第一段；"gac" 映射到 scoring，这里要的是 gate 类别
    _escape(escape_dir, "ci-local-fast|requirement-iteration-gate", GATE_SYMPTOM)

    counts = module.feed_from_escapes(escape_dir)
    assert counts["bumped"] == 1 and counts["promoted"] == 1
    assert yaml_load(pitfalls / "gate" / "PITFALL-GAT-908.yaml")["times_encountered"] == 2 + 3
    assert (drafts / "CR-PITFALL-GAT-908.json").is_file()


def test_feed_promotes_even_without_an_escape_ledger(monkeypatch, tmp_path):
    """The back edge must not be hostage to a worktree-local directory."""
    module = _load_module()
    pitfalls, drafts = _isolate(monkeypatch, module, tmp_path)
    _pitfall(pitfalls, "PITFALL-GAT-909", category="gate", count=module.ESCALATION_THRESHOLD)

    counts = module.feed_from_escapes(tmp_path / "no-such-escape-dir")
    assert counts == {"fed": 0, "bumped": 0, "promoted": 1}
    assert (drafts / "CR-PITFALL-GAT-909.json").is_file()


def test_confirm_and_reject_fail_loudly_instead_of_no_op(monkeypatch, capsys):
    """These two subcommands had parsers but no handler: help + exit 0, forever."""
    module = _load_module()
    for verb in ("confirm", "reject"):
        rc = module.cmd_review_unwired(argparse.Namespace(cmd=verb, id="PITFALL-GAT-004"))
        assert rc == 2
    err = capsys.readouterr().err
    assert "NOT_IMPLEMENTED" in err and "governance-checks.yaml" in err


def test_rule_drafts_queue_is_tracked_in_git():
    """.gitignore re-includes it exactly once, next to the other queue exceptions."""
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert gitignore.count("!.omo/_delivery/rule-drafts/") == 1
    probe = ROOT / ".omo" / "_delivery" / "rule-drafts" / "probe.json"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text("{}", encoding="utf-8")
    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", str(probe.relative_to(ROOT))],
            cwd=ROOT,
            capture_output=True,
        )
        assert ignored.returncode != 0, "rule-drafts fell back under .omo/_delivery/*"
    finally:
        probe.unlink()


def yaml_load(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _whitelist_literals(path: Path) -> list[str]:
    """Read ``WHITELIST_PREFIXES`` without importing either gate.

    One copy is module-level, the other is function-local, so only AST extraction
    compares them on equal terms.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = [
        ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id == "WHITELIST_PREFIXES"
    ]
    assert len(found) == 1, f"{path.name}: expected exactly one WHITELIST_PREFIXES, got {len(found)}"
    return found[0]


def _stage(repo: Path, *paths: str) -> None:
    for rel in paths:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", *paths], cwd=repo, check=True, capture_output=True)


def _run_hook_gate(repo: Path) -> int:
    return subprocess.run(
        [sys.executable, str(ARTIFACT_HOOK), "--staged"], cwd=repo, capture_output=True, text=True
    ).returncode


def _run_fast_gate(repo: Path) -> int:
    spec = importlib.util.spec_from_file_location("ci_local_fast_artifacts", ARTIFACT_FAST)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass field resolution needs the module registered
    spec.loader.exec_module(module)
    return module.run_runtime_artifact_gate(root=repo, output=io.StringIO())


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    return repo


def test_both_runtime_artifact_gates_share_one_whitelist(git_repo: Path):
    """I8: the drawer had two locks that did not know about each other.

    ``check-runtime-artifacts.py`` documents itself as a port of
    ``ci-local-fast.py::run_runtime_artifact_gate()``, yet only the hook copy grew
    ``WHITELIST_PREFIXES`` — drift is the failure mode this test exists to kill.
    """
    hook, fast = _whitelist_literals(ARTIFACT_HOOK), _whitelist_literals(ARTIFACT_FAST)
    assert hook == fast, f"runtime-artifacts whitelist drift: hook={hook} fast={fast}"
    assert ".omo/_delivery/rule-drafts/" in hook
    assert {p for p in hook if p.startswith(".omo/_delivery/")} == {
        ".omo/_delivery/calibration/",
        ".omo/_delivery/events/",
        ".omo/_delivery/scene-outcomes/",
        ".omo/_delivery/rule-drafts/",
    }, "widening the drawer needs a principal decision, not another prefix appended here"


@pytest.mark.parametrize("run_gate", [_run_hook_gate, _run_fast_gate], ids=["pre-commit", "ci-local-fast"])
def test_drafts_may_be_committed_without_opening_the_drawer(git_repo: Path, run_gate):
    """.gitignore alone still loses at `git commit`; the tracked queue must pass both gates."""
    _stage(git_repo, ".omo/_delivery/rule-drafts/CR-PITFALL-GAT-910.json")
    assert run_gate(git_repo) == 0, "promotion queue is still blacklisted from version control"

    _stage(git_repo, ".omo/_delivery/runtime-junk.json")
    assert run_gate(git_repo) == 1, "whitelisting the drafts directory un-protected _delivery"

