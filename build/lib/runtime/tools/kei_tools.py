from .shared import PROJECT_HOME

def _kei_list() -> str:
    import yaml
    reg_file = PROJECT_HOME / "protocols" / "kei-extensions.yaml"
    if not reg_file.exists():
        return "❌ KEI Extension Registry not found"
    data = yaml.safe_load(reg_file.read_text())
    exts = data.get("extensions", [])
    lines = [f"{'ID':40s} {'TYPE':16s} {'STATUS':12s}", "-" * 75]
    for e in exts:
        lines.append(f"{e['id']:40s} {e.get('type','?'):16s} {e.get('status','?'):12s}")
    lines.append(f"\nTotal: {len(exts)} extensions registered")
    return "\n".join(lines)

def _kei_inspect(ext_id: str) -> str:
    import yaml
    reg_file = PROJECT_HOME / "protocols" / "kei-extensions.yaml"
    if not reg_file.exists():
        return "❌ KEI Extension Registry not found"
    data = yaml.safe_load(reg_file.read_text())
    exts = data.get("extensions", [])
    e = next((x for x in exts if x["id"] == ext_id), None)
    if not e:
        return f"❌ Extension not found: {ext_id}"
    lines = [f"ID:          {e['id']}", f"Name:        {e['name']}", f"Version:     {e['version']}",
             f"Type:        {e.get('type','?')}", f"Status:      {e.get('status','?')}",
             f"Entry:       {e.get('entrypoint','?')}", f"Desc:        {e.get('description','')}", ""]
    perms = e.get("permissions", {})
    lines.append(f"Permissions:")
    for k, v in perms.items():
        lines.append(f"  {k}: {v}")
    rules = e.get("kei_rules", {})
    lines.append(f"\nKEI Rules:")
    for k, v in rules.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)

TOOLS = [
    {
        "name": "kei_list",
        "description": "List all registered KEI extensions and their status.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda args: _kei_list(),
    },
    {
        "name": "kei_inspect",
        "description": "Inspect a specific KEI extension's manifest and permissions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "extension_id": {"type": "string", "description": "Extension ID (e.g. ecos.plane.governance)"}
            },
            "required": ["extension_id"],
        },
        "handler": lambda args: _kei_inspect(args["extension_id"]),
    }
]
