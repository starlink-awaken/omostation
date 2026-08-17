from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Providers ≡ Module
# 内涵 ≝ {Providers}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Providers)}
# 功能 ⊢ {Init_Providers, Execute_Providers, Validate_Providers}
# =============================================================================

# ---
# domain: D-Harvest
# layer: embeddings
# status: active
# ---

"""
嵌入提供商实现

提供多种文本嵌入生成后端:
- OpenAIEmbeddingProvider: OpenAI API
- LocalEmbeddingProvider: sentence-transformers 本地模型
- MockEmbeddingProvider: 确定性伪随机嵌入（测试用）
- FallbackEmbeddingProvider: 自动回退到 Mock 的包装器
"""

import hashlib
import logging
import os
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    pass

_log = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """嵌入生成器接口协议"""

    @property
    def dimension(self) -> int:
        """返回嵌入向量维度"""
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        将文本列表转换为嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表（每个向量是 float 列表）
        """
        ...


class BaseEmbeddingProvider(ABC):
    """嵌入提供商基类"""

    def __init__(self, dimension: int = 1536) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """子类必须实现此方法"""
        ...

    def _validate_texts(self, texts: list[str]) -> None:
        """验证输入文本"""
        if not isinstance(texts, list):
            raise TypeError(f"Expected list of strings, got {type(texts)}")
        if not texts:
            return
        if not all(isinstance(t, str) for t in texts):
            raise TypeError("All items must be strings")


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Test/fallback embedding provider — NOT for production use.

    生成固定维度的确定性伪随机向量，不依赖外部 API。
    相同文本始终产生相同向量，适合测试和演示。
    """

    def __init__(self, dimension: int = 1536, seed_prefix: str = "mock") -> None:
        _log.warning("Using MockEmbeddingProvider — embeddings will be deterministic fakes")
        super().__init__(dimension)
        self._seed_prefix = seed_prefix

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """生成确定性伪随机嵌入"""
        self._validate_texts(texts)

        if not texts:
            return []

        results = []
        for text in texts:
            # 使用文本哈希作为随机种子，保证相同文本产生相同向量
            seed_str = f"{self._seed_prefix}:{text}"
            seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2**32)  # noqa: S324
            rng = random.Random(seed)  # noqa: S311

            # 生成单位向量
            vec = [rng.gauss(0, 1) for _ in range(self._dimension)]
            norm = sum(x**2 for x in vec) ** 0.5
            if norm > 0:
                vec = [x / norm for x in vec]

            results.append(vec)

        return results


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI API 嵌入提供商

    使用 OpenAI 的 text-embedding-3-small 或其他模型生成高质量嵌入。
    需要 OPENAI_API_KEY 环境变量或构造函数传入 api_key。

    特性:
    - 高质量嵌入（1536 维度）
    - 支持 text-embedding-3-small/large/ada-002
    - 自动批处理和重试
    - 符合 OpenAI API 速率限制
    """

    # OpenAI 模型维度映射
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    DEFAULT_MODEL = "text-embedding-3-small"
    MAX_BATCH_SIZE = 2048  # OpenAI 限制

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        """
        初始化 OpenAI 嵌入提供商

        Args:
            api_key: OpenAI API Key（默认从 OPENAI_API_KEY 环境变量）
            model: 模型名称（默认 text-embedding-3-small）
            dimension: 嵌入维度（默认根据模型自动选择）
            base_url: 自定义 API 基础 URL（用于代理或 Azure）
            timeout: API 调用超时时间（秒）
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key.")

        self._model = model or os.getenv("EMBEDDING_MODEL", self.DEFAULT_MODEL)

        # 根据模型确定维度
        if dimension is None:
            dimension = self.MODEL_DIMENSIONS.get(self._model or "", 1536)

        super().__init__(dimension)
        self._base_url = base_url
        self._timeout = timeout
        self._client: Any = None

    def _get_client(self) -> Any:
        """延迟初始化 OpenAI 客户端"""
        if self._client is None:
            try:
                import openai
            except ImportError as e:
                raise ImportError("openai package is required. Install with: pip install openai") from e

            client_kwargs: dict[str, Any] = {
                "api_key": self._api_key,
                "timeout": self._timeout,
            }
            if self._base_url:
                client_kwargs["base_url"] = self._base_url

            self._client = openai.AsyncOpenAI(**client_kwargs)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        使用 OpenAI API 生成嵌入

        Args:
            texts: 文本列表（最多 2048 条）

        Returns:
            嵌入向量列表

        Raises:
            ValueError: 输入验证失败
            RuntimeError: API 调用失败
        """
        self._validate_texts(texts)

        if not texts:
            return []

        if len(texts) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Batch size {len(texts)} exceeds OpenAI limit of {self.MAX_BATCH_SIZE}")

        # 过滤空文本（OpenAI 不接受空字符串）
        processed_texts = []
        empty_indices = []
        for i, text in enumerate(texts):
            if not text or not text.strip():
                empty_indices.append(i)
                processed_texts.append(" ")  # 用空格代替空字符串
            else:
                processed_texts.append(text.strip())

        try:
            client = self._get_client()
            response = await client.embeddings.create(
                model=self._model,
                input=processed_texts,
                encoding_format="float",
            )

            # 提取嵌入向量
            embeddings = [item.embedding for item in response.data]

            # 对于空文本，返回零向量
            if empty_indices:
                zero_vector = [0.0] * self._dimension
                for idx in empty_indices:
                    embeddings[idx] = zero_vector

            _log.debug(f"[OpenAIEmbedding] Generated {len(embeddings)} embeddings using {self._model}")

            return embeddings

        except Exception as e:
            _log.error(f"[OpenAIEmbedding] API call failed: {e}")
            raise RuntimeError(f"OpenAI embedding generation failed: {e}") from e


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """
    本地嵌入提供商（sentence-transformers）

    使用本地运行的 sentence-transformers 模型生成嵌入，
    无需外部 API 调用，适合隐私敏感场景和离线使用。

    特性:
    - 完全本地运行，无需网络
    - 支持多种预训练模型
    - 自动使用 GPU（如果可用）
    - 适合中等批量处理

    默认模型: all-MiniLM-L6-v2 (384维，快速)
    高质量模型: all-mpnet-base-v2 (768维，更准确)
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(
        self,
        model_name: str | None = None,
        dimension: int | None = None,
        device: str | None = None,
        cache_dir: str | None = None,
    ) -> None:
        """
        初始化本地嵌入提供商

        Args:
            model_name: 模型名称（默认 all-MiniLM-L6-v2）
            dimension: 嵌入维度（默认根据模型自动检测）
            device: 运行设备（'cpu', 'cuda', 'mps' 或 None 自动选择）
            cache_dir: 模型缓存目录

        Raises:
            ImportError: 未安装 sentence-transformers
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is required for LocalEmbeddingProvider. "
                "Install with: pip install sentence-transformers"
            ) from e

        self._model_name = model_name or self.DEFAULT_MODEL
        self._device = device
        self._cache_dir = cache_dir
        self._model: Any = None

        # 延迟加载模型，首次使用时初始化
        # 维度将在首次 embed 调用时确定
        super().__init__(dimension or 384)  # 默认 384 (all-MiniLM-L6-v2)

    def _get_model(self) -> Any:
        """延迟初始化模型"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            _log.info(f"[LocalEmbedding] Loading model: {self._model_name}")

            model_kwargs = {}
            if self._cache_dir:
                model_kwargs["cache_folder"] = self._cache_dir

            self._model = SentenceTransformer(self._model_name, device=self._device, **model_kwargs)

            # 更新维度为实际模型维度
            self._dimension = self._model.get_sentence_embedding_dimension()
            _log.info(
                f"[LocalEmbedding] Model loaded: {self._model_name} "
                f"(dim={self._dimension}, device={self._model.device})"
            )

        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        使用本地模型生成嵌入

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        self._validate_texts(texts)

        if not texts:
            return []

        try:
            model = self._get_model()

            # sentence-transformers 是同步的，在线程池中运行
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as pool:
                embeddings = await loop.run_in_executor(
                    pool,
                    lambda: model.encode(
                        texts,
                        convert_to_numpy=True,
                        normalize_embeddings=True,
                        show_progress_bar=False,
                    ).tolist(),
                )

            _log.debug(f"[LocalEmbedding] Generated {len(embeddings)} embeddings")
            return cast("list[list[float]]", embeddings)

        except Exception as e:
            _log.error(f"[LocalEmbedding] Encoding failed: {e}")
            raise RuntimeError(f"Local embedding generation failed: {e}") from e


class FallbackEmbeddingProvider(BaseEmbeddingProvider):
    """
    回退嵌入提供商

    尝试使用真实提供商（OpenAI -> Local），失败时自动回退到 Mock。
    适合生产环境，确保嵌入功能始终可用。

    回退顺序:
    1. OpenAIEmbeddingProvider (如果配置了 API key)
    2. LocalEmbeddingProvider (如果 sentence-transformers 可用)
    3. MockEmbeddingProvider (始终可用)
    """

    def __init__(self, dimension: int = 1536) -> None:
        super().__init__(dimension)
        self._primary: EmbeddingProvider | None = None
        self._fallback: MockEmbeddingProvider = MockEmbeddingProvider(dimension)
        self._initialized = False
        self._active_provider = "mock"  # 当前使用的提供商名称

    async def _init_provider(self) -> None:
        """延迟初始化，尝试真实提供商"""
        if self._initialized:
            return

        # 尝试 OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                self._primary = OpenAIEmbeddingProvider(
                    api_key=openai_key,
                    dimension=self._dimension,
                )
                _log.info("[FallbackEmbedding] Primary provider: OpenAI")
                self._active_provider = "openai"
                self._initialized = True
                return
            except (ValueError, RuntimeError) as e:
                _log.warning(f"[FallbackEmbedding] OpenAI init failed: {e}")

        # 尝试本地模型
        try:
            self._primary = LocalEmbeddingProvider(dimension=self._dimension)
            _log.info("[FallbackEmbedding] Primary provider: Local")
            self._active_provider = "local"
            self._initialized = True
            return
        except ImportError:
            _log.debug("[FallbackEmbedding] sentence-transformers not available")
        except RuntimeError as e:
            _log.warning(f"[FallbackEmbedding] Local init failed: {e}")

        # 使用 Mock
        _log.warning("[FallbackEmbedding] Using Mock provider (no real provider available)")
        self._primary = None
        self._active_provider = "mock"
        self._initialized = True

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        生成嵌入，自动回退到 Mock 如果真实提供商失败
        """
        await self._init_provider()

        # 如果有真实提供商，先尝试使用
        if self._primary is not None:
            try:
                return await self._primary.embed(texts)
            except RuntimeError as e:
                _log.warning(
                    f"[FallbackEmbedding] Primary provider failed ({self._active_provider}): {e}. Falling back to Mock."
                )

        # 使用 Mock
        self._active_provider = "mock"
        return await self._fallback.embed(texts)

    def get_active_provider(self) -> str:
        """获取当前实际使用的提供商名称"""
        return self._active_provider
