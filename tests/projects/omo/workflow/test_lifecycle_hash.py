import pytest

# omo 包需在 sys.path 上 (CI 的 `uv run pytest` 在 projects/omo/ 下运行, 主仓侧不经
# PYTHONPATH 注入)。主仓根 `pyproject.toml` 的 pythonpath 只含根 src/, 故直接
# 从主仓跑本文件会 collection error 并中断整个 pytest 运行 —— 缺依赖时优雅跳过。
try:
    from omo.workflow.lifecycle import WorkflowError, claim_run
except ImportError as exc:  # pragma: no cover - 环境相关
    pytest.skip(f"omo 不可用: {exc}", allow_module_level=True)


def test_claim_run_requires_existing_run(tmp_path):
    with pytest.raises(WorkflowError, match="run not found"):
        claim_run(
            {},
            "run123",
            "test_actor",
            ["projects/knowledge/gbrain"],
            [],
            False,
            affected_receipt=None,
        )
