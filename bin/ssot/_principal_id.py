"""_principal_id.py — canonical principal_id normalization.

BET-Y2Q4-SH-7: shared utility for the ``principal:<id>`` convention
enforced by sovereignty (``projects/omo/src/omo/sovereignty/roles.py:_ID_PREFIXES``).

Two helpers:

- :func:`canonical_principal_id` — pure transformation: given a raw
  value (typically ``OMO_PRINCIPAL_ID`` env var), return either the
  same string (if already prefixed) or ``principal:<value>``.
- :func:`principal_id_from_env` — convenience wrapper that reads
  ``OMO_PRINCIPAL_ID`` from ``os.environ`` (with fallback) and routes
  it through :func:`canonical_principal_id`.

All other call sites should use :func:`principal_id_from_env` instead
of reading ``OMO_PRINCIPAL_ID`` directly.  The recorder's private
``_canonical_principal_id`` (introduced in SH-5.1) is re-exported here
as :func:`canonical_principal_id` for compatibility.
"""
from __future__ import annotations

import os
from typing import Final

# Sovereignty strict prefixes (BET-Y1Q2-T1-04).  Any prefix not listed
# here is treated as already-canonical.  See sovereignty/roles.py:_ID_PREFIXES.
_PRINCIPAL_PREFIX: Final[str] = "principal:"


def canonical_principal_id(raw: str | None) -> str:
    """Normalize a raw principal_id to the canonical ``principal:<id>`` form.

    Behavior:
      - Empty / None / whitespace-only → returns ``""`` (caller decides).
      - Already prefixed (``principal:x``, ``role:y``, etc.) → returned
        as-is so callers that pass a non-principal id do not get a
        spurious prefix.
      - Bare identifier (e.g., ``xiamingxing``) → ``principal:xiamingxing``.

    Examples
    --------
    >>> canonical_principal_id("xiamingxing")
    'principal:xiamingxing'
    >>> canonical_principal_id("principal:xiamingxing")
    'principal:xiamingxing'
    >>> canonical_principal_id("role:foo")
    'role:foo'
    >>> canonical_principal_id("")
    ''
    """
    value = str(raw or "").strip()
    if not value:
        return ""
    if ":" in value:
        # Already has a kind prefix (principal / role / responsibility / ...).
        return value
    return f"{_PRINCIPAL_PREFIX}{value}"


def principal_id_from_env(env: dict[str, str] | None = None) -> str:
    """Read ``OMO_PRINCIPAL_ID`` from the environment, canonicalize, and return.

    Falls back to ``"xiamingxing"`` when unset, then canonicalizes to
    ``principal:xiamingxing``.  Pass ``env={}`` to simulate an empty
    environment in tests.
    """
    source = env if env is not None else dict(os.environ)
    raw = source.get("OMO_PRINCIPAL_ID", "xiamingxing")
    return canonical_principal_id(raw)