"""
Workspace Tools — omostation/eCOS v6 统一工具层
提供跨域共享的控制器、提取器、预测器基类
"""
from .base_controller import BaseController
from .base_extractor import BaseExtractor
from .base_predictor import BasePredictor

__all__ = ["BaseController", "BaseExtractor", "BasePredictor"]
