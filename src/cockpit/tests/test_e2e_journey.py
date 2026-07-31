"""全链路 E2E 验证测试 — 模拟完整用户旅程。"""

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE_CMD = [sys.executable, "-m", "cockpit"]


def _cockpit(*args: str) -> subprocess.CompletedProcess:
    """Run workspace command and return result."""
    return subprocess.run(
        WORKSPACE_CMD + list(args),
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
        env={
            "PYTHONPATH": str(Path(__file__).resolve().parent.parent)
            + ":"
            + str(Path(__file__).resolve().parent.parent.parent)
        },
    )


class TestE2EJourney:
    """模拟用户完整旅程的 E2E 测试。"""

    def test_help_displays(self):
        """用户旅程 1: 查看帮助"""
        r = _cockpit("--help")
        assert r.returncode == 0
        assert "workspace" in r.stdout or "usage:" in r.stdout

    def test_profile_exists(self):
        """用户旅程 2: 查看身份档案"""
        r = _cockpit("profile")
        assert r.returncode == 0
        assert len(r.stdout) > 0

    def test_daily_displays(self):
        """用户旅程 3: 每日简报"""
        r = _cockpit("daily")
        assert r.returncode == 0

    def test_contracts_validate(self):
        """用户旅程 4: 契约验证"""
        r = _cockpit("contracts", "validate")
        assert r.returncode in (0, 2)  # 0=通过, 2=有错误

    def test_contracts_export_identity(self):
        """用户旅程 5: 导出身份封套"""
        r = _cockpit("contracts", "export", "identity")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["type"] == "identity_envelope"
        assert "profile" in data

    def test_contracts_list(self):
        """用户旅程 6: 列出契约"""
        r = _cockpit("contracts", "list")
        assert r.returncode == 0

    def test_product_health(self):
        """用户旅程 7: 产品健康度"""
        r = _cockpit("product-health")
        assert r.returncode == 0
        assert "Product Health Score:" in r.stdout

    def test_research_heatmap(self):
        """用户旅程 8: 研究热力图"""
        r = _cockpit("research", "--heatmap")
        assert r.returncode == 0

    def test_research_list(self):
        """用户旅程 9: 研究列表"""
        r = _cockpit("research", "--list")
        assert r.returncode == 0

    def test_status_workbench(self):
        """用户旅程 10: 工作台状态"""
        r = _cockpit("status")
        assert r.returncode == 0
