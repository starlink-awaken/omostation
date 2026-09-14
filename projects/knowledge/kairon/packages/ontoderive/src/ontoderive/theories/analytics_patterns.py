# flake8: noqa
from .patterns.advanced import *  # noqa: F403

# Private helpers must be explicitly imported (underscore prefix hides from *)
from .patterns.common import _extract_num, _find_entity_for_fact, _is_dict, _iter_facts  # noqa: F401
from .patterns.common import *  # noqa: F403
