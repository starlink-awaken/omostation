"""L0 Audit — 共享审计层 | 约束校验·操作日志·BOS验证"""
import yaml, json, os
from pathlib import Path
from datetime import datetime

H = Path.home()
DOCS = H / "Documents"
CONSTRAINTS_PATH = Path(__file__).parent.parent / "l0" / "constraints.yaml"
AUDIT_LOG = H / ".ecos" / "audit" / "operations.jsonl"

def load_constraints():
    if not CONSTRAINTS_PATH.exists(): return []
    with open(CONSTRAINTS_PATH) as f:
        return yaml.safe_load(f).get("constraints", [])

def validate_operation(domain_id: str, operation: str, uri: str = None) -> dict:
    """在任何入口(MCP/HTTP/CLI)执行操作前调用此函数"""
    constraints = load_constraints()
    violations = []
    
    # X4-C05: 跨域直接写入检查
    if operation.startswith("write"):
        for c in constraints:
            if c["id"] == "X4-C05":
                violations.append({"constraint": "X4-C05", "rule": c["rule"], "severity": c["type"]})
    
    # X4-C10: BOS URI格式
    if uri and not uri.startswith("bos://"):
        violations.append({"constraint": "X4-C10", "rule": "URI格式", "severity": "required"})
    
    # X4-C08: KEMS结构 (write操作)
    if operation in ("domain_create", "domain_register"):
        violations.append({"constraint": "X4-C08", "note": "创建后需运行 domain validate", "severity": "preferred"})
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "domain": domain_id,
        "operation": operation,
        "uri": uri,
        "passed": len([v for v in violations if v["severity"]=="required"]) == 0,
        "violations": violations,
    }
    
    # 写审计日志
    log_operation(result)
    
    return result

def log_operation(result: dict):
    """写入审计日志"""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG, 'a') as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

def get_audit_log(domain: str = None, since: str = None, limit: int = 50) -> list:
    """查询审计日志"""
    if not AUDIT_LOG.exists(): return []
    entries = []
    with open(AUDIT_LOG) as f:
        for line in f:
            try:
                e = json.loads(line)
                if domain and e.get("domain") != domain: continue
                entries.append(e)
            except: pass
    return entries[-limit:]
