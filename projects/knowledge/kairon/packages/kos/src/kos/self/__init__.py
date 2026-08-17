"""KOS Self Domain — L4 自我层：身份画像、愿景系统、价值原则、认知框架。"""

from kos.self.api import (  # type: ignore[import-not-found]
    get_current_role,
    get_profile,
    get_profile_history,
    get_vision_summary,
    update_profile,
)

__all__ = [
    "get_profile",
    "update_profile",
    "get_current_role",
    "get_vision_summary",
    "get_profile_history",
]
