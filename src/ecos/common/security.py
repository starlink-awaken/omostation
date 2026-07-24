"""ECOS 安全工具"""

import hashlib
import hmac
from typing import Any, Optional


class TokenManager:
    """Token 管理器"""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()

    def generate_token(self, user_id: str, expires_in: int = 3600) -> str:
        payload = f"{user_id}:{expires_in}"
        signature = hmac.new(
            self.secret_key, payload.encode(), hashlib.sha256
        ).hexdigest()
        return f"{payload}:{signature}"

    def verify_token(self, token: str) -> Optional[str]:
        try:
            parts = token.split(":")
            if len(parts) != 3:
                return None
            user_id, expires_in, signature = parts
            payload = f"{user_id}:{expires_in}"
            expected = hmac.new(
                self.secret_key, payload.encode(), hashlib.sha256
            ).hexdigest()
            if signature == expected:
                return user_id
        except Exception:  # defensive fallback
            pass
        return None


class InputValidator:
    """输入参数校验器"""

    @staticmethod
    def validate_string(
        value: Any, min_length: int = 0, max_length: int = 1000
    ) -> bool:
        if not isinstance(value, str):
            return False
        return min_length <= len(value) <= max_length

    @staticmethod
    def validate_number(
        value: Any, min_val: float = float("-inf"), max_val: float = float("inf")
    ) -> bool:
        if not isinstance(value, (int, float)):
            return False
        return min_val <= value <= max_val

    @staticmethod
    def validate_dict(value: Any, required_keys: list[str] | None = None) -> bool:
        if not isinstance(value, dict):
            return False
        if required_keys:
            return all(key in value for key in required_keys)
        return True
