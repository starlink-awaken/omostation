"""tests/unit 的 host 字面量只准留在声明过的合法位置 (BET-Y2Q4-T10-245 / ADR-0456 B4b 前置).

尺与 spec §1 一致：全量递归扫 `tests/unit/**/*.py` 找本机用户目录绝对路径 (HOST_LITERAL)，不挑文件。
「改前 13 → 改后 3」的差分由交付时在同一把尺上的对照树扫描产出 (见 closeout receipt)；
本用例钉住改后终态，挡三类漂移：新增 host 字面量、把脱敏用例的输入前提「顺手清理」掉、
以及镜像用例退回写字面量而不是从 registry / home 派生。
"""
from pathlib import Path

TESTS_UNIT = Path(__file__).resolve().parent
# 拼接而非字面量：检测器一旦内含自己的针就得把自己从被扫集合里摘出去，那是收窄断言。
# 写成拼接后本文件仍留在被扫集合内 —— 谁在这里加字面量，当场自曝。
HOST_LITERAL = "/Users/" + "xiamingxing"

# spec §1 表：这 3 处命中是合法前提，不是待收敛的锚点
# - test_service_interpreter_stability.py:11  模块 docstring 叙述一次 uv 构建伪影，不参与断言
# - test_spine_diff_adaptation.py:35,42        脱敏用例要求输入含真实用户名形状路径，才能证 REDACTED 生效
LEGITIMATE_HITS = frozenset(
    {
        ("test_service_interpreter_stability.py", 11),
        ("test_spine_diff_adaptation.py", 35),
        ("test_spine_diff_adaptation.py", 42),
    }
)

MIRROR_TESTS = (
    "test_agent_cell_semantic_scheduler.py",
    "test_reference_cell_direct_local_schedule.py",
)


def _hits(root: Path) -> frozenset:
    found = set()
    for path in sorted(root.rglob("*.py")):
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if HOST_LITERAL in line:
                found.add((path.name, number))
    return frozenset(found)


def test_detector_is_not_a_no_op(tmp_path):
    """合成违规样本自证：检测器必须点名它，否则「0 命中」可能只是压根没命中。"""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "bad.py").write_text(
        f'X = Path("{HOST_LITERAL}/Workspace")\n', encoding="utf-8"
    )
    assert _hits(tmp_path) == frozenset({("bad.py", 1)})


def test_host_literals_are_confined_to_declared_legitimate_sites():
    assert _hits(TESTS_UNIT) == LEGITIMATE_HITS


def test_legitimate_sites_still_present_and_in_the_right_shape():
    """反向钉住：删掉这 3 处 ⇒ 当场红，挡住「顺手清理」把脱敏用例的前提一起扫掉。"""
    spine = (TESTS_UNIT / "test_spine_diff_adaptation.py").read_text(encoding="utf-8")
    assert f"{HOST_LITERAL}/confidential.md" in spine
    assert f'assert "{HOST_LITERAL}/" not in cleaned' in spine
    stability = (TESTS_UNIT / "test_service_interpreter_stability.py").read_text(encoding="utf-8")
    assert f"{HOST_LITERAL}/.cache/uv/builds-v0/" in stability


def test_mirror_tests_derive_expectations_instead_of_writing_them():
    for name in MIRROR_TESTS:
        source = (TESTS_UNIT / name).read_text(encoding="utf-8")
        assert HOST_LITERAL not in source, f"{name} 退回 host 字面量"
        assert ".omo/_truth/registry/services.yaml" in source, f"{name} 不再读 registry"


def test_home_composition_is_confined_to_declared_sites():
    """`$HOME` 组合点数逐文件钉死：reference-cell 3 处、agent-cell 0 处。

    registry 不声明 PATH / EnvironmentVariables（实测 .omo/cron/registry.yaml 无该键），
    所以 reference-cell 那 3 处只能由 `Path.home()` 组合 —— 它们是本轮唯一面向 host 的面。
    在 HOME=<空目录> 下这 3 处转红是**正确读数**（基线字面量在那里是假绿），
    点数钉死可挡住两件事：往 agent-cell 塞 home 组合，或用撤销这 3 处来「修好」敌意 HOME 读数。
    """
    counts = {
        name: (TESTS_UNIT / name).read_text(encoding="utf-8").count("str(HOME")
        for name in MIRROR_TESTS
    }
    assert counts == {
        "test_agent_cell_semantic_scheduler.py": 0,
        "test_reference_cell_direct_local_schedule.py": 3,
    }, counts
    reference = (TESTS_UNIT / "test_reference_cell_direct_local_schedule.py").read_text(
        encoding="utf-8"
    )
    assert "HOME = Path.home()" in reference
