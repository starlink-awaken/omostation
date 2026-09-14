"""Domain cartridge packages for omostation workspace.

`domain` is the import root for domain-cartridge capabilities.  Each subpackage
(`research`, `health`, ...) is a self-contained cartridge that can be run via
`uv run python -m domain.<name>.<entry>` from the cartridge directory.

Health cartridge: continuous vitals monitoring, anomaly alerting and
visit-question cards.  Fully deterministic local computation, no third-party
runtime dependencies, no network access.  Missing data is reported as
`unmeasured` — never interpolated or fabricated.
"""

__version__ = "0.1.0"
