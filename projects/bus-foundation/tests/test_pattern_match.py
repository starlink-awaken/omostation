"""Test shared pattern_match helper (R74 LOW fix)."""

from bus_foundation.backends.pattern_match import match_pattern


class TestPatternMatch:
    def test_catchall(self):
        assert match_pattern("*", "anything") is True
        assert match_pattern("*", "x:y:z") is True

    def test_exact(self):
        assert match_pattern("pipeline:completed", "pipeline:completed") is True
        assert match_pattern("pipeline:completed", "pipeline:failed") is False
        assert match_pattern("x", "y") is False

    def test_prefix(self):
        assert match_pattern("pipeline:*", "pipeline:completed") is True
        assert match_pattern("pipeline:*", "pipeline:failed") is True
        assert match_pattern("pipeline:*", "task:completed") is False

    def test_prefix_empty(self):
        # "x:*" should match anything starting with "x:"
        assert match_pattern("x:*", "x:") is True
        assert match_pattern("x:*", "y:x:") is False
