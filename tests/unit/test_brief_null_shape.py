"""BET-Y2Q4-T10-236 — a present-but-null system.yaml key must read exactly like an absent file.

T10-235 shipped the creator of ``.omo/state/system.yaml`` and untracked it; the creator's
contract is a key set equal to the ``write-owners.yaml`` declaration, so the 13 keys the
producer does not own can only appear as empty shape (YAML ``null``). ``dict.get(key,
default)`` returns ``None`` for such a key — the default only covers "key missing" — so the
brief generator sat between two states that both worked: absent ran, valued ran, empty shape
crashed at the ``health_score >= 90`` comparison and rendered ``None/100``.

The folding itself landed upstream (#4687 → ``b85ed694f``). These cases are its teeth:

* I1 equivalence — the folded and absent arms print byte-identical briefs.
* I2 truth not swallowed — a real ``health_score: 46`` still reads 46 (rules out ``or default``,
  which would also fold a legitimate ``0``).
* I4 site set pinned — the ``.get(<6 keys>, default)`` sites in ``bin/**`` equal a reviewed list,
  and ``generate-brief.py`` contributes none of them (the fold keeps them folded).
* I5/I6 — detector self-proof and CI visibility.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "mof" / "generate-brief.py"
WORKFLOW = ROOT / ".github" / "workflows" / "governance-check.yml"

# The six keys the materializer emits as empty shape (spec §1 / §3).
EMPTY_SHAPE_KEYS = frozenset(
    {
        "health_score",
        "health_score_source",
        "health_score_generated_at",
        "governance_anomaly_score",
        "governance_feedback_last_run",
        "service_online_ratio",
    }
)

# I4: every ``.get(<one of the six>, <default>)`` site in bin/**, counted per (file, key).
# Counts rather than line numbers: AGENTS.md §7⑥ — line pointers rot on any edit above them,
# while the same file legitimately carries several sites for one key (quarterly-report.py has
# three for health_score). Disposition for all nine: spec §3 measured them reading identically
# under absent vs empty shape; only generate-brief.py's own pair was behaviourally broken, and
# that pair must stay out of this shape (asserted below).
REVIEWED_SITES: dict[tuple[str, str], int] = {
    ("bin/gac/governance-readiness.py", "health_score"): 1,
    ("bin/gac/m1-closeout-report.py", "health_score"): 1,
    ("bin/gac/unified-health-score.py", "service_online_ratio"): 1,
    ("bin/reports/quarterly-report.py", "health_score"): 3,
    ("bin/reports/quarterly-report.py", "governance_anomaly_score"): 1,
    ("bin/reports/quarterly-report.py", "service_online_ratio"): 1,
    ("bin/ssot/weekly-review.py", "health_score"): 1,
}
BRIEF_GENERATOR = "bin/mof/generate-brief.py"


def _scan_default_get_sites(base: Path) -> dict[tuple[str, str], int]:
    """AST scan (spec §3): ``ast.Call`` with ``func.attr == "get"``, first arg a Constant among
    the six keys, and >= 2 positional args. Regex gave 10 / 11 / 13 on the same text depending
    on engine and line wrapping, so the criterion is computed from the syntax tree."""
    found: dict[tuple[str, str], int] = {}
    for path in sorted(base.rglob("*.py")):
        if "_vendored" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, ValueError, UnicodeDecodeError):
            continue
        rel = path.relative_to(base.parent).as_posix()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
            ):
                continue
            if len(node.args) < 2:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and first.value in EMPTY_SHAPE_KEYS:
                key = (rel, str(first.value))
                found[key] = found.get(key, 0) + 1
    return found


def _load_generator() -> object:
    """The module name has a hyphen, so it must be loaded by file location (precedent:
    tests/unit/mof/test_generate_brief_no_host_paths.py:21)."""
    spec = importlib.util.spec_from_file_location("generate_brief", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _child_env(state_root: Path) -> dict[str, str]:
    """Both arms run against the checkout under test, never the host's profile. Pinning
    OMOSTATION_ROOT and clearing the two write-plane overrides is what makes the pair
    comparable — and keeps the fixture from writing into a real state root (AGENTS.md §7 hermetic)."""
    return {
        **os.environ,
        "OMOSTATION_ROOT": str(ROOT),
        "OMOSTATION_STATE_ROOT": str(state_root),
        "OMO_EVENT_LEDGER_DB": str(state_root / "runtime" / "omo" / "event-ledger.sqlite3"),
    }


def _run_brief(state_root: Path) -> subprocess.CompletedProcess[str]:
    """判据-1 apparatus: a no-flag run prints to stdout and writes nothing (:609). The state
    root is redirected to a scratch directory so no arm can touch the real governed surface."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=_child_env(state_root),
        cwd=str(ROOT),
        check=False,
    )


def _state_file(state_root: Path) -> Path:
    return state_root / ".omo" / "state" / "system.yaml"


@pytest.fixture()
def scratch_state_root(tmp_path: Path) -> Path:
    root = tmp_path / "state"
    root.mkdir()
    return root


class TestNullShapeEquivalence:
    """I1 / 判据-1 — the same checkout, only ``system.yaml`` swapped."""

    def test_null_shape_stdout_equals_absent_shape(self, scratch_state_root: Path) -> None:
        absent = _run_brief(scratch_state_root)
        assert _state_file(scratch_state_root).is_file() is False, "absent arm must not write state"
        assert absent.returncode == 0, absent.stderr[-2000:]

        materialized = subprocess.run(
            [sys.executable, str(ROOT / "bin" / "gac" / "materialize-system-state.py"), "--json"],
            capture_output=True,
            text=True,
            env=_child_env(scratch_state_root),
            cwd=str(ROOT),
            check=False,
        )
        assert materialized.returncode == 0, materialized.stderr[-2000:]
        state_file = _state_file(scratch_state_root)
        assert state_file.is_file(), f"creator did not materialize into the scratch root: {materialized.stdout[-500:]}"

        # The shape under test: the six keys present and null, or the file would be vacuous.
        import yaml as _yaml

        produced = _yaml.safe_load(state_file.read_text(encoding="utf-8")) or {}
        null_keys = sorted(k for k in EMPTY_SHAPE_KEYS if k in produced and produced[k] is None)
        assert null_keys, (
            "empty shape carried no null key, so this comparison is vacuous — "
            f"produced keys: {sorted(produced)[:8]}"
        )

        null = _run_brief(scratch_state_root)
        assert null.returncode == 0, (
            f"empty shape must not be dumber than absence; stderr tail: {null.stderr[-2000:]}"
        )
        # spec §2 has two faces: the rc=1 comparison and the rendered "None/100". Equality alone
        # would pass if both arms rendered None, so the token is pinned on the null arm directly.
        assert "None" not in null.stdout, "the empty shape leaked a literal None into the brief"

        module = _load_generator()
        norm = module.normalize_brief_content
        assert norm(null.stdout) == norm(absent.stdout), _first_difference(norm(absent.stdout), norm(null.stdout))

    def test_real_value_is_not_swallowed_by_the_fold(self, scratch_state_root: Path) -> None:
        """I2 / 判据-2 — 46 still reads 46; a fold written as ``.get(k) or default`` would pass
        the equivalence test and fail this one, which is exactly why both exist."""
        state_file = _state_file(scratch_state_root)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("health_score: 46\ngovernance_anomaly_score: 71\n", encoding="utf-8")

        run = _run_brief(scratch_state_root)
        assert run.returncode == 0, run.stderr[-2000:]
        # Anchored to the health-detail line: a bare "46/100" can also occur inside another
        # number's rendering, and an unanchored "90/100" absence check would then be luck.
        assert "**复合健康分**: `46/100`" in run.stdout, "the snapshot value must reach the brief"
        assert "**复合健康分**: `90/100`" not in run.stdout, "default leaked into a valued read"
        assert "46/100" in run.stdout and run.stdout.count("46/100") == 2, run.stdout[:400]

    def test_legitimate_zero_survives_the_fold(self, scratch_state_root: Path) -> None:
        """The other half of I2: a real 0 is not "unmeasured"."""
        state_file = _state_file(scratch_state_root)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("health_score: 0\ngovernance_anomaly_score: 100\n", encoding="utf-8")

        run = _run_brief(scratch_state_root)
        assert run.returncode == 0, run.stderr[-2000:]
        # Substring trap: "0/100" occurs inside "100/100", so the bare token would pass on a
        # collapsed default. Only the anchored field can tell a real 0 from a folded one.
        assert "**复合健康分**: `0/100`" in run.stdout, "collapsing a real 0 to the default is the forbidden fold shape"
        assert "**复合健康分**: `90/100`" not in run.stdout, run.stdout[:400]

    def test_crash_site_is_reached_by_both_arms(self) -> None:
        """The pre-fix failure was ``if health_score >= 90`` raising on None; if that comparison
        is gone the equivalence test would pass for the wrong reason."""
        source = SCRIPT.read_text(encoding="utf-8")
        assert "health_score >= 90" in source, (
            "spec §2 names this as the only crashing site; without it the equivalence is not the fix's guard"
        )


class TestSiteInventory:
    """I4 — the site list is a set equality, not a subset, and the detector is not a no-op."""

    def test_measured_sites_equal_reviewed_list(self) -> None:
        measured = _scan_default_get_sites(ROOT / "bin")
        assert measured == REVIEWED_SITES, _site_delta(measured, REVIEWED_SITES)

    def test_brief_generator_contributes_no_default_get_site(self) -> None:
        """I3 locality: the fold lives at the read site, so the generator must no longer match
        the ``.get(<key>, default)`` shape. A revert would reappear here and in the equivalence."""
        measured = _scan_default_get_sites(ROOT / "bin")
        leaked = {site for site in measured if site[0] == BRIEF_GENERATOR}
        assert leaked == set(), f"generate-brief.py regression back to a swallowed default: {sorted(leaked)}"

    def test_detector_fires_on_a_synthetic_site(self, tmp_path: Path) -> None:
        """判据-5 — empty green is not evidence. Feed the scanner a tree carrying one new site."""
        bin_dir = tmp_path / "bin" / "gac"
        bin_dir.mkdir(parents=True)
        (bin_dir / "synthetic-consumer.py").write_text(
            'def f(data):\n    return data.get("health_score", 0)\n', encoding="utf-8"
        )
        found = _scan_default_get_sites(tmp_path / "bin")
        synthetic = ("bin/gac/synthetic-consumer.py", "health_score")
        assert found == {synthetic: 1}, found
        assert synthetic not in REVIEWED_SITES, "the synthetic site must be off the reviewed list"

    def test_detector_does_not_fire_on_folded_or_foreign_shapes(self, tmp_path: Path) -> None:
        """Anti-over-breadth: single-arg ``.get`` (the folded shape), a non-empty-shape key, and a
        keyword-default call must all stay out of the set, or the equality is self-proving noise."""
        bin_dir = tmp_path / "bin" / "gac"
        bin_dir.mkdir(parents=True)
        (bin_dir / "shapes.py").write_text(
            "def f(data):\n"
            '    a = data.get("health_score")\n'
            '    b = data.get("unrelated_key", 5)\n'
            '    c = data.get("governance_anomaly_score", default=7)\n'
            "    return a, b, c\n",
            encoding="utf-8",
        )
        assert _scan_default_get_sites(tmp_path / "bin") == {}

    def test_every_reviewed_site_points_at_a_real_file(self) -> None:
        for (rel, _key), _n in REVIEWED_SITES.items():
            assert (ROOT / rel).is_file(), f"stale inventory entry: {rel}"


class TestCIVisibility:
    """I6 / 判据-6 — tests/unit/** is not in any CI path filter, so an unlisted file is undelivered."""

    def test_workflow_names_this_file(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "test_brief_null_shape.py" in text, (
            "governance-check.yml must name tests/unit/test_brief_null_shape.py in its explicit "
            "pytest whitelist; local green is not CI evidence"
        )


def _first_difference(left: str, right: str) -> str:
    for i, (a, b) in enumerate(zip(left.splitlines(), right.splitlines(), strict=False)):
        if a != b:
            return f"first differing line {i}:\n  absent: {a!r}\n  null:   {b!r}"
    return (
        f"line counts differ: absent={len(left.splitlines())} null={len(right.splitlines())}\n"
        f"tail absent={left.splitlines()[-3:]!r}\ntail null  ={right.splitlines()[-3:]!r}"
    )


def _site_delta(measured: dict, reviewed: dict) -> str:
    extra = sorted(set(measured) - set(reviewed))
    missing = sorted(set(reviewed) - set(measured))
    count_mismatch = sorted(k for k in set(measured) & set(reviewed) if measured[k] != reviewed[k])
    return (
        f"new/unreviewed sites: {extra}\n"
        f"gone from inventory (shrink the list deliberately): {missing}\n"
        f"count mismatch: {count_mismatch}"
    )
