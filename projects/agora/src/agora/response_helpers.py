"""统一的 _ok / _error 响应辅助函数。

Agora 所有 MCP 工具和模板都使用这两个函数返回标准格式。
"""


def _error(msg: str) -> dict:
    """返回标准错误响应。"""
    return {"status": "error", "error": msg}


def _ok(data: dict) -> dict:
    """返回标准成功响应。data 中的字段会被合并到顶层。"""
    return {"status": "ok", **data}
