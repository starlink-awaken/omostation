"""Voice recognition data models — extracted from SharedBrain D_Voice."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LanguageCode(StrEnum):
    EN = "en"
    ZH = "zh"
    JP = "ja"
    DE = "de"
    FR = "fr"
    ES = "es"
    AUTO = "auto"


@dataclass
class RecognitionResult:
    text: str
    language: str
    confidence: float
    duration: float
    segments: list[dict]
    is_final: bool = True


@dataclass
class RecognitionConfig:
    language: LanguageCode = LanguageCode.AUTO
    model_size: str = "base"
    device: str = "cpu"
    enable_timestamps: bool = True
    enable_punctuation: bool = True
