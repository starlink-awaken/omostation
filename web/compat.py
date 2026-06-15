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
    @staticmethod
    def list_recent_research(limit=10):
        return []

    @staticmethod
    def search_research(q="", status="", tag="", limit=10):
        return []

    @staticmethod
    def get_research_detail(research_id):
        return None

    @staticmethod
    def archive_research(research_id):
        return True

    @staticmethod
    def publish_brief(research_id):
        return ""

    @staticmethod
    def sync_published(research_id, target_dir=""):
        return True

    @staticmethod
    def unarchive_research(research_id):
        return True

    @staticmethod
    def tag_research(research_id, tag_list):
        return True

    @staticmethod
    def rename_research(research_id, title):
        return True

workspace_research = WorkspaceResearch

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
        self._event_log = []
    def register_hook(self, hook):
        self._hooks.append(hook)
    def emit(self, event):
        for hook in self._hooks:
            try:
                hook(event)
            except Exception:
                pass
        self._event_log.append(event)
    def get_event_log(self, limit=100):
        return self._event_log[-limit:]

class Router:
    """兼容类 — router"""
    def __init__(self):
        self._routes = []
    def add_route(self, *args, **kwargs):
        pass
    async def close(self):
        pass

class ServiceRegistry:
    """兼容类 — service registry"""
    def __init__(self):
        self._services = {}
    def register(self, name, service):
        self._services[name] = service
    def list_all(self):
        return list(self._services.values())
    def list_healthy(self):
        return [s for s in self._services.values() if getattr(s, 'healthy', True)]
    async def health_check_all(self):
        pass

def get_event_bus(*args, **kwargs):
    """兼容函数"""
    return EventBus()

def get_registry(*args, **kwargs):
    """兼容函数"""
    return ServiceRegistry()

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
