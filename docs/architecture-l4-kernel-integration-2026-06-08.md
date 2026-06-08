# L4 Kernel · 跨层串联设计

**2026-06-08 · 架构集成**

---

## 一、当前状态

### 1.1 l4-kernel 独立运行

```
l4-kernel 目前:
  ✅ Python API (import l4_kernel)
  ✅ CLI (l4-kernel domain/health/kems)
  ✅ MCP Server (42 tools, stdio/http/sse :7455)
  
  尚未集成:
  ❌ cockpit MCP tools (仍使用旧 _L4_DOMAINS)
  ❌ agora 服务注册 (agora-services.json)
  ❌ runtime cron (l4-kernel health 定时任务)
  ❌ ecos-link (CLI 注册)
```

### 1.2 集成目标

```
┌──────────────────────────────────────────────────────────┐
│                     I0 · agora                            │
│  服务注册 + BOS 路由 + MCP 代理                            │
│                                                          │
│  agora-services.json:                                    │
│    l4-kernel: mcp, stdio://l4-kernel, port 7455          │
│                                                          │
│  agora-routes.json:                                      │
│    l4_domains_list → l4-kernel                           │
│    l4_health → l4-kernel                                 │
│    ... (42 tools 全注册)                                  │
└──────────────────────────────────────────────────────────┘
         ↕ MCP proxy                ↕ import
┌──────────────────────┐  ┌──────────────────────────────────┐
│   L3 · cockpit        │  │   L1 · runtime                   │
│                       │  │                                  │
│  MCP tools 替换:      │  │  cron jobs:                      │
│  _L4_DOMAINS →        │  │  l4-domain-health-scan           │
│    DomainRegistry     │  │  l4-freshness-scan               │
│  _scan_cards →        │  │  l4-claude-validate              │
│    CardsPlane         │  │  l4-governance-report            │
│  _search_vault →      │  │                                  │
│    KemsPlane.search() │  │  cockpit health --full 集成      │
└──────────────────────┘  └──────────────────────────────────┘
         ↕ import
┌──────────────────────────────────────────────────────────┐
│               L2 · metaos / minerva / omo                  │
│                                                          │
│  metaos cards_context → l4_kernel.CardsPlane              │
│  minerva VaultSink → l4_kernel.KemsPlane                  │
│  omo domain audit → l4_kernel.DomainHealth                │
└──────────────────────────────────────────────────────────┘
```

---

## 二、集成步骤

### 2.1 I0 · agora 集成

**agora-services.json 新增**:
```json
{
  "name": "l4-kernel",
  "description": "L4 自我层管理面 — 21域统一注册 + KEMS六面 + 42 MCP tools",
  "protocol": "mcp",
  "mcp_endpoint": "stdio://l4-kernel",
  "health_endpoint": "http://localhost:7455/health",
  "port": 7455,
  "tags": ["l4", "domain", "kems", "knowledge-management"],
  "healthy": true
}
```

**agora-routes.json 新增 (42 条路由)**:
```json
{
  "l4_domains_list": "l4-kernel",
  "l4_domain_info": "l4-kernel",
  "l4_domain_create": "l4-kernel",
  "l4_domain_validate": "l4-kernel",
  "l4_state_read": "l4-kernel",
  "l4_memory_read": "l4-kernel",
  "l4_signals_list": "l4-kernel",
  "l4_signal_emit": "l4-kernel",
  "l4_search": "l4-kernel",
  "l4_cross_search": "l4-kernel",
  "l4_health": "l4-kernel",
  "l4_dashboard": "l4-kernel",
  "l4_cards_list": "l4-kernel",
  "l4_cards_get": "l4-kernel",
  "l4_cards_check": "l4-kernel",
  ...
}
```

### 2.2 L3 · cockpit 集成

**cockpit/pyproject.toml**:
```toml
[project.optional-dependencies]
l4 = ["l4-kernel"]

[tool.uv.sources]
l4-kernel = { path = "../l4-kernel", editable = true }
```

**cockpit_mcp.py 替换**:
```python
# 替换前:
_CARDS_DIR = Path.home() / "Documents" / "驾驶舱" / "CARDS"
_L4_DOMAINS = { ... }

# 替换后:
from l4_kernel import DomainRegistry
from l4_kernel.kems import KemsPlane, CardsPlane

_registry = DomainRegistry()

def _search_vault(keyword, domain="vault"):
    d = _registry.get(domain)
    return KemsPlane(d.path).search(keyword) if d else []

def _scan_cards():
    cockpit = _registry.get("cockpit")
    return CardsPlane(cockpit.path).scan_cards() if cockpit else []
```

### 2.3 L1 · runtime cron 集成

**l4_kernel_jobs.yaml**:
```yaml
- name: "l4-domain-health-scan"
  schedule: "0 6 * * *"
  script: "l4-kernel health --json"
  deliver: "local"
  timeout: 60
  enabled: true

- name: "l4-freshness-scan"
  schedule: "0 2 * * *"
  script: "l4-kernel domain check --freshness --json"
  deliver: "local"
  timeout: 60
  enabled: true
```

### 2.4 ecos-link 注册

```bash
ecos-link install  # 自动包含 l4-kernel CLI
```

---

## 三、实施

现在开始实施 cockpit 集成和 agora 注册。