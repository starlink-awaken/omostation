from fastmcp.server.middleware import Middleware
import inspect
print(inspect.signature(Middleware.on_call_tool))
