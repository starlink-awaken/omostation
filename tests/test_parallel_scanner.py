"""测试 ParallelScanner"""

from pathlib import Path
from tempfile import TemporaryDirectory

from omo.parallel_scanner import ParallelScanner


def test_scan_simple():
    with TemporaryDirectory() as tmpdir:
        for i in range(5):
            (Path(tmpdir) / f"file{i}.txt").write_text(f"test{i}")

        scanner = ParallelScanner(max_workers=2)

        def simple_scan(path):
            return [{"file": str(path), "len": len(path.read_text())}]

        paths = list(Path(tmpdir).glob("*.txt"))
        results = scanner.scan_with_workers(paths, simple_scan)

        assert len(results) == 5
        assert all(r.success for r in results)


def test_aggregate():
    from omo.parallel_scanner import ScanResult

    scanner = ParallelScanner()

    results = [
        ScanResult("a", True, [{"f": 1}], [], 0.1),
        ScanResult("b", False, [], ["error"], 0.2),
    ]
    agg = scanner.aggregate_findings(results)
    assert agg["success_count"] == 1
    assert agg["failure_count"] == 1
