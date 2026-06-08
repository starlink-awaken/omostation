from .shared import PROJECT_HOME

def _protocol_list() -> str:
    from runtime.protocol import L0_PROTOCOLS
    icons = {"active": "✅", "draft": "📝", "planned": "🔲", "deprecated": "🗄️"}
    parts = [f"{'PROTOCOL':25s} {'VERSION':12s} {'CATEGORY':22s} {'STATUS':10s}", "-" * 75]
    for p in L0_PROTOCOLS:
        icon = icons.get(p.status, "❓")
        parts.append(f"{icon} {p.name:22s} {p.version:12s} {p.category:22s} {p.status:10s}")
    parts.append(f"\nTotal: {len(L0_PROTOCOLS)} protocols")
    return "\n".join(parts)

def _protocol_get(name: str) -> str:
    from runtime.protocol import get_protocol
    p = get_protocol(name)
    if not p: return f"❌ Protocol not found: {name}"
    lines = [f"Protocol:  {p.name} v{p.version}", f"Category:  {p.category}", f"Status:    {p.status}", f"Desc:      {p.description}"]
    if p.spec_url: lines.append(f"Spec:      {p.spec_url}")
    if p.port_range: lines.append(f"Ports:     {p.port_range}")
    lines.append(f"Transport: {', '.join(p.transport)}")
    return "\n".join(lines)

def _plane_list() -> str:
    import yaml
    registry_file = PROJECT_HOME / "protocols" / "tri-plane-registry.yaml"
    if not registry_file.exists():
        return "❌ Tri-Plane Registry not found"
    data = yaml.safe_load(registry_file.read_text())
    planes = data.get("planes", {})
    lines = [f"{'PLANE':15s} {'STATUS':10s} {'CAPABILITIES':30s}", "-" * 60]
    for name, p in planes.items():
        caps = len(p.get("capabilities", []))
        lines.append(f"{p['name']:15s} {p.get('status', '?'):10s} {caps} capabilities")
    lines.append(f"\nTotal: {len(planes)} planes registered")
    return "\n".join(lines)

def _plane_capabilities(plane_name: str) -> str:
    import yaml
    registry_file = PROJECT_HOME / "protocols" / "tri-plane-registry.yaml"
    if not registry_file.exists():
        return "❌ Tri-Plane Registry not found"
    data = yaml.safe_load(registry_file.read_text())
    planes = data.get("planes", {})
    p = planes.get(plane_name)
    if not p:
        return f"❌ Plane not found: {plane_name}"
    lines = [f"Plane:      {p['name']}", f"Status:     {p.get('status', '?')}",
             f"Runtime:    {p.get('runtime', '?')}", f"Entry:      {p.get('entry', '?')}",
             f"Code:       {p.get('code', '?')}", f"Description: {p.get('description', '')}", ""]
    caps = p.get("capabilities", [])
    lines.append(f"Capabilities ({len(caps)}):")
    for c in caps:
        lines.append(f"  • {c['name']}: {c['description']}")
    return "\n".join(lines)

TOOLS = [
    {
        "name": "runtime_protocol_list",
        "description": "List all L0 protocols in the registry.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _protocol_list(),
    },
    {
        "name": "runtime_protocol_get",
        "description": "Get detailed info about a specific protocol.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Protocol name"}},
            "required": ["name"],
        },
        "handler": lambda args: _protocol_get(args["name"]),
    },
    {
        "name": "runtime_ontology_get",
        "description": "Get the eCOS v5 Meta-Model Ontology (L0 SSOT).",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: (PROJECT_HOME / "protocols" / "ecos-ontology.yaml").read_text() if (PROJECT_HOME / "protocols" / "ecos-ontology.yaml").exists() else "Ontology not found",
    },
    {
        "name": "plane_list",
        "description": "List all L2 Kernel Tri-Planes (governance/engine/memory) and their capabilities.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _plane_list(),
    },
    {
        "name": "plane_capabilities",
        "description": "Get detailed capabilities of a specific L2 kernel plane.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "plane": {
                    "type": "string",
                    "enum": ["governance", "engine", "memory"],
                    "description": "Plane name: governance (OMO), engine (kairon), memory (gbrain)",
                }
            },
            "required": ["plane"],
        },
        "handler": lambda args: _plane_capabilities(args["plane"]),
    }
]
