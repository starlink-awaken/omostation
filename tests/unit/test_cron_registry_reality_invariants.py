"""`.omo/cron/registry.yaml` 的登记↔现实一致性不变式（BET-Y2Q4-T10-224）。

三条不变式全部只看文件内部，不查本机 launchctl / LaunchAgents —— 查机器即把
用例的绿红交给 host 状态（BET-Y2Q4-T10-222 刚清掉的那一类）。
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".omo" / "cron" / "registry.yaml"

INSTALLED_REALITIES = {"installed", "crontab_installed"}
KNOWN_REALITIES = INSTALLED_REALITIES | {"declared_only", "pending"}
KNOWN_STATUSES = {"active", "proposed"}


class _DuplicateKeyLoader(yaml.SafeLoader):
    """SafeLoader 在解析阶段就折叠重复键，所以检测必须自己重放 mapping 构造。"""


def _construct_mapping(loader: _DuplicateKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    mapping: dict = {}
    duplicates: list[str] = []
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            duplicates.append(str(key))
        mapping[key] = loader.construct_object(value_node, deep=deep)
    if "name" in mapping:
        loader.job_duplications[str(mapping["name"])] = duplicates
    return mapping


_DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def _job_duplications(text: str) -> dict[str, list[str]]:
    loader = _DuplicateKeyLoader(text)
    loader.job_duplications = {}
    loader.get_single_data()
    return loader.job_duplications


def _jobs(text: str) -> list[dict]:
    return yaml.safe_load(text)["jobs"]


SOURCE = REGISTRY.read_text(encoding="utf-8")
JOBS = _jobs(SOURCE)


def _job(name: str) -> dict:
    return next(job for job in JOBS if job["name"] == name)


def test_registry_parses_and_keeps_every_job_key_in_known_vocabulary() -> None:
    assert JOBS, "registry 必须至少登记一条 job"
    assert {job["status"] for job in JOBS} <= KNOWN_STATUSES
    assert {job["reality"] for job in JOBS} <= KNOWN_REALITIES


def test_i3_no_job_record_has_duplicate_keys() -> None:
    offenders = {n: d for n, d in _job_duplications(SOURCE).items() if d}
    assert offenders == {}, f"重复键会被 PyYAML last-wins 静默折叠: {offenders}"


def test_i1_active_job_must_claim_an_installed_reality() -> None:
    offenders = [
        job["name"] for job in JOBS if job["status"] == "active"
        and job["reality"] not in INSTALLED_REALITIES
    ]
    assert offenders == [], f"status=active 却无装机证据的登记: {offenders}"


def test_i2_installed_reality_must_be_an_active_job() -> None:
    offenders = [
        job["name"] for job in JOBS
        if job["reality"] in INSTALLED_REALITIES and job["status"] != "active"
    ]
    assert offenders == [], f"proposed 却声称 installed 的登记: {offenders}"


def test_the_three_2026_10_04_measurements_are_encoded() -> None:
    """逐条向三探针实测纠偏：低报上修、高报降级、退役表达为 declared_only。"""
    assert _job("panorama-dashboard-refresh")["status"] == "active"
    assert _job("panorama-dashboard-refresh")["reality"] == "installed"

    retired = _job("panorama-dashboard")
    assert retired["status"] == "proposed"
    assert retired["reality"] == "declared_only"
    assert "sunset-redirector" in retired["reconciliation_note"]

    foundry = _job("knowledge-foundry-6h")
    assert foundry["status"] == "proposed"
    assert foundry["reality"] == "declared_only"
    assert "从未装机" in foundry["reconciliation_note"]


def test_resolved_ssot_conflicts_do_not_stay_declared() -> None:
    """ssot_conflict 的语义是「两面仍未收敛」，纠偏完成后必须撤键。"""
    resolved = ("panorama-dashboard", "panorama-dashboard-refresh")
    still_declared = [name for name in resolved if "ssot_conflict" in _job(name)]
    assert still_declared == []


def test_duplicate_key_detector_is_not_a_no_op() -> None:
    """变异对照：注入一条带两个 reality 的记录，检测器必须点名它。"""
    lines = SOURCE.splitlines(keepends=True)
    target = next(i for i, line in enumerate(lines) if line.startswith("    reality: "))
    injected = "    reality: injected_duplicate_probe\n"
    mutated = "".join(lines[: target + 1]) + injected + "".join(lines[target + 1:])

    offenders = {n: d for n, d in _job_duplications(mutated).items() if d}
    assert offenders, "重复键检测器空转：注入违规后仍未报"
    assert any("reality" in dup for dup in offenders.values()), offenders


def test_safe_load_alone_would_have_missed_that_violation() -> None:
    """反证重复键只能靠 dup-aware loader 发现：safe_load 会静默折叠它。"""
    lines = SOURCE.splitlines(keepends=True)
    target = next(i for i, line in enumerate(lines) if line.startswith("    reality: "))
    mutated = "".join(lines[: target + 1]) + "    reality: injected_duplicate_probe\n" + "".join(lines[target + 1:])

    jobs = _jobs(mutated)
    duplicated = [job for job in jobs if job["reality"] == "injected_duplicate_probe"]
    assert len(duplicated) == 1, "safe_load 应当只保留最后一个值"
    assert _job_duplications(mutated)[duplicated[0]["name"]] == ["reality"]


def test_registry_source_lock_has_no_host_literal() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    needle = "/Use" + "rs/"
    assert needle not in source
