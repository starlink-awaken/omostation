from mos.eval_harness import run_eval


def test_eval_harness_high_score():
    report = run_eval()
    assert report.total == 15
    # Intent + roundtrip + forget should mostly pass on pure MemoryOS
    assert report.score >= 0.8, report.to_dict()
    assert report.passed >= 12
