"""Reserved real-hardware smoke suite.

Task 2 intentionally has no backend implementation, so this opt-in suite must
not contact hardware yet.
"""

import pytest

pytestmark = pytest.mark.hardware


def test_hardware_smoke_is_reserved_for_an_explicit_future_request() -> None:
    """Keep real-device access opt-in until a future task implements it."""
    pytest.skip("Task 2 has no real-hardware smoke implementation")
