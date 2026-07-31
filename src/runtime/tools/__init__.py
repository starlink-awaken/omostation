from .matrix_tools import TOOLS as MATRIX_TOOLS
from .protocol_tools import TOOLS as PROTOCOL_TOOLS
from .kei_tools import TOOLS as KEI_TOOLS
from .i0_tools import TOOLS as I0_TOOLS
from .task_tools import TOOLS as TASK_TOOLS

TOOLS = MATRIX_TOOLS + PROTOCOL_TOOLS + KEI_TOOLS + I0_TOOLS + TASK_TOOLS
TOOL_MAP = {t["name"]: t for t in TOOLS}
