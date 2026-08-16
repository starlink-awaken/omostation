#!/usr/bin/env python3
"""
BOS Router — URI 路由层
解析 bos:// URI 并分发到对应的域服务。
"""

import re
from pathlib import Path
from typing import Optional


class BOSRouter:
    """BOS URI 路由器"""

    def __init__(self, domain_config_path: Optional[Path] = None):
        self._domains = {}
        if domain_config_path and domain_config_path.exists():
            try:
                import yaml
                config = yaml.safe_load(domain_config_path.read_text(encoding="utf-8"))
                self._domains = config.get("domains", {})
            except Exception:
                pass

    def resolve(self, uri: str) -> dict:
        """解析 BOS URI → {domain, service, path}"""
        match = re.match(r'^bos://([a-z]+)/([a-z_.]+)/([a-z_.]*)$', uri)
        if not match:
            return {"error": f"无效 URI: {uri}", "valid": False}

        namespace, domain_id, service = match.groups()
        return {
            "valid": True,
            "namespace": namespace,
            "domain_id": domain_id,
            "service": service,
            "uri": uri,
        }

    def dispatch(self, uri: str, **kwargs) -> str:
        """分发 BOS URI 到对应处理函数"""
        resolved = self.resolve(uri)
        if not resolved["valid"]:
            return f"ERROR: {resolved['error']}"

        domain_id = resolved["domain_id"]
        service = resolved["service"]

        # 路由表
        handlers = {
            "analysis": {
                "health_commission": self._handle_health_commission,
                "land_planning": self._handle_land_planning,
                "transformation": self._handle_transformation,
                "contract_law": self._handle_contract_law,
            }
        }

        ns_handlers = handlers.get(resolved["namespace"], {})
        handler = ns_handlers.get(domain_id)
        if handler:
            return handler(service, **kwargs)
        return f"ERROR: 未找到处理函数 for {uri}"

    def _handle_health_commission(self, service: str, **kwargs) -> str:
        from domain_kems import HealthCommissionController
        ctrl = HealthCommissionController()
        if service == "controller":
            import json
            return json.dumps(ctrl.run(), ensure_ascii=False, indent=2)
        return f"ERROR: 未知服务 {service}"

    def _handle_land_planning(self, service: str, **kwargs) -> str:
        from domain_kems import LandPlanningController
        ctrl = LandPlanningController()
        if service == "controller":
            import json
            return json.dumps(ctrl.run(), ensure_ascii=False, indent=2)
        return f"ERROR: 未知服务 {service}"

    def _handle_transformation(self, service: str, **kwargs) -> str:
        from domain_kems import TransformationCenterController
        ctrl = TransformationCenterController()
        if service == "controller":
            import json
            return json.dumps(ctrl.run(), ensure_ascii=False, indent=2)
        return f"ERROR: 未知服务 {service}"

    def _handle_contract_law(self, service: str, **kwargs) -> str:
        from domain_kems import ContractLawController
        ctrl = ContractLawController()
        if service == "controller":
            import json
            return json.dumps(ctrl.run(), ensure_ascii=False, indent=2)
        return f"ERROR: 未知服务 {service}"


if __name__ == "__main__":
    import sys

    uri = sys.argv[1] if len(sys.argv) > 1 else "bos://analysis/health_commission/controller"
    router = BOSRouter(Path.home() / ".config" / "domain" / "config.yaml")
    print(router.dispatch(uri))
