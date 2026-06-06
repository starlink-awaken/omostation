from typing import Dict, Optional, Any, List
import logging
import asyncio

_log = logging.getLogger(__name__)

class MountRegistry:
    """
    Dynamic mount registry for routing BOS URIs to downstream providers (MCP servers/proxies).
    Supports prefix routing for MCP resources.
    """
    
    def __init__(self):
        # Maps prefix (e.g. "bos://memory/") to downstream provider connection info or local handler
        self._mounts: Dict[str, Any] = {}
        
    def register_mount(self, prefix: str, provider: Any):
        """
        Register a mount point.
        prefix: e.g. "bos://memory/"
        provider: e.g. an MCP Client, "local:omo_provider", "http://..."
        """
        if not prefix.endswith("/"):
            prefix += "/"
        self._mounts[prefix] = provider
        _log.info("Registered BOS mount point: %s", prefix)
        
    def unregister_mount(self, prefix: str):
        if not prefix.endswith("/"):
            prefix += "/"
        if prefix in self._mounts:
            del self._mounts[prefix]
            _log.info("Unregistered BOS mount point: %s", prefix)
            
    def resolve_provider(self, uri: str) -> Optional[Any]:
        """
        Find the longest matching prefix for the URI.
        """
        best_match = None
        best_len = -1
        
        for prefix, provider in self._mounts.items():
            if uri.startswith(prefix) and len(prefix) > best_len:
                best_match = provider
                best_len = len(prefix)
                
        return best_match
        
    def get_all_mounts(self) -> Dict[str, Any]:
        return dict(self._mounts)

# Global singleton
_mount_registry = MountRegistry()

def get_mount_registry() -> MountRegistry:
    return _mount_registry
