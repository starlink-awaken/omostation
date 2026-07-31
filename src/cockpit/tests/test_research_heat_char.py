"""测试 research._heat_char — 研究热力图中的活跃度字符渲染。

函数定义：
    def _heat_char(val: int, max_val: int) -> str:
        if val == 0:             → "[dim]·[/]"
        ratio = val / max(1, max_val)
        if ratio > 0.5:          → f"[red]{val}[/]"     (高)
        elif ratio > 0.2:        → f"[yellow]{val}[/]"  (中)
        else:                    → f"[green]{val}[/]"   (低)
"""

from __future__ import annotations

from cockpit.commands.research import _heat_char


class TestHeatChar:
    """_heat_char 的 4 条分支测试。"""

    def test_zero(self):
        """val==0 → dim 占位符"""
        assert _heat_char(0, 10) == "[dim]·[/]"

    def test_high(self):
        """ratio > 0.5 → red"""
        assert _heat_char(6, 10) == "[red]6[/]"

    def test_medium(self):
        """0.2 < ratio <= 0.5 → yellow"""
        assert _heat_char(3, 10) == "[yellow]3[/]"

    def test_low(self):
        """ratio <= 0.2 → green"""
        assert _heat_char(1, 10) == "[green]1[/]"

    def test_max_val_zero(self):
        """max_val==0 边界→分母取 1→val/1"""
        assert _heat_char(0, 0) == "[dim]·[/]"
        assert _heat_char(1, 0) == "[red]1[/]"

    def test_exact_boundaries(self):
        """边界值测试"""
        # ratio == 0.5 → yellow (not > 0.5, but > 0.2)
        assert _heat_char(5, 10) == "[yellow]5[/]"
        # ratio == 0.2 → green (not > 0.2)
        assert _heat_char(2, 10) == "[green]2[/]"
