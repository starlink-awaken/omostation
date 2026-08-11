"""Explicit backend-ID registry with fail-closed placement binding."""

from __future__ import annotations

from omlxc.domain.protocols import BackendAdapter
from omlxc.scheduler import PlacementSnapshot

from .models import AdapterBinding


class AdapterRegistry:
    def __init__(self, bindings: tuple[AdapterBinding, ...]) -> None:
        self._adapters: dict[str, BackendAdapter] = {}
        self._placement_bindings: dict[str, tuple[str, str, str, str]] = {}
        for binding in bindings:
            if binding.backend_id in self._adapters:
                raise ValueError("duplicate backend adapter binding")
            self._adapters[binding.backend_id] = binding.adapter

    def resolve(self, placement: PlacementSnapshot) -> BackendAdapter:
        try:
            adapter = self._adapters[placement.backend_id]
        except KeyError:
            raise LookupError("placement backend has no registered adapter") from None
        binding = (
            placement.model_id,
            placement.backend_id,
            placement.backend_model_id,
            placement.node_id,
        )
        prior = self._placement_bindings.setdefault(placement.placement_id, binding)
        if prior != binding:
            raise LookupError("placement binding changed without registry replacement")
        return adapter
