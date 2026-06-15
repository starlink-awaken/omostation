"""兼容层 — 为旧版 agora 模块提供兼容"""

def service_to_agent_card(service):
    """兼容函数 — 返回简单的 Agent Card"""
    return {
        "name": getattr(service, "name", "unknown"),
        "description": getattr(service, "description", ""),
        "url": getattr(service, "url", ""),
    }

class WorkspaceResearch:
    """兼容类 — workspace research"""
    pass

class AuditSubscriber:
    """兼容类 — audit subscriber"""
    def __init__(self, *args, **kwargs):
        pass
    def on_event(self, *args, **kwargs):
        pass

class DiscoveryEngine:
    """兼容类 — discovery engine"""
    def __init__(self, *args, **kwargs):
        pass

class Pipeline:
    """兼容类 — pipeline"""
    def __init__(self, *args, **kwargs):
        pass

class Service:
    """兼容类 — service base"""
    pass

class EventBus:
    """兼容类 — event bus"""
    def __init__(self):
        self._hooks = []
    def register_hook(self, hook):
        self._hooks.append(hook)
    def emit(self, event):
        for hook in self._hooks:
            try:
                hook(event)
            except Exception:
                pass

class Router:
    """兼容类 — router"""
    def __init__(self):
        self._routes = []
    def add_route(self, *args, **kwargs):
        pass
    async def close(self):
        pass

def get_event_bus(*args, **kwargs):
    """兼容函数"""
    return EventBus()

def get_registry(*args, **kwargs):
    """兼容函数"""
    return {}

def get_router(*args, **kwargs):
    """兼容函数"""
    return Router()

def is_safe_url(url):
    """兼容函数"""
    return True

def parse_protocol_config(config):
    """兼容函数"""
    return config

def parse_tags(tags):
    """兼容函数"""
    return tags

# 兼容别名
workspace_research = WorkspaceResearch
