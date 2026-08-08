"""Anti-corruption adapter for projects/ecos (L0).

Re-exports the ecos MOF audit hook symbols used by Agora BOS tools.
"""

from ecos.ssot.tools.mof_agora_hook import post_audit, pre_check

__all__ = [
    "post_audit",
    "pre_check",
]
