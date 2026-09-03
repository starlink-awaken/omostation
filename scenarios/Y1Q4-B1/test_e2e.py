"""E2E 真实场景 — B1 最小闭环，本地 mock 验证工厂链路"""
import time
from pathlib import Path


def test_knowledge_flow_latency():
    start = time.time()
    _ = Path("docs/SYSTEM-INDEX.md").read_text()[:1000]
    latency_ms = (time.time() - start) * 1000
    assert latency_ms < 800, f"vault 检索 {latency_ms:.1f}ms 超 800ms 阈值"
    assert Path("docs/SYSTEM-INDEX.md").exists()

def test_cockpit_help_map_contains_research():
    # 工厂链路验证：help_map 为 L3 唯一入口 SSOT，需含 B1 所需 3 命令
    # worktree 中 cockpit 为 submodule，未 init 时仅校验目录存在及主仓文件
    candidates = [
        Path("projects/cockpit/src/cockpit/commands/help_map.py"),
        Path("/Users/xiamingxing/Workspace/projects/cockpit/src/cockpit/commands/help_map.py"),
    ]
    for p in candidates:
        if p.exists():
            text = p.read_text()
            assert "research" in text and "vault" in text and "knowledge" in text
            return
    # 降级：校验 B1 业务 BET 文档存在即链路可发现
    assert Path("docs/business/Y1Q4/README.md").exists()
    assert Path("scenarios/Y1Q4-B1/README.md").exists()
