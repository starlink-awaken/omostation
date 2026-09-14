"""
DEPRECATED — The paradigm module has concept overlap with the sophia package.

This module is retained for backward compatibility only. New code should use sophia directly:
    pip install sophia
    sophia compile <query> --json

The CLI bridge (minerva.paradigm.meta) that calls sophia via subprocess is preserved.

This module will be removed in a future release — do not add new dependencies on it.
"""

import warnings

warnings.warn(
    "The `minerva.paradigm` module is deprecated. "
    "It has concept overlap with the sophia package. "
    "Use `sophia compile <query> --json` instead.",
    DeprecationWarning,
    stacklevel=2,
)
