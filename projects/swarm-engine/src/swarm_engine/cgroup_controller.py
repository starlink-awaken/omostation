from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Layer: L3
Summary: 'CgroupController: Manages physical resource isolation using Cgroup v2 or process-level fallbacks.'
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Cgroup Controller ≡ Module
# 内涵 ≝ {Cgroup, Controller}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, CgroupController)}
# 功能 ⊢ {Cgroup_Controller, Init_Cgroup, Validate_Controller}
# =============================================================================


import logging
import os
import platform
from abc import ABC, abstractmethod
from typing import Any

_log = logging.getLogger(__name__)


class IResourceProvider(ABC):
    """Interface for physical resource isolation."""

    @abstractmethod
    def set_limits(self, cpu_shares: int, mem_limit_bytes: int) -> bool:
        pass

    @abstractmethod
    def get_usage(self) -> dict[str, Any]:
        pass


# ── Linux Cgroup v2 Provider ────────────────────────────────────────────────


class LinuxCgroupProvider(IResourceProvider):
    CGROUP_ROOT = "/sys/fs/cgroup/sharedbrain"

    def __init__(self) -> None:
        if platform.system() == "Linux":
            try:
                os.makedirs(self.CGROUP_ROOT, exist_ok=True)
            except OSError as e:
                _log.warning(f"Failed to create cgroup root: {e}")

    def set_limits(self, cpu_shares: int, mem_limit_bytes: int) -> bool:
        if platform.system() != "Linux":
            return False

        try:
            # CPU limits (cpu.weight in v2)
            with open(os.path.join(self.CGROUP_ROOT, "cpu.weight"), "w") as f:
                f.write(str(cpu_shares))

            # Memory limits (memory.max in v2)
            limit_str = str(mem_limit_bytes) if mem_limit_bytes > 0 else "max"
            with open(os.path.join(self.CGROUP_ROOT, "memory.max"), "w") as f:
                f.write(limit_str)

            return True
        except Exception as e:
            _log.error(f"Failed to set cgroup limits: {e}")
            return False

    def get_usage(self) -> dict[str, Any]:
        usage = {"cpu_usage": 0.0, "mem_usage": 0}
        if platform.system() != "Linux":
            return usage

        try:
            with open(os.path.join(self.CGROUP_ROOT, "memory.current")) as f:
                usage["mem_usage"] = int(f.read().strip())
            # CPU usage requires more complex calculation in v2 (cpu.stat)
        except FileNotFoundError:
            _log.debug("Cgroup memory telemetry unavailable at %s", self.CGROUP_ROOT)
        except ValueError as exc:
            _log.warning("Invalid cgroup memory telemetry: %s", exc)
        except OSError as exc:
            _log.warning("Failed to read cgroup telemetry: %s", exc)
        return usage


# ── Cross-Platform Process Provider (Fallback) ──────────────────────────────


class ProcessLevelProvider(IResourceProvider):
    """Fallback using psutil for monitoring (cannot strictly enforce via kernel)."""

    def __init__(self) -> None:
        try:
            import psutil

            self._psutil = psutil
        except ImportError:
            self._psutil = None

    def set_limits(self, cpu_shares: int, mem_limit_bytes: int) -> bool:
        # psutil can set 'nice' value for CPU priority
        if self._psutil:
            try:
                p = self._psutil.Process(os.getpid())
                p.nice(10)  # Lower priority
                return True
            except (OSError, AttributeError, TypeError):
                pass
        return False

    def get_usage(self) -> dict[str, Any]:
        if not self._psutil:
            return {"cpu_usage": 0.0, "mem_usage": 0}

        p = self._psutil.Process(os.getpid())
        return {"cpu_usage": p.cpu_percent(interval=None), "mem_usage": p.memory_info().rss}


# ── Controller ─────────────────────────────────────────────────────────────


class CgroupController:
    def __init__(self) -> None:
        if platform.system() == "Linux" and os.path.exists("/sys/fs/cgroup"):
            self.provider: IResourceProvider = LinuxCgroupProvider()
        else:
            self.provider = ProcessLevelProvider()

    def enforce_isolation(self, cpu_weight: int = 100, mem_limit: int = 512 * 1024 * 1024) -> None:
        """Enforce resource limits for the current process."""
        _log.info(f"Enforcing isolation: CPU={cpu_weight}, MEM={mem_limit} bytes")
        success = self.provider.set_limits(cpu_weight, mem_limit)
        if success:
            _log.info("✅ Physical isolation layer active.")
        else:
            _log.warning("⚠️ Physical isolation enforcement failed, using logical fallback.")

    def get_telemetry(self) -> dict[str, Any]:
        return self.provider.get_usage()
