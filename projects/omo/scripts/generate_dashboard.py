#!/usr/bin/env python3
"""
OMO Debt Dashboard Generator
Reads all debt item YAML files and generates a self-contained HTML dashboard.
"""

import yaml
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEBT_DIR = Path.home() / "Workspace" / ".omo" / "debt" / "items"
OUTPUT = Path.home() / "Workspace" / "projects" / "omo" / "debt" / "dashboard.html"
SCRIPT_DIR = Path.home() / "Workspace" / "projects" / "omo" / "scripts"

# X3 Tier definitions from x3-value-stack.yaml
X3_TIERS = [
    {"id": "Axiom",     "color": "#c084fc", "weight": 2.0, "half_life": "50 years"},
    {"id": "Principle", "color": "#818cf8", "weight": 1.5, "half_life": "8 years"},
    {"id": "Theory",    "color": "#38bdf8", "weight": 1.5, "half_life": "20 years"},
    {"id": "Framework", "color": "#4ade80", "weight": 1.2, "half_life": "4 years"},
    {"id": "Knowledge", "color": "#fbbf24", "weight": 1.0, "half_life": "2 years"},
    {"id": "Skill",     "color": "#fb923c", "weight": 0.8, "half_life": "9 months"},
    {"id": "Tool",      "color": "#f87171", "weight": 0.6, "half_life": "3 months"},
]

# X1 Governance Policies from x1-governance-policies.yaml
X1_POLICIES = [
    {"id": "X1-AUDIT-001",   "name": "审计完整性",     "category": "audit",          "level": "mandatory"},
    {"id": "X1-AUDIT-002",   "name": "权限最小化",     "category": "authorization",  "level": "mandatory"},
    {"id": "X1-AUTH-001",    "name": "身份追踪",       "category": "identity",       "level": "advisory"},
    {"id": "X1-TRUST-001",   "name": "治理链完整性",   "category": "trust",          "level": "advisory"},
    {"id": "X1-CONST-001",   "name": "宪法遵从",       "category": "constitution",   "level": "mandatory"},
]

# X2 Lifecycle Rules from x2-lifecycle-rules.yaml
X2_RULES = [
    {"id": "X2-FRESH-001",      "name": "服务保鲜",     "category": "freshness",  "interval": "30 days"},
    {"id": "X2-FRESH-002",      "name": "知识保鲜",     "category": "freshness",  "interval": "7 days"},
    {"id": "X2-LIFECYCLE-001",  "name": "闲置退役",     "category": "lifecycle",  "interval": "30 days"},
    {"id": "X2-LIFECYCLE-002",  "name": "债务半衰期",   "category": "lifecycle",  "interval": "N/A"},
]

# X3 tier mapping based on debt dimension
DIMENSION_TO_X3 = {
    "architecture": "Framework",
    "governance_process": "Principle",
    "product": "Theory",
    "code_test": "Skill",
    "runtime_ops": "Tool",
    "technical": "Knowledge",
    "documentation": "Knowledge",
    "product_quality": "Framework",
}

# X1 policy mapping based on subdimension/domain
SUBDIM_TO_X1 = {
    "security": ["X1-AUDIT-001", "X1-AUDIT-002"],
    "runtime_monitoring": ["X1-CONST-001"],
    "protocol_registry": ["X1-CONST-001"],
    "anti_entropy": ["X1-TRUST-001"],
    "cost_accounting": ["X1-TRUST-001"],
    "ssot_semantics": ["X1-TRUST-001"],
    "planning_readiness": ["X1-CONST-001"],
    "accuracy": ["X1-TRUST-001"],
    "portability": ["X1-AUDIT-002"],
    "code_quality": ["X1-AUDIT-001"],
    "baseline_coverage": ["X1-CONST-001"],
    "isolation_test_coverage": ["X1-CONST-001"],
    "ci_environment": ["X1-AUDIT-001"],
    "user_surface": ["X1-AUTH-001"],
    "service_mesh": ["X1-AUDIT-002"],
    "integration_bridge": ["X1-AUDIT-002"],
    "platform_decomposition": ["X1-CONST-001"],
    "residual_surface": ["X1-TRUST-001"],
    "registry_freshness": ["X1-CONST-001"],
}

DOMAIN_TO_X1 = {
    ".omo": ["X1-CONST-001", "X1-TRUST-001"],
    "workspace": ["X1-AUDIT-001"],
    "projects": ["X1-AUDIT-002"],
}

SEVERITY_COLORS = {
    "critical": "#f87171",
    "high": "#fb923c",
    "medium": "#fbbf24",
    "low": "#a3e635",
}

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def get_x3_tier(debt):
    """Derive X3 tier from debt dimension."""
    dim = debt.get("dimension", "").lower()
    return DIMENSION_TO_X3.get(dim, "Knowledge")


def get_x1_policy_refs(debt):
    """Derive X1 policy references from debt."""
    refs = set()
    subdim = debt.get("subdimension", "").lower()
    domain = debt.get("domain", "").lower()
    debt_id = debt.get("id", "").upper()

    # Direct mapping from subdimension
    if subdim in SUBDIM_TO_X1:
        for r in SUBDIM_TO_X1[subdim]:
            refs.add(r)

    # Mapping from domain
    if domain in DOMAIN_TO_X1:
        for r in DOMAIN_TO_X1[domain]:
            refs.add(r)

    # Items with X1- prefix map to specific policies
    if debt_id.startswith("X1-"):
        refs.add("X1-CONST-001")
        if "audit" in debt_id.lower():
            refs.add("X1-AUDIT-001")

    # If nothing matched, default to most relevant
    if not refs:
        refs.add("X1-CONST-001")

    return sorted(refs)


def get_x2_rules(debt):
    """Derive X2 lifecycle rules from debt."""
    rules = set()
    entropy = debt.get("entropy_class", "").lower()
    dim = debt.get("dimension", "").lower()
    debt_id = debt.get("id", "").upper()

    if entropy == "time":
        rules.add("X2-FRESH-001")
    if dim in ("knowledge", "documentation"):
        rules.add("X2-FRESH-002")
    if debt.get("lifecycle_state") == "closed":
        rules.add("X2-LIFECYCLE-001")

    # All debts get the half-life rule
    rules.add("X2-LIFECYCLE-002")

    return sorted(rules)


def load_debt_items():
    """Load all debt item YAML files."""
    items = []
    if not DEBT_DIR.exists():
        print(f"WARNING: Debt directory not found at {DEBT_DIR}")
        return items

    yaml_files = sorted(DEBT_DIR.glob("*.yaml"))
    print(f"Found {len(yaml_files)} YAML files in {DEBT_DIR}")

    for fpath in yaml_files:
        with open(fpath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not data or not isinstance(data, dict):
            print(f"  SKIP (empty/invalid): {fpath.name}")
            continue
        if "id" not in data:
            print(f"  SKIP (no id): {fpath.name}")
            continue

        # Derive X1/X2/X3 fields
        data["x3_tier"] = get_x3_tier(data)
        data["x1_policy_refs"] = get_x1_policy_refs(data)
        data["x2_rules"] = get_x2_rules(data)
        data["x2_freshness"] = data.get("x2_freshness", "")

        items.append(data)
        print(f"  LOADED: {data['id']} | sev={data.get('severity','?')} | x3={data['x3_tier']} | x1={','.join(data['x1_policy_refs'])}")

    print(f"Total loaded: {len(items)} debt items")
    return items


def generate_html(items):
    """Generate the complete HTML dashboard."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(items)
    open_items = [d for d in items if d.get("lifecycle_state") == "open"]
    critical_items = [d for d in items if d.get("severity") == "critical"]
    closed_items = [d for d in items if d.get("lifecycle_state") == "closed"]

    # X3 tier breakdown
    tier_counts = {}
    for t in X3_TIERS:
        tier_counts[t["id"]] = {"count": 0, "color": t["color"]}
    for d in items:
        t = d.get("x3_tier", "Knowledge")
        if t in tier_counts:
            tier_counts[t]["count"] += 1
        else:
            tier_counts[t] = {"count": 1, "color": "#94a3b8"}

    # X1 policy coverage
    policy_counts = {}
    for p in X1_POLICIES:
        policy_counts[p["id"]] = {"name": p["name"], "count": 0, "category": p["category"], "level": p["level"]}
    for d in items:
        for ref in d.get("x1_policy_refs", []):
            if ref in policy_counts:
                policy_counts[ref]["count"] += 1

    # Build X2 rule coverage
    rule_counts = {}
    for r in X2_RULES:
        rule_counts[r["id"]] = {"name": r["name"], "count": 0, "category": r["category"]}
    for d in items:
        for rule in d.get("x2_rules", []):
            if rule in rule_counts:
                rule_counts[rule]["count"] += 1

    # Sort items by severity (critical first)
    sorted_items = sorted(items, key=lambda d: (SEVERITY_ORDER.get(d.get("severity", "low"), 99), d.get("id", "")))

    # JSON data for embedding in HTML
    debt_json = json.dumps(sorted_items, ensure_ascii=False)
    tiers_json = json.dumps(X3_TIERS)
    policies_json = json.dumps(X1_POLICIES)
    rules_json = json.dumps(X2_RULES)
    tier_counts_json = json.dumps(tier_counts)
    policy_counts_json = json.dumps(policy_counts)
    rule_counts_json = json.dumps(rule_counts)
    severity_colors_json = json.dumps(SEVERITY_COLORS)

    # Unique X1 policies referenced
    x1_refs_count = sum(1 for p in policy_counts.values() if p["count"] > 0)
    coverage_pct = round(x1_refs_count / len(X1_POLICIES) * 100) if X1_POLICIES else 0

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMO Debt Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  :root {{
    --bg: #0a0a0f;
    --surface: #141420;
    --surface-2: #1a1a2e;
    --border: #282840;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --accent: #38bdf8;
    --accent-glow: rgba(56, 189, 248, 0.15);
  }}
  * {{ box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    margin: 0;
    padding: 0;
    min-height: 100vh;
  }}
  .dashboard {{ max-width: 1400px; margin: 0 auto; padding: 24px 20px; }}
  .header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 20px 24px; margin-bottom: 28px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px;
  }}
  .header h1 {{
    font-size: 24px; font-weight: 700; margin: 0;
    background: linear-gradient(135deg, var(--accent), #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }}
  .header .meta {{ font-size: 13px; color: var(--text-muted); }}
  .header .meta span {{ margin-left: 16px; }}

  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px; }}
  .card-stat {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px 20px;
  }}
  .card-stat .label {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
  .card-stat .value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
  .card-stat .value.accent {{ color: var(--accent); }}
  .card-stat .value.green {{ color: #4ade80; }}
  .card-stat .value.red {{ color: #f87171; }}
  .card-stat .value.yellow {{ color: #fbbf24; }}

  .section {{ margin-bottom: 28px; }}
  .section-title {{
    font-size: 16px; font-weight: 600; margin-bottom: 12px;
    padding-bottom: 8px; border-bottom: 1px solid var(--border);
    color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;
  }}

  .tier-chart {{ display: flex; gap: 8px; height: 200px; align-items: flex-end; padding: 8px 0; }}
  .tier-bar {{
    flex: 1; display: flex; flex-direction: column; align-items: center;
    justify-content: flex-end; position: relative; min-width: 50px;
  }}
  .tier-bar-inner {{
    width: 100%; max-width: 60px; border-radius: 6px 6px 0 0;
    min-height: 8px; transition: height 0.5s ease;
    position: relative;
  }}
  .tier-bar .count {{
    position: absolute; top: -24px; font-size: 18px; font-weight: 700;
  }}
  .tier-bar .tier-label {{ margin-top: 8px; font-size: 11px; color: var(--text-muted); text-align: center; }}

  .filters {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
  .filters select {{
    background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px 14px; font-size: 13px;
    cursor: pointer; min-width: 150px;
  }}
  .filters select:focus {{ outline: none; border-color: var(--accent); }}
  .filter-count {{ font-size: 13px; color: var(--text-muted); padding: 8px 0; }}

  .table-wrap {{
    overflow-x: auto; border: 1px solid var(--border); border-radius: 10px;
    background: var(--surface);
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{
    background: var(--surface-2); padding: 10px 12px; text-align: left;
    font-weight: 600; color: var(--text-muted); text-transform: uppercase;
    font-size: 11px; letter-spacing: 0.5px; border-bottom: 1px solid var(--border);
    white-space: nowrap; cursor: pointer; user-select: none;
  }}
  th:hover {{ color: var(--accent); }}
  td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); }}
  tr:hover {{ background: rgba(56, 189, 248, 0.04); }}
  tr.row-closed {{ opacity: 0.55; }}
  .badge-sev {{
    display: inline-block; padding: 2px 10px; border-radius: 4px;
    font-size: 11px; font-weight: 600; text-transform: uppercase;
  }}
  .badge-tier {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 500;
  }}
  .badge-state-open {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 500; background: rgba(56, 189, 248, 0.15); color: #38bdf8;
  }}
  .badge-state-closed {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 500; background: rgba(74, 222, 128, 0.15); color: #4ade80;
  }}
  .badge-policy {{
    display: inline-block; padding: 1px 6px; border-radius: 3px;
    font-size: 10px; font-weight: 500; background: rgba(129, 140, 248, 0.15); color: #818cf8;
    margin: 1px 2px;
  }}
  .id-cell {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; color: var(--accent); }}
  .title-cell {{ max-width: 300px; }}
  .policy-cell {{ max-width: 200px; }}

  .policy-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 12px; margin-bottom: 20px;
  }}
  .policy-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px;
  }}
  .policy-card .pol-id {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 11px; color: var(--accent); }}
  .policy-card .pol-name {{ font-size: 14px; font-weight: 600; margin: 2px 0; }}
  .policy-card .pol-meta {{ font-size: 11px; color: var(--text-muted); }}
  .policy-card .pol-count {{ font-size: 20px; font-weight: 700; margin-top: 6px; }}
  .policy-bar-wrap {{ height: 4px; background: var(--border); border-radius: 2px; margin-top: 6px; overflow: hidden; }}
  .policy-bar-fill {{ height: 100%; border-radius: 2px; transition: width 0.5s ease; }}

  .x2-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px; margin-bottom: 20px;
  }}
  .x2-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 12px 14px;
  }}
  .x2-card .x2-id {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 10px; color: #4ade80; }}
  .x2-card .x2-name {{ font-size: 13px; font-weight: 500; }}
  .x2-card .x2-count {{ font-size: 18px; font-weight: 700; color: var(--accent); }}

  @media (max-width: 768px) {{
    .header {{ flex-direction: column; align-items: flex-start; gap: 8px; }}
    .header .meta span {{ display: block; margin-left: 0; }}
    .cards {{ grid-template-columns: repeat(2, 1fr); }}
    .tier-chart {{ height: 140px; }}
    .filters {{ flex-direction: column; }}
    .filters select {{ width: 100%; }}
  }}
</style>
</head>
<body>
<div class="dashboard">

  <!-- Header -->
  <div class="header">
    <div>
      <h1>⚡ OMO Debt Dashboard</h1>
      <div class="meta">
        <span>📦 {total} items</span>
        <span>🔓 {len(open_items)} open</span>
        <span>✅ {len(closed_items)} closed</span>
        <span>🔄 Generated: {now}</span>
      </div>
    </div>
  </div>

  <!-- Summary Cards -->
  <div class="cards">
    <div class="card-stat">
      <div class="label">Total Items</div>
      <div class="value accent">{total}</div>
    </div>
    <div class="card-stat">
      <div class="label">Open Items</div>
      <div class="value yellow">{len(open_items)}</div>
    </div>
    <div class="card-stat">
      <div class="label">Critical Items</div>
      <div class="value red">{len(critical_items)}</div>
    </div>
    <div class="card-stat">
      <div class="label">X1 Coverage</div>
      <div class="value green">{x1_refs_count}/{len(X1_POLICIES)}</div>
    </div>
    <div class="card-stat">
      <div class="label">Policies Referenced</div>
      <div class="value accent">{coverage_pct}%</div>
    </div>
  </div>

  <!-- X3 Tier Breakdown -->
  <div class="section">
    <div class="section-title">📊 X3 Value Tier Breakdown</div>
    <div class="tier-chart" id="tierChart"></div>
  </div>

  <!-- X1 Policy Coverage -->
  <div class="section">
    <div class="section-title">🔒 X1 Governance Policy Coverage</div>
    <div class="policy-grid" id="policyGrid"></div>
  </div>

  <!-- X2 Lifecycle Rule Coverage -->
  <div class="section">
    <div class="section-title">🔄 X2 Anti-Entropy Lifecycle Rules</div>
    <div class="x2-grid" id="x2Grid"></div>
  </div>

  <!-- Filter Controls -->
  <div class="section">
    <div class="section-title">🔍 Debt Explorer</div>
    <div class="filters">
      <select id="filterSeverity" onchange="applyFilters()"><option value="">All Severities</option></select>
      <select id="filterTier" onchange="applyFilters()"><option value="">All X3 Tiers</option></select>
      <select id="filterPolicy" onchange="applyFilters()"><option value="">All X1 Policies</option></select>
      <select id="filterState" onchange="applyFilters()"><option value="">All States</option>
        <option value="open">Open</option><option value="closed">Closed</option>
      </select>
      <select id="filterLens" onchange="applyFilters()"><option value="">All Lenses</option>
        <option value="X1">X1 (has policy ref)</option><option value="X2">X2 (has freshness)</option><option value="X3">X3 (has tier)</option>
      </select>
      <div class="filter-count" id="filterCount"></div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Title</th>
            <th>Severity</th>
            <th>X3 Tier</th>
            <th>X1 Policy</th>
            <th>State</th>
            <th>Freshness</th>
            <th>Dimension</th>
          </tr>
        </thead>
        <tbody id="debtTableBody"></tbody>
      </table>
    </div>
  </div>

  <div style="text-align:center; padding: 20px; color: var(--text-muted); font-size: 12px;">
    OMO Debt Dashboard · Generated {now} · {total} debt items from .omo/debt/items/
  </div>
</div>

<script>
const DEBTS = {debt_json};
const TIERS = {tiers_json};
const POLICIES = {policies_json};
const RULES = {rules_json};
const TIER_COUNTS = {tier_counts_json};
const POLICY_COUNTS = {policy_counts_json};
const RULE_COUNTS = {rule_counts_json};
const SEV_COLORS = {severity_colors_json};

// Populate tier chart
function renderTierChart() {{
  const chart = document.getElementById('tierChart');
  const maxCount = Math.max(1, ...Object.values(TIER_COUNTS).map(t => t.count));
  chart.innerHTML = '';
  TIERS.forEach(tier => {{
    const tc = TIER_COUNTS[tier.id] || {{count: 0, color: tier.color}};
    const pct = (tc.count / maxCount) * 100;
    const bar = document.createElement('div');
    bar.className = 'tier-bar';
    bar.innerHTML = `
      <div class="tier-bar-inner" style="height:${{pct}}%;background:${{tier.color}};">
        <div class="count" style="color:${{tier.color}}">${{tc.count}}</div>
      </div>
      <div class="tier-label">${{tier.id}}<br><span style="font-size:10px;opacity:0.6">×${{tier.weight}}</span></div>
    `;
    chart.appendChild(bar);
  }});
}}

// Populate policy grid
function renderPolicyGrid() {{
  const grid = document.getElementById('policyGrid');
  const maxCount = Math.max(1, ...Object.values(POLICY_COUNTS).map(p => p.count));
  grid.innerHTML = '';
  POLICIES.forEach(p => {{
    const pc = POLICY_COUNTS[p.id] || {{count: 0, name: p.name, category: p.category, level: p.level}};
    const pct = (pc.count / maxCount) * 100;
    const card = document.createElement('div');
    card.className = 'policy-card';
    card.innerHTML = `
      <div class="pol-id">${{p.id}}</div>
      <div class="pol-name">${{pc.name}}</div>
      <div class="pol-meta">${{pc.category}} · ${{pc.level}}</div>
      <div class="pol-count" style="color:${{pc.count > 0 ? '#38bdf8' : '#64748b'}}">${{pc.count}} debts</div>
      <div class="policy-bar-wrap"><div class="policy-bar-fill" style="width:${{pct}}%;background:${{pc.count > 0 ? '#38bdf8' : '#64748b'}}"></div></div>
    `;
    grid.appendChild(card);
  }});
}}

// Populate X2 grid
function renderX2Grid() {{
  const grid = document.getElementById('x2Grid');
  grid.innerHTML = '';
  RULES.forEach(r => {{
    const rc = RULE_COUNTS[r.id] || {{count: 0, name: r.name, category: r.category}};
    const card = document.createElement('div');
    card.className = 'x2-card';
    card.innerHTML = `
      <div class="x2-id">${{r.id}}</div>
      <div class="x2-name">${{rc.name}}</div>
      <div class="x2-count">${{rc.count}} debts</div>
      <div style="font-size:10px;color:var(--text-muted);margin-top:2px">${{rc.category}}</div>
    `;
    grid.appendChild(card);
  }});
}}

// Render debt table
function renderTable(items) {{
  const body = document.getElementById('debtTableBody');
  body.innerHTML = '';
  items.forEach(d => {{
    const sevColor = SEV_COLORS[d.severity] || '#94a3b8';
    const tier = TIERS.find(t => t.id === d.x3_tier) || {{color: '#94a3b8', id: d.x3_tier || '?'}};
    const isClosed = d.lifecycle_state === 'closed';
    const policies = (d.x1_policy_refs || []).map(p => `<span class="badge-policy">${{p}}</span>`).join('');

    const row = document.createElement('tr');
    row.className = isClosed ? 'row-closed' : '';
    const freshness = d.x2_freshness || '';
    row.innerHTML = `
      <td class="id-cell">${{d.id}}</td>
      <td class="title-cell">${{d.title || d.id}}</td>
      <td><span class="badge-sev" style="background:${{sevColor}}22;color:${{sevColor}}">${{d.severity||'?'}}</span></td>
      <td><span class="badge-tier" style="background:${{tier.color}}22;color:${{tier.color}}">${{tier.id}}</span></td>
      <td class="policy-cell">${{policies}}</td>
      <td><span class="badge-state-${{d.lifecycle_state||'open'}}">${{d.lifecycle_state||'open'}}</span></td>
      <td style="font-size:11px;color:var(--text-muted)">${{freshness ? freshness.slice(0,10) : '—'}}</td>
      <td style="font-size:11px;color:var(--text-muted)">${{d.dimension||''}}</td>
    `;
    body.appendChild(row);
  }});
  document.getElementById('filterCount').textContent = `Showing ${{items.length}} of ${{DEBTS.length}} items`;
}}

// Populate filter dropdowns
function populateFilters() {{
  const sevSet = new Set(); const tierSet = new Set(); const polSet = new Set();
  DEBTS.forEach(d => {{
    if (d.severity) sevSet.add(d.severity);
    if (d.x3_tier) tierSet.add(d.x3_tier);
    (d.x1_policy_refs || []).forEach(p => polSet.add(p));
  }});

  const sev = document.getElementById('filterSeverity');
  ['critical','high','medium','low'].forEach(s => {{
    if (sevSet.has(s)) {{ const o = document.createElement('option'); o.value=s; o.textContent=s.charAt(0).toUpperCase()+s.slice(1); sev.appendChild(o); }}
  }});

  const tier = document.getElementById('filterTier');
  TIERS.forEach(t => {{
    if (tierSet.has(t.id)) {{ const o = document.createElement('option'); o.value=t.id; o.textContent=t.id; tier.appendChild(o); }}
  }});

  const pol = document.getElementById('filterPolicy');
  [...polSet].sort().forEach(p => {{ const o = document.createElement('option'); o.value=p; o.textContent=p; pol.appendChild(o); }});
}}

// Apply filters
function applyFilters() {{
  const sev = document.getElementById('filterSeverity').value;
  const tier = document.getElementById('filterTier').value;
  const pol = document.getElementById('filterPolicy').value;
  const state = document.getElementById('filterState').value;
  const lens = document.getElementById('filterLens').value;

  let filtered = DEBTS.filter(d => {{
    if (sev && d.severity !== sev) return false;
    if (tier && d.x3_tier !== tier) return false;
    if (pol && !(d.x1_policy_refs || []).includes(pol)) return false;
    if (state && d.lifecycle_state !== state) return false;
    if (lens === 'X1' && (!d.x1_policy_refs || d.x1_policy_refs.length === 0)) return false;
    if (lens === 'X2' && !d.x2_freshness) return false;
    if (lens === 'X3' && !d.x3_tier) return false;
    return true;
  }});
  renderTable(filtered);
}}

// Init
renderTierChart();
renderPolicyGrid();
renderX2Grid();
populateFilters();
renderTable(DEBTS);
</script>
</body>
</html>"""

    return html


def validate_all_yaml():
    """Pre-check all YAML files before loading."""
    if not DEBT_DIR.exists():
        print(f"WARNING: Debt directory not found at {DEBT_DIR}")
        return True
    yaml_files = sorted(DEBT_DIR.glob("*.yaml"))
    broken = []
    for fpath in yaml_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                yaml.safe_load(f)
        except Exception as e:
            broken.append((fpath.name, str(e)))
    if broken:
        print(f"\n⚠ YAML VALIDATION FAILED: {len(broken)} broken file(s):")
        for name, err in broken:
            print(f"  ✗ {name}: {err.split(chr(10))[0]}")
        return False
    print(f"✅ YAML validation: {len(yaml_files)} files OK")
    return True


def main():
    print("=" * 60)
    print("OMO Debt Dashboard Generator")
    print("=" * 60)
    print(f"Source: {DEBT_DIR}")
    print(f"Output: {OUTPUT}")
    print()

    if not validate_all_yaml():
        print("ERROR: YAML validation failed. Aborting.")
        return 1

    items = load_debt_items()
    if not items:
        print("ERROR: No debt items loaded. Aborting.")
        return 1

    html = generate_html(items)

    # Ensure output directory exists
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"\n✅ Dashboard generated: {OUTPUT}")
    print(f"   Size: {size_kb:.1f} KB")
    print(f"   Items: {len(items)}")
    print(f"   X3 Tiers: {len(X3_TIERS)}")
    print(f"   X1 Policies: {len(X1_POLICIES)}")
    print(f"   X2 Rules: {len(X2_RULES)}")

    if size_kb < 10:
        print("⚠️  WARNING: File size < 10KB, may be incomplete!")
        return 1

    print("✅ Dashboard generation complete!")
    return 0


if __name__ == "__main__":
    exit(main())
