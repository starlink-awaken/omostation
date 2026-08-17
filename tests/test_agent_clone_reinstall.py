#!/usr/bin/env python3
"""Test agent-clone.py uv path dependency reinstall (E8 fix).

最小测试：mock subprocess.run 验证 reinstall 命令被构造（不真跑 uv）。
"""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest


# 动态导入 agent_clone（从 bin/gac/ 目录）
def _import_agent_clone():
    import importlib.util

    bin_path = os.path.join(os.path.dirname(__file__), "..", "bin", "gac", "agent-clone.py")
    spec = importlib.util.spec_from_file_location("agent_clone", bin_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent_clone = _import_agent_clone()


class TestExtractUVPathDependencies:
    """测试 [tool.uv.sources] 解析逻辑."""

    def test_no_pyproject(self, tmp_path):
        """没有 pyproject.toml 时返回空列表。"""
        assert agent_clone.extract_uv_path_dependencies(str(tmp_path)) == []

    def test_empty_pyproject(self, tmp_path):
        """空 pyproject.toml 返回空列表。"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("")
        assert agent_clone.extract_uv_path_dependencies(str(tmp_path)) == []

    def test_no_uv_section(self, tmp_path):
        """pyproject.toml 没有 [tool.uv.sources] 时返回空列表。"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "0.1.0"

[tool.uv]
dev-dependencies = []
""")
        assert agent_clone.extract_uv_path_dependencies(str(tmp_path)) == []

    def test_single_path_dep(self, tmp_path):
        """单个 path 依赖。"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.uv.sources]
ecos = { path = "../ecos" }
""")
        result = agent_clone.extract_uv_path_dependencies(str(tmp_path))
        assert result == ["ecos"]

    def test_multiple_path_deps(self, tmp_path):
        """多个 path 依赖（模拟 projects/omo 的真实配置）。"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.uv.sources]
aetherforge = { path = "../aetherforge", editable = true }
agora = { path = "../agora", editable = true }
bus-foundation = { path = "../bus-foundation" }
ecos = { path = "../ecos" }
l4-kernel = { path = "../l4-kernel" }
""")
        result = agent_clone.extract_uv_path_dependencies(str(tmp_path))
        assert set(result) == {
            "aetherforge",
            "agora",
            "bus-foundation",
            "ecos",
            "l4-kernel",
        }

    def test_uv_section_end_detection(self, tmp_path):
        """验证离开 [tool.uv.sources] 后停止解析。"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.uv.sources]
ecos = { path = "../ecos" }

[tool.ruff]
line-length = 100
""")
        result = agent_clone.extract_uv_path_dependencies(str(tmp_path))
        assert result == ["ecos"]


class TestReinstallPathDependencies:
    """测试 uv sync --reinstall-package 调用逻辑."""

    def test_no_path_deps(self, tmp_path):
        """没有 path 依赖时直接返回成功，不调用 uv。"""
        ok, msg = agent_clone.reinstall_path_dependencies(str(tmp_path))
        assert ok is True
        assert "no uv path dependencies" in msg

    def test_uv_not_available(self, tmp_path):
        """有 path 依赖但 uv 不可用时返回失败但不抛异常。"""
        # 先写一个有 path 依赖的 pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.uv.sources]
ecos = { path = "../ecos" }
""")

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if cmd[0] == "uv" and cmd[1] == "--version":
                raise FileNotFoundError("uv not found")
            return MagicMock(returncode=0, stdout="")

        with patch.object(subprocess, "run", side_effect=side_effect):
            ok, msg = agent_clone.reinstall_path_dependencies(str(tmp_path))
            assert ok is False
            assert "uv not available" in msg.lower() or "uv command not found" in msg.lower()

    def test_successful_reinstall(self, tmp_path):
        """成功 reinstall 多个包。"""
        # 写入 pyproject.toml
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.uv.sources]
ecos = { path = "../ecos" }
agora = { path = "../agora" }
""")

        with patch.object(subprocess, "run") as mock_run:
            # uv --version 成功
            mock_run.return_value = MagicMock(returncode=0, stdout="uv 0.1.0")

            ok, msg = agent_clone.reinstall_path_dependencies(str(tmp_path))

            assert ok is True
            assert "reinstalled 2" in msg
            assert "ecos" in msg
            assert "agora" in msg

            # 验证 uv --version 被调用
            assert mock_run.call_count >= 3  # --version + sync ecos + sync agora

    def test_reinstall_partial_failure(self, tmp_path):
        """部分包 reinstall 失败时返回 warning 但不抛异常。"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.uv.sources]
ecos = { path = "../ecos" }
agora = { path = "../agora" }
""")

        with patch.object(subprocess, "run") as mock_run:

            def side_effect(*args, **kwargs):
                cmd = args[0]
                if cmd[0] == "uv" and cmd[1] == "--version":
                    return MagicMock(returncode=0, stdout="uv 0.1.0")
                if "ecos" in cmd:
                    return MagicMock(returncode=0, stdout="", stderr="")
                if "agora" in cmd:
                    return MagicMock(returncode=1, stderr="package not found")
                return MagicMock(returncode=0)

            mock_run.side_effect = side_effect

            ok, msg = agent_clone.reinstall_path_dependencies(str(tmp_path))

            assert ok is False
            assert "failed for:" in msg
            assert "agora" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
