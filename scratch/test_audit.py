def audit_tool_call(func):
    def wrapper(*args, **kwargs):
        print(f"Audit: {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
