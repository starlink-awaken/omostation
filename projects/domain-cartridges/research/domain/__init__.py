"""Domain cartridge packages for omostation workspace.

`domain` is the import root for domain-cartridge capabilities.  Each subpackage
(`research`, future `health`, `health-gov`, ...) is a self-contained cartridge
that can be run via `uv run python -m domain.<name>.<entry>` from the cartridge
directory.

This package intentionally has no third-party runtime dependencies at import
time; optional dependencies (e.g. network access for paper fetching) degrade
gracefully via the `circuit_breaker` guard in each source adapter.
"""

__version__ = "0.1.0"
