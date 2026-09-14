from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import concurrent.futures
import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# TODO-migrate: import nucleus.Z_Microkernel.organs.organ_protocol as organ_protocol

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ Output_Reshaper
# 内涵 ≝ {Compression, Truncation, Token_Estimation}
# 外延 ≝ {r | r ∈ Z-Microkernel ∧ reshapes(r, Output)}
# 功能 ⊢ {ReshapeOutput, CompressWithLLM, SmartTruncate, EstimateTokens}
# =============================================================================

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-01_prime_axiom.md
Layer: L3
Constraint: "[!!] TOKEN_AWARE_OUTPUT_RESHAPING_WITH_LLM_FALLBACK"
Summary: "输出重塑器 - 智能压缩和截断长输出，优化token使用"
Tags:
- output
- compression
- token
- llm
- truncation
---
"""
# 🔄 输出重塑器 (Output Reshaper - OR-01) v1.0.0
# 职责: 自动检测输出长度，选择最优策略进行压缩或截断，确保高效token使用
# 策略:
#   PASSTHROUGH      — 直接透传（短输出）
#   LLM_COMPRESSION  — 使用LLM智能压缩（中等长度）
#   SMART_TRUNCATE   — 智能截断保留关键信息（超长输出）

_log = logging.getLogger(__name__)


# =============================================================================
# 1. 常量定义
# =============================================================================

TOKEN_THRESHOLD = 2000  # Token阈值，低于此值直接透传
TRUNCATE_THRESHOLD = 5000  # 截断阈值，高于此值使用智能截断
MAX_OUTPUT_TOKENS = 500  # LLM压缩后的最大输出token数
LLM_TIMEOUT = 0.5  # 500ms = 0.5s

ERROR_KEYWORDS = ["error", "exception", "failed", "failure", "traceback", "fatal", "panic"]


# =============================================================================
# 2. 枚举与数据类
# =============================================================================


class Strategy(Enum):
    """输出重塑策略枚举"""

    PASSTHROUGH = "passthrough"  # 直接透传
    LLM_COMPRESSION = "llm_compression"  # LLM智能压缩
    SMART_TRUNCATE = "smart_truncate"  # 智能截断


@dataclass
class ReshapeResult:
    """重塑结果数据类"""

    compressed_output: str  # 压缩后的输出
    strategy_used: Strategy  # 使用的策略
    confidence: float  # 压缩置信度 (0.0 - 1.0)
    original_tokens: int = 0  # 原始token数
    compressed_tokens: int = 0  # 压缩后token数
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外元数据


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""

    total_calls: int = 0
    passthrough_count: int = 0
    llm_compression_count: int = 0
    smart_truncate_count: int = 0
    llm_timeout_count: int = 0
    llm_fallback_count: int = 0
    total_processing_time_ms: float = 0.0
    avg_processing_time_ms: float = 0.0


# =============================================================================
# 3. 工具函数
# =============================================================================


def estimate_tokens(text: str, method: str = "approximation") -> int:
    """
    估算文本的token数量

    Args:
        text: 待估算的文本
        method: 估算方法 ("approximation" | "character" | "word")

    Returns:
        估算的token数量

    Note:
        - approximation: 使用经验公式 (中文1字≈1token, 英文4字符≈1token)
        - character: 简单字符数/4
        - word: 词数*1.3
    """
    if not text:
        return 0

    if method == "character":
        return len(text) // 4

    if method == "word":
        words = len(text.split())
        return int(words * 1.3)

    # approximation (默认) - 更精确的中英文混合估算
    # 中文、日文、韩文字符
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]", text))
    # 英文单词
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    # 其他字符（标点、数字等）
    other_chars = len(text) - cjk_chars - sum(len(w) for w in re.findall(r"[a-zA-Z]+", text))

    # CJK字符 ≈ 1 token, 英文单词 ≈ 1.3 tokens, 其他 ≈ 0.25 token/char
    estimated = cjk_chars + int(english_words * 1.3) + (other_chars // 4)

    return max(1, estimated)


# =============================================================================
# 4. 主类实现
# =============================================================================


class OutputReshaper:
    """
    输出重塑器 - 智能压缩和截断长输出

    根据输出长度自动选择最优策略:
    1. PASSTHROUGH: 短输出直接透传 (< TOKEN_THRESHOLD)
    2. LLM_COMPRESSION: 中等输出使用LLM压缩 (TOKEN_THRESHOLD ~ TRUNCATE_THRESHOLD)
    3. SMART_TRUNCATE: 超长输出智能截断 (> TRUNCATE_THRESHOLD)

    LLM压缩支持超时和自动降级到智能截断
    """

    def __init__(
        self,
        llm_provider: Callable[[str], str] | None = None,
        token_threshold: int = TOKEN_THRESHOLD,
        truncate_threshold: int = TRUNCATE_THRESHOLD,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
        llm_timeout: float = LLM_TIMEOUT,
        enable_metrics: bool = True,
    ) -> None:
        """
        初始化输出重塑器

        Args:
            llm_provider: LLM调用函数，接收prompt返回压缩结果
            token_threshold: 透传阈值（低于此值不处理）
            truncate_threshold: 截断阈值（高于此值直接使用智能截断）
            max_output_tokens: LLM压缩后的最大token数
            llm_timeout: LLM调用超时时间（秒）
            enable_metrics: 是否启用性能监控
        """
        self.metadata_path = "nucleus/Z-Microkernel/organs/output_reshaper.py"
        self.organ_name = "OutputReshaper"
        self.organ_id = f"OR-{id(self):x}"
        self.status = "INITIALIZING"

        # 配置参数
        self.llm_provider = llm_provider
        self.token_threshold = token_threshold
        self.truncate_threshold = truncate_threshold
        self.max_output_tokens = max_output_tokens
        self.llm_timeout = llm_timeout
        self.enable_metrics = enable_metrics

        # 性能监控
        self._metrics = PerformanceMetrics()
        self._metrics_lock = threading.Lock()

        # 运行时状态
        self._initialized = False

        # 默认LLM提示模板
        self._compression_prompt_template = (
            "请压缩以下输出内容，保留关键信息，"
            "去除冗余细节。直接返回压缩后的内容，"
            "不要添加解释。内容:\n\n{content}\n\n"
            "压缩结果（不超过{max_tokens} tokens）:"
        )

        # 初始化完成
        self.status = "ACTIVE"
        self._initialized = True

    # -------------------------------------------------------------------------
    # IOrgan 接口实现
    # -------------------------------------------------------------------------

    def initialize(self) -> None:
        """初始化器官"""
        self.status = "ACTIVE"
        self._initialized = True

    def shutdown(self) -> None:
        """关闭器官"""
        self.status = "SHUTDOWN"
        self._initialized = False

    # -------------------------------------------------------------------------
    # 核心功能方法
    # -------------------------------------------------------------------------

    def reshape(
        self,
        output: str,
        context: dict[str, Any] | None = None,
        force_strategy: Strategy | None = None,
    ) -> ReshapeResult:
        """
        主入口方法 - 重塑输出

        Args:
            output: 原始输出内容
            context: 上下文信息（用于LLM压缩时提供额外背景）
            force_strategy: 强制使用指定策略（默认自动选择）

        Returns:
            ReshapeResult: 重塑结果
        """
        start_time = time.time()
        context = context or {}

        # 估算原始token数
        original_tokens = estimate_tokens(output)

        # 确定策略
        if force_strategy:
            strategy = force_strategy
        else:
            strategy = self._select_strategy(output, original_tokens)

        # 执行对应策略
        try:
            if strategy == Strategy.PASSTHROUGH:
                result = self._passthrough(output, original_tokens)
            elif strategy == Strategy.LLM_COMPRESSION:
                result = self._compress_with_llm(output, context, original_tokens)
            else:  # SMART_TRUNCATE
                result = self._smart_truncate(output, original_tokens)
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            # 任何异常都降级到智能截断
            result = self._fallback_to_truncate(output, original_tokens, str(e))

        # 计算处理时间
        processing_time = (time.time() - start_time) * 1000  # ms

        # 更新性能指标
        if self.enable_metrics:
            self._update_metrics(strategy, processing_time)

        # 添加处理时间到元数据
        result.metadata["processing_time_ms"] = round(processing_time, 2)
        result.metadata["original_tokens"] = original_tokens

        return result

    def _select_strategy(self, output: str, token_count: int) -> Strategy:
        """根据token数选择最优策略"""
        if token_count < self.token_threshold:
            return Strategy.PASSTHROUGH
        elif token_count < self.truncate_threshold and self.llm_provider:
            return Strategy.LLM_COMPRESSION
        else:
            return Strategy.SMART_TRUNCATE

    def _passthrough(self, output: str, original_tokens: int) -> ReshapeResult:
        """直接透传策略"""
        return ReshapeResult(
            compressed_output=output,
            strategy_used=Strategy.PASSTHROUGH,
            confidence=1.0,
            original_tokens=original_tokens,
            compressed_tokens=original_tokens,
            metadata={"reason": "token_count_below_threshold"},
        )

    def _compress_with_llm(
        self,
        output: str,
        context: dict[str, Any],
        original_tokens: int,
    ) -> ReshapeResult:
        """
        使用LLM压缩输出（带超时控制）

        Args:
            output: 原始输出
            context: 上下文信息
            original_tokens: 原始token数

        Returns:
            ReshapeResult: 压缩结果
        """
        if not self.llm_provider:
            # 无LLM提供商，降级到智能截断
            return self._fallback_to_truncate(output, original_tokens, "LLM provider not available")

        # 构建prompt
        prompt = self._build_compression_prompt(output, context)

        # 带超时执行LLM调用
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.llm_provider, prompt)
                compressed = future.result(timeout=self.llm_timeout)
        except concurrent.futures.TimeoutError:
            # LLM超时，降级到智能截断
            if self.enable_metrics:
                with self._metrics_lock:
                    self._metrics.llm_timeout_count += 1
            return self._fallback_to_truncate(output, original_tokens, "LLM timeout")
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            # LLM调用异常，降级到智能截断
            return self._fallback_to_truncate(output, original_tokens, str(e))

        # 验证压缩结果
        compressed_tokens = estimate_tokens(compressed)

        # 如果压缩后反而更长，使用原始内容
        if compressed_tokens >= original_tokens:
            return ReshapeResult(
                compressed_output=output,
                strategy_used=Strategy.LLM_COMPRESSION,
                confidence=0.5,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                metadata={"warning": "compression_ineffective", "fallback": True},
            )

        # 计算压缩置信度（基于压缩率）
        compression_ratio = 1 - (compressed_tokens / original_tokens)
        confidence = min(1.0, 0.5 + compression_ratio * 0.5)

        return ReshapeResult(
            compressed_output=compressed,
            strategy_used=Strategy.LLM_COMPRESSION,
            confidence=confidence,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            metadata={"compression_ratio": round(compression_ratio, 2)},
        )

    def _smart_truncate(self, output: str, original_tokens: int) -> ReshapeResult:
        """
        智能截断策略

        策略:
        1. 保留前10%和后20%的行
        2. 提取包含error/exception/failed等关键词的行
        3. 添加[SUGGESTION]提示
        """
        lines = output.split("\n")
        total_lines = len(lines)

        if total_lines <= 10:
            if len(output) > self.max_output_tokens * 4:
                truncated_output = output[: self.max_output_tokens * 4] + "\n...[TRUNCATED SINGLE LINE OUTPUT]"
                return ReshapeResult(
                    compressed_output=truncated_output,
                    strategy_used=Strategy.SMART_TRUNCATE,
                    confidence=0.8,
                    original_tokens=original_tokens,
                    compressed_tokens=estimate_tokens(truncated_output),
                    metadata={"reason": "single_line_truncated", "total_lines": total_lines},
                )

            # 行数太少，直接返回
            return ReshapeResult(
                compressed_output=output,
                strategy_used=Strategy.SMART_TRUNCATE,
                confidence=0.9,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                metadata={"reason": "too_few_lines", "total_lines": total_lines},
            )

        # 计算保留的行数
        head_lines = max(1, total_lines // 10)  # 前10%
        tail_lines = max(1, total_lines // 5)  # 后20%

        # 保留头部和尾部
        head = lines[:head_lines]
        tail = lines[-tail_lines:]

        # 提取包含错误关键词的行
        error_lines = []
        for i, line in enumerate(lines):
            lower_line = line.lower()
            if any(keyword in lower_line for keyword in ERROR_KEYWORDS):
                error_lines.append(f"[Line {i + 1}] {line}")

        # 构建结果
        result_parts = [
            "[OUTPUT TRUNCATED - Showing head, error lines, and tail]",
            f"[Original: {total_lines} lines, ~{original_tokens} tokens]",
            "",
            "=== HEAD (first 10%) ===",
            *head,
        ]

        # 添加错误行（如果有）
        if error_lines:
            result_parts.extend(
                [
                    "",
                    "=== ERROR LINES ===",
                    *error_lines[:20],  # 最多20行错误
                ]
            )

        result_parts.extend(
            [
                "",
                "=== TAIL (last 20%) ===",
                *tail,
                "",
                "[SUGGESTION] Output was truncated due to length. "
                "If you need complete output, consider using pagination or filtering.",
            ]
        )

        compressed_output = "\n".join(result_parts)
        compressed_tokens = estimate_tokens(compressed_output)

        # 计算置信度（基于保留的信息完整性）
        confidence = 0.7 if error_lines else 0.6

        return ReshapeResult(
            compressed_output=compressed_output,
            strategy_used=Strategy.SMART_TRUNCATE,
            confidence=confidence,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            metadata={
                "total_lines": total_lines,
                "head_lines": head_lines,
                "tail_lines": tail_lines,
                "error_lines_found": len(error_lines),
            },
        )

    def _fallback_to_truncate(
        self,
        output: str,
        original_tokens: int,
        reason: str,
    ) -> ReshapeResult:
        """降级到智能截断"""
        if self.enable_metrics:
            with self._metrics_lock:
                self._metrics.llm_fallback_count += 1

        result = self._smart_truncate(output, original_tokens)
        result.metadata["fallback_reason"] = reason
        result.metadata["original_strategy"] = Strategy.LLM_COMPRESSION.value
        return result

    def _build_compression_prompt(self, output: str, context: dict[str, Any]) -> str:
        """构建LLM压缩prompt"""
        # 如果输出太长，先简单截断到合理长度再发送给LLM
        max_input_chars = self.max_output_tokens * 4  # 估算
        if len(output) > max_input_chars:
            output = output[:max_input_chars] + "\n... [truncated for LLM input]"

        # 添加上下文信息（如果有）
        context_str = ""
        if context.get("task_type"):
            context_str = f"Task type: {context['task_type']}\n"
        if context.get("user_intent"):
            context_str += f"User intent: {context['user_intent']}\n"

        prompt = self._compression_prompt_template.format(
            content=output,
            max_tokens=self.max_output_tokens,
        )

        if context_str:
            prompt = f"Context:\n{context_str}\n{prompt}"

        return prompt

    # -------------------------------------------------------------------------
    # 性能监控接口
    # -------------------------------------------------------------------------

    def _update_metrics(self, strategy: Strategy, processing_time_ms: float) -> None:
        """更新性能指标"""
        with self._metrics_lock:
            self._metrics.total_calls += 1
            self._metrics.total_processing_time_ms += processing_time_ms

            if strategy == Strategy.PASSTHROUGH:
                self._metrics.passthrough_count += 1
            elif strategy == Strategy.LLM_COMPRESSION:
                self._metrics.llm_compression_count += 1
            else:  # SMART_TRUNCATE
                self._metrics.smart_truncate_count += 1

            # 更新平均处理时间
            if self._metrics.total_calls > 0:
                self._metrics.avg_processing_time_ms = round(
                    self._metrics.total_processing_time_ms / self._metrics.total_calls, 2
                )

    def get_metrics(self) -> dict[str, Any]:
        """获取性能指标"""
        with self._metrics_lock:
            total = self._metrics.total_calls
            return {
                "total_calls": total,
                "passthrough_count": self._metrics.passthrough_count,
                "passthrough_ratio": (round(self._metrics.passthrough_count / total, 2) if total > 0 else 0),
                "llm_compression_count": self._metrics.llm_compression_count,
                "llm_compression_ratio": (round(self._metrics.llm_compression_count / total, 2) if total > 0 else 0),
                "smart_truncate_count": self._metrics.smart_truncate_count,
                "smart_truncate_ratio": (round(self._metrics.smart_truncate_count / total, 2) if total > 0 else 0),
                "llm_timeout_count": self._metrics.llm_timeout_count,
                "llm_fallback_count": self._metrics.llm_fallback_count,
                "avg_processing_time_ms": self._metrics.avg_processing_time_ms,
                "total_processing_time_ms": round(self._metrics.total_processing_time_ms, 2),
            }

    def reset_metrics(self) -> None:
        """重置性能指标"""
        with self._metrics_lock:
            self._metrics = PerformanceMetrics()

    # -------------------------------------------------------------------------
    # 配置接口
    # -------------------------------------------------------------------------

    def set_llm_provider(self, provider: Callable[[str], str] | None) -> None:
        """设置/更新LLM提供商"""
        self.llm_provider = provider

    def update_thresholds(
        self,
        token_threshold: int | None = None,
        truncate_threshold: int | None = None,
        max_output_tokens: int | None = None,
        llm_timeout: float | None = None,
    ) -> None:
        """更新阈值配置"""
        if token_threshold is not None:
            self.token_threshold = token_threshold
        if truncate_threshold is not None:
            self.truncate_threshold = truncate_threshold
        if max_output_tokens is not None:
            self.max_output_tokens = max_output_tokens
        if llm_timeout is not None:
            self.llm_timeout = llm_timeout


# =============================================================================
# 5. 便捷函数
# =============================================================================


def reshape_output(
    output: str,
    llm_provider: Callable[[str], str] | None = None,
    context: dict[str, Any] | None = None,
    **kwargs: Any,
) -> ReshapeResult:
    """
    便捷函数 - 快速重塑输出

    Args:
        output: 原始输出
        llm_provider: 可选的LLM提供商
        context: 上下文信息
        **kwargs: 传递给OutputReshaper的其他参数

    Returns:
        ReshapeResult: 重塑结果

    Example:
        >>> result = reshape_output(long_text)
        >>> _log.info(result.compressed_output)
        >>> _log.info("Strategy: {result.strategy_used.value}")
    """
    reshaper = OutputReshaper(llm_provider=llm_provider, **kwargs)
    return reshaper.reshape(output, context)


# =============================================================================
# 6. 全局实例（单例模式）
# =============================================================================

_reshaper_instance: OutputReshaper | None = None
_reshaper_lock = threading.Lock()


def get_reshaper() -> OutputReshaper:
    """获取全局OutputReshaper实例（单例）"""
    global _reshaper_instance
    if _reshaper_instance is None:
        with _reshaper_lock:
            if _reshaper_instance is None:
                _reshaper_instance = OutputReshaper()
    return _reshaper_instance
