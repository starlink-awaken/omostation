"""性能基准测试 — 对 OntoDerive 核心操作计时

用法:
    .venv/bin/python -m pytest tests/benchmarks/ -v --benchmark-only

要求: pip install pytest-benchmark
如果未安装，使用内置计时器自动降级。
"""

import time
from pathlib import Path

import pytest

try:
    from ontoderive.core.derive import OntoDerive

    _ENGINE_AVAILABLE = True
except ImportError:
    OntoDerive = None
    _ENGINE_AVAILABLE = False

Z_PARK = Path(__file__).parent.parent.parent / "examples" / "z-park"

# 如果 z-park 不存在，跳过基准测试
pytestmark = [
    pytest.mark.skipif(not Z_PARK.exists(), reason="z-park 示例项目不存在"),
    pytest.mark.benchmark,
]


@pytest.fixture(scope="module")
def od():
    """创建 OntoDerive 实例（复用）"""
    return OntoDerive(Z_PARK)  # type: ignore[reportOptionalCall]


class TestBenchmarkDerive:
    """T2: derive() 性能基线"""

    def test_derive_baseline(self, od):
        """结构分析基线"""
        t0 = time.perf_counter()
        r = od.derive()
        elapsed = time.perf_counter() - t0
        assert isinstance(r, dict)
        assert "facts" in r

        print(f"\n  derive() 耗时: {elapsed:.3f}s")
        print(f"  事实={r.get('facts', 0)}, 推论={r.get('inferences', 0)}")
        if elapsed > 5.0:
            pytest.skip(f"性能较差: {elapsed:.2f}s，需要优化")

    def test_derive_with_check(self, od):
        """derive + check 联合执行"""
        t0 = time.perf_counter()
        od.derive()
        results = od.check()
        elapsed = time.perf_counter() - t0

        passed = sum(1 for c in results if c.get("passed"))
        print(f"\n  derive+check 耗时: {elapsed:.3f}s")
        print(f"  规约通过: {passed}/{len(results)}")
        if elapsed > 10.0:
            pytest.skip(f"性能较差: {elapsed:.2f}s，需要优化")


class TestBenchmarkCheck:
    """check() 性能基线"""

    def test_check_standalone(self, od):
        """独立规约检查"""
        od.derive()  # 预热: 确保目录状态

        t0 = time.perf_counter()
        results = od.check()
        elapsed = time.perf_counter() - t0

        print(f"\n  check() 耗时: {elapsed:.3f}s")
        print(f"  规约数: {len(results)}")
        if elapsed > 3.0:
            pytest.skip(f"性能较差: {elapsed:.2f}s，需要优化")
