"""core-models stdio CLI shim (BOS transport=stdio).

匹配 agora BOS stdio 适配器协议:
- action 从 argv 尾参取 (如 `python -m core_models.cli schema` 的 `schema`)
- 请求从 stdin 读一行 JSON `{"args":..., "kwargs":...}`
- 结果打印一行 JSON 到 stdout
复用 __main__._call_action 真业务 dispatch (search/ingest/validate/... + do_default fallback)。

修复: bos://persona/core-models/{schema,validate} 声明用 `-m core_models.cli`,
但此前包内只有 __main__.serve() (stdio-RPC 循环) 无 argv cli → resolve 断层 (A2)。
"""

from __future__ import annotations

import json
import sys
from typing import Any

from core_models.__main__ import _call_action


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    action = argv[0] if argv else "default"
    raw = sys.stdin.readline()
    req: dict[str, Any] = {}
    if raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                req = parsed
        except json.JSONDecodeError:
            req = {}
    args = req.get("kwargs") or req.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    result = _call_action(action, args)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
