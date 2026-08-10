"""Forwarding module — re-exports from l0.ssb.ssb_auth."""

from ecos.l0.ssb.ssb_auth import (
    _load_key,
    compute_signature,
    verify,
)

__all__ = ["_load_key", "compute_signature", "verify"]
