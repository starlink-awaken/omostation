from __future__ import annotations

# ruff: noqa: RUF002, RUF003
import json
import logging
import os
from pathlib import Path
from typing import Any, Protocol

_log = logging.getLogger(__name__)

# Import metrics system (optional, falls back to noop)
try:
    from .metrics import get_registry  # type: ignore[import-not-found]
except ImportError:

    class _Counter(Protocol):
        def inc(self, *a: Any, **kw: Any) -> None: ...

        def dec(self, *a: Any, **kw: Any) -> None: ...

        def get(self) -> int: ...

    class _Gauge(Protocol):
        def set(self, *a: Any, **kw: Any) -> None: ...

        def inc(self, *a: Any, **kw: Any) -> None: ...

        def dec(self, *a: Any, **kw: Any) -> None: ...

        def get(self) -> int: ...

    class _Histogram(Protocol):
        def observe(self, *a: Any, **kw: Any) -> None: ...

        def get_stats(self) -> dict[str, float | int]: ...

    class _Registry(Protocol):
        def counter(self, *a: Any, **kw: Any) -> _Counter: ...

        def gauge(self, *a: Any, **kw: Any) -> _Gauge: ...

        def histogram(self, *a: Any, **kw: Any) -> _Histogram: ...

    def get_registry() -> _Registry:
        class _NoopCounter:
            def inc(self, *a: Any, **kw: Any) -> None:
                pass

            def dec(self, *a: Any, **kw: Any) -> None:
                pass

            def get(self) -> int:
                return 0

        class _NoopGauge:
            def set(self, *a: Any, **kw: Any) -> None:
                pass

            def inc(self, *a: Any, **kw: Any) -> None:
                pass

            def dec(self, *a: Any, **kw: Any) -> None:
                pass

            def get(self) -> int:
                return 0

        class _NoopHistogram:
            def observe(self, *a: Any, **kw: Any) -> None:
                pass

            def get_stats(self) -> dict[str, float | int]:
                return {"count": 0, "sum": 0, "avg": 0}

        class _NoopRegistry:
            def counter(self, *a: Any, **kw: Any) -> _NoopCounter:
                return _NoopCounter()

            def gauge(self, *a: Any, **kw: Any) -> _NoopGauge:
                return _NoopGauge()

            def histogram(self, *a: Any, **kw: Any) -> _NoopHistogram:
                return _NoopHistogram()

        return _NoopRegistry()


class EnvResolver:
    _instance: EnvResolver | None = None

    def __new__(cls) -> EnvResolver:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
            cls._instance._init_metrics()
        return cls._instance

    def _init_metrics(self) -> None:
        """初始化指标"""
        registry = get_registry()
        self._resolve_calls = registry.counter(
            "env_resolver_resolve_calls_total", "Total number of path resolution calls"
        )
        self._resolve_cache_hits = registry.counter("env_resolver_cache_hits_total", "Total number of cache hits")
        self._resolve_cache_misses = registry.counter("env_resolver_cache_misses_total", "Total number of cache misses")
        self._resolve_duration = registry.histogram(
            "env_resolver_resolve_duration_ms", "Path resolution duration in milliseconds"
        )

        # 清除缓存计数器
        self._cache_clears = registry.counter("env_resolver_cache_clears_total", "Total number of cache clears")

    def _load_config(self) -> None:
        # 读取 BOS_ROOT 环境变量
        bos_root = os.environ.get("BOS_ROOT")
        if not bos_root:
            raise ValueError(
                "BOS_ROOT environment variable is required. Please set it to the root directory of your B-OS installation."
            )
        self.root = Path(bos_root).resolve()

        # 优先读取 YAML 配置
        yaml_path = self.root / "Z-Core/ACT-env.yaml"
        json_path = self.root / "Z-Core/ACT-env.json"

        if yaml_path.exists():
            try:
                import yaml

                with open(yaml_path, encoding="utf-8") as f:
                    self.config = yaml.safe_load(f)
            except (yaml.YAMLError, OSError) as e:
                _log.error("%s: %s", type(e).__name__, e)
                # YAML 解析失败，尝试 JSON 或回退到空配置
                if json_path.exists():
                    with open(json_path, encoding="utf-8") as f:
                        self.config = json.load(f)
                else:
                    self.config = {"PATHS": {}}
        elif json_path.exists():
            with open(json_path, encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {"PATHS": {}}

    def resolve(self, alias: str, use_cache: bool = True) -> Path | None:
        """将逻辑别名解析为物理绝对路径

        Args:
            alias: 逻辑别名
            use_cache: 是否使用缓存（默认True）

        returns: Path | None
           解析后的物理路径，如果无法解析返回 None

        Raises:
            Exception: 无法解析别名
        """
