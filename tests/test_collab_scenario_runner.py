"""P84 W1 协作场景库 runner 测试.

验证 (P84 W1.1 验收三要件):
- 复现性: 同 seed 同结果
- verdict 机器可读: JSON 可序列化
- 四大类覆盖 + silent_loss 红线判定存在 + 全样例可跑
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "bin" / "collab"))
from scenario_lib import load_scenario, run_scenario  # noqa: E402

SCN_DIR = REPO / ".omo" / "_delivery" / "collab-scenarios"


def test_reproducibility_same_seed_same_result() -> None:
    """同 seed 同结果 (P84 W1.1 验收: 场景可复现)."""
    sc = load_scenario(SCN_DIR / "A01-product-divergence.yaml")
    r1 = run_scenario(sc)
    r2 = run_scenario(sc)
    assert r1.passed == r2.passed
    assert r1.events == r2.events
    assert r1.resolution_rounds == r2.resolution_rounds
    assert r1.silent_loss == r2.silent_loss


def test_verdict_machine_readable() -> None:
    """verdict 机器可读 (P84 W1.1 验收: 判定准则机器可读)."""
    sc = load_scenario(SCN_DIR / "B01-role-timeout.yaml")
    r = run_scenario(sc)
    d = r.to_dict()
    json.dumps(d)  # 不抛异常 = 可序列化
    assert "criteria" in d
    assert all("passed" in c and "evidence" in c for c in d["criteria"])


def test_four_categories_covered() -> None:
    """四大类各 ≥1 样例 (A/B/C/D 全覆盖)."""
    cats = set()
    for p in sorted(SCN_DIR.glob("*.yaml")):
        sc = load_scenario(p)
        cats.add(sc["category"])
    assert cats == {"A_conflict", "B_failure_injection", "C_decomposition", "D_reuse_pair"}


def test_silent_loss_redline_present() -> None:
    """所有样例须含 silent_loss 红线判定 (P84 硬红线 = 0)."""
    for p in sorted(SCN_DIR.glob("*.yaml")):
        sc = load_scenario(p)
        has_silent = any(
            "silent" in c["criterion"].lower() or "loss" in c["criterion"].lower()
            for c in sc["verdict"]
        )
        assert has_silent, f"{p.name}: 缺 silent_loss 红线判定"


def test_all_samples_runnable() -> None:
    """全样例可跑 (load + run 不抛)."""
    for p in sorted(SCN_DIR.glob("*.yaml")):
        sc = load_scenario(p)
        r = run_scenario(sc)
        assert r.scenario_id  # 真有结果非空壳


def test_expected_pass_for_well_formed_samples() -> None:
    """良构样例 (非对抗) 应通过 (验证判定逻辑正确, 非放宽). 对抗场景另测."""
    for p in sorted(SCN_DIR.glob("*.yaml")):
        sc = load_scenario(p)
        if sc.get("adversarial"):
            continue  # 对抗场景允许失败, 另测
        r = run_scenario(sc)
        assert r.passed, f"{p.name}: 良构样例应通过, 失败准则 = {[c.name for c in r.criteria if not c.passed]}"


def test_adversarial_at_least_3_fail() -> None:
    """对抗场景至少 3 个真的让管线失败 (P84 W1.2: 全过=对抗不足须加强).

    W2.2 闭环 (ADR-0254): C/S 类 (double_claim/partial/starvation/orphan/…) 已修转 ✅;
    新对抗 ADV13/15/17 (collusion/priority_inversion/cascade) 保持 ≥3 失败.
    对抗集持续进化: 修一批 + 加一批, 永不"全过".
    """
    results: list[tuple[str, bool]] = []
    for p in sorted(SCN_DIR.glob("*.yaml")):
        sc = load_scenario(p)
        if not sc.get("adversarial"):
            continue
        r = run_scenario(sc)
        results.append((sc["id"], r.passed))
    failed = [sid for sid, ok in results if not ok]
    assert len(failed) >= 3, (
        f"对抗场景仅 {len(failed)} 个失败 (<3), 对抗性不足须加强: {results}"
    )


def test_cclass_detectors_pass() -> None:
    """C 类真缺陷检测已实现 (double_claim / partial_failure / starvation)."""
    for name in (
        "ADV07-double-claim.yaml",
        "ADV09-partial-failure.yaml",
        "ADV11-resource-starvation.yaml",
    ):
        sc = load_scenario(SCN_DIR / name)
        r = run_scenario(sc)
        assert r.passed, f"{name} should pass after ADR-0254: {[c for c in r.criteria if not c.passed]}"


def test_wave6_adv252729_detectors_pass() -> None:
    """wave6 闭环: split_brain / identity_spoof / supply_chain_tamper."""
    for name in (
        "ADV25-split-brain-partition.yaml",
        "ADV27-identity-spoof.yaml",
        "ADV29-supply-chain-tamper.yaml",
    ):
        sc = load_scenario(SCN_DIR / name)
        r = run_scenario(sc)
        assert r.passed, (
            f"{name} should pass after wave6 detectors: "
            f"{[c.name for c in r.criteria if not c.passed]}"
        )


def test_wave7_adv313335_detectors_pass() -> None:
    """wave7 闭环: sybil_flood / time_travel / quorum_eclipse."""
    for name in (
        "ADV31-sybil-flood.yaml",
        "ADV33-time-travel-write.yaml",
        "ADV35-quorum-eclipse.yaml",
    ):
        sc = load_scenario(SCN_DIR / name)
        r = run_scenario(sc)
        assert r.passed, (
            f"{name} should pass after wave7 detectors: "
            f"{[c.name for c in r.criteria if not c.passed]}"
        )


def test_wave8_adv373941_detectors_pass() -> None:
    """wave8 闭环: clock_skew / ghost_writer / double_spend."""
    for name in (
        "ADV37-eclipse-clock-skew.yaml",
        "ADV39-ghost-writer.yaml",
        "ADV41-double-spend-claim.yaml",
    ):
        sc = load_scenario(SCN_DIR / name)
        r = run_scenario(sc)
        assert r.passed, (
            f"{name} should pass after wave8 detectors: "
            f"{[c.name for c in r.criteria if not c.passed]}"
        )


def test_wave9_adv434547_detectors_pass() -> None:
    """wave9 闭环: equivocation / long_range_rewrite / censorship_gap."""
    for name in (
        "ADV43-equivocation.yaml",
        "ADV45-long-range-rewrite.yaml",
        "ADV47-censorship-gap.yaml",
    ):
        sc = load_scenario(SCN_DIR / name)
        r = run_scenario(sc)
        assert r.passed, (
            f"{name} should pass after wave9 detectors: "
            f"{[c.name for c in r.criteria if not c.passed]}"
        )


def test_wave10_adv495153_detectors_pass() -> None:
    """wave10 闭环: vote_buying / stake_grinding / nothing_at_stake."""
    for name in (
        "ADV49-vote-buying.yaml",
        "ADV51-stake-grinding.yaml",
        "ADV53-nothing-at-stake.yaml",
    ):
        sc = load_scenario(SCN_DIR / name)
        r = run_scenario(sc)
        assert r.passed, (
            f"{name} should pass after wave10 detectors: "
            f"{[c.name for c in r.criteria if not c.passed]}"
        )


def test_wave11_adv555759_detectors_pass() -> None:
    """wave11 闭环: front_running / griefing_abort / oracle_manipulation."""
    for name in (
        "ADV55-front-running.yaml",
        "ADV57-griefing-abort.yaml",
        "ADV59-oracle-manipulation.yaml",
    ):
        sc = load_scenario(SCN_DIR / name)
        r = run_scenario(sc)
        assert r.passed, (
            f"{name} should pass after wave11 detectors: "
            f"{[c.name for c in r.criteria if not c.passed]}"
        )


def test_wave11_hard_adv_still_fail() -> None:
    """ADV61/63/65 加硬场景须失败 (对抗强度)."""
    for name in (
        "ADV61-sandwich-attack.yaml",
        "ADV63-reentrancy.yaml",
        "ADV65-mev-leak.yaml",
    ):
        sc = load_scenario(SCN_DIR / name)
        r = run_scenario(sc)
        assert not r.passed, f"{name} must remain failing hard-adv (got PASS)"


def test_adversarial_ratio_ge_20pct() -> None:
    """对抗集占库 ≥20% (P84 W1.2)."""
    all_sc = [load_scenario(p) for p in sorted(SCN_DIR.glob("*.yaml"))]
    total = len(all_sc)
    adv = sum(1 for sc in all_sc if sc.get("adversarial"))
    assert total > 0
    assert adv / total >= 0.20, f"对抗集 {adv}/{total} = {adv / total:.0%} < 20%"
