"""AdmissionPort SPI — I0 准入契约面 (方案 C / ADR-0181).

L0 只声明义务: 注册前必须 admission.evaluate(...).status == admitted.
实现由 SPI 绑定 (entry point / 可选 lazy provider)，不点名 metaos 类路径。
"""

from __future__ import annotations

from agora.admission.port import (
    AdmissionPort,
    AdmissionRequest,
    AdmissionResult,
    evaluate_admission,
    get_admission_provider,
    reset_admission_provider_cache,
)

__all__ = [
    "AdmissionPort",
    "AdmissionRequest",
    "AdmissionResult",
    "evaluate_admission",
    "get_admission_provider",
    "reset_admission_provider_cache",
]
