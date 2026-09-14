"""conftest — kairon root 测试的路径配置。"""

import sys
from pathlib import Path

# 确保 src/ 在 sys.path 上，使 import kairon 可工作
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
