"""Cockpit Web Dashboard — HTTP server with real-time status from I0 + L4.

Serves the cockpit status dashboard with live data from I0 Fabric and L4 bridge.

Endpoints:
  GET /              → dashboard HTML
  GET /api/status    → i0_status() JSON
  GET /api/services  → i0_services() JSON
  GET /api/events    → i0_events(50) JSON
  GET /api/protocols → i0_protocols() JSON
  GET /api/debt      → debt ledger JSON
  GET /api/context   → workspace_context JSON (L4 bridge)
  GET /api/cards     → cards_status JSON (L4 bridge)

Usage:
    cockpit dashboard
    # or
    python3 -m cockpit.dashboard_server
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# ─── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent  # cockpit/src/cockpit/
OMO_ROOT = Path.home() / "Workspace/projects/omo"
DASHBOARD_HTML = PROJECT_ROOT / "templates" / "dashboard.html"

# Ensure both runtime/src and omo/src are on sys.path for imports
_runtime_src = str(PROJECT_ROOT / "src")
_omo_src = str(OMO_ROOT / "src")
for p in [_runtime_src, _omo_src]:
    if p not in sys.path:
        sys.path.insert(0, p)

# L4 bridge imports (try/except for graceful degradation)
try:
    from cockpit.scripts.cockpit_mcp import workspace_context, cards_status, cards_check, vault_search

    _HAS_L4_BRIDGE = True
except ImportError:
    _HAS_L4_BRIDGE = False

PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))


# ─── Live-Data JS Snippet ──────────────────────────────────────────────────
# This snippet is injected into the dashboard HTML before </body>.
# It replaces the static DEBTS/... constants with live fetch() calls.
LIVE_DATA_JS = r'''
<script>
// ─── Live dashboard: fetch + re-render with I0 Fabric API ────────────────
// Cache original static data so we can merge fallbacks
const STATIC_DEBTS = typeof DEBTS !== 'undefined' ? DEBTS : [];
const STATIC_TIERS = typeof TIERS !== 'undefined' ? TIERS : [];
const STATIC_POLICIES = typeof POLICIES !== 'undefined' ? POLICIES : [];
const STATIC_RULES = typeof RULES !== 'undefined' ? RULES : [];
const STATIC_TIER_COUNTS = typeof TIER_COUNTS !== 'undefined' ? TIER_COUNTS : {};
const STATIC_POLICY_COUNTS = typeof POLICY_COUNTS !== 'undefined' ? POLICY_COUNTS : {};
const STATIC_RULE_COUNTS = typeof RULE_COUNTS !== 'undefined' ? RULE_COUNTS : {};
const STATIC_SEV_COLORS = typeof SEV_COLORS !== 'undefined' ? SEV_COLORS : {};

async function loadLiveDebt() {
  try {
    const resp = await fetch('/api/debt');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const ledger = await resp.json();
    if (ledger.error) { console.warn('Debt API error:', ledger.error); return; }

    const items = ledger.items || [];
    // Rebuild tier counts
    const tierCounts = {};
    const policyCounts = {};
    const ruleCounts = {};
    STATIC_TIERS.forEach(t => { tierCounts[t.id] = { count: 0, color: t.color }; });
    STATIC_POLICIES.forEach(p => { policyCounts[p.id] = { ...p, count: 0 }; });
    STATIC_RULES.forEach(r => { ruleCounts[r.id] = { ...r, count: 0 }; });

    items.forEach(d => {
      const tier = d.x3 || d.x3_tier;
      if (tier && tierCounts[tier]) tierCounts[tier].count++;
      // x1_policy_ref may be a string or array; normalize
      const refs = Array.isArray(d.x1) ? d.x1 : (d.x1_policy_refs || []);
      refs.forEach(p => { if (policyCounts[p]) policyCounts[p].count++; });
      // x2 rules
      (d.x2 || []).forEach(r => { if (ruleCounts[r]) ruleCounts[r].count++; });
    });

    // Reassign globals for existing render functions
    window.DEBTS = items;
    window.TIER_COUNTS = tierCounts;
    window.POLICY_COUNTS = policyCounts;
    window.RULE_COUNTS = ruleCounts;

    // Re-render
    renderTierChart();
    renderPolicyGrid();
    renderX2Grid();
    populateFilters();
    renderTable(items);
  } catch(e) {
    console.warn('Live debt unavailable, using static data:', e);
  }
}

async function loadLiveStatus() {
  try {
    const [status, services] = await Promise.all([
      fetch('/api/status').then(r => r.ok ? r.json() : null),
      fetch('/api/services').then(r => r.ok ? r.json() : null)
    ]);
    if (status) {
      // Update header meta
      const meta = document.querySelector('.header .meta');
      if (meta) {
        const el = document.querySelector('.header .meta span:first-child');
        if (el) el.textContent = '📦 ' + (status.total_services || '?') + ' services';
      }
    }
    // Update the first card (Total Items → show live service count)
    const card = document.querySelector('.card-stat:first-child .value');
    if (card && services) {
      const online = services.filter(s => s.port_listening).length;
      card.textContent = online + '/' + services.length;
      card.style.color = online === services.length ? '#4ade80' : '#fbbf24';
    }
  } catch(e) {
    console.log('Status unavailable:', e);
  }
}

// Run on page load
loadLiveDebt();
loadLiveStatus();
// Auto-refresh status every 30s, debt every 60s
setInterval(loadLiveStatus, 30000);
setInterval(loadLiveDebt, 60000);
</script>'''


# ─── Dashboard Handler ─────────────────────────────────────────────────────

class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the live I0 dashboard."""

    def do_GET(self):
        if self.path == "/":
            self.serve_dashboard()
        elif self.path.startswith("/api/"):
            self.serve_api()
        elif self.path == "/favicon.ico":
            self.send_error(404)
        else:
            self.send_error(404)

    def serve_dashboard(self):
        """Serve dashboard.html with live-data JS injected before </body>."""
        if not DASHBOARD_HTML.exists():
            html = f"""<!DOCTYPE html><html><body><h1>Dashboard not found</h1>
<p>Expected at: {DASHBOARD_HTML}</p></body></html>"""
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        html = DASHBOARD_HTML.read_text(encoding="utf-8")
        # Inject live-data JS before </body>
        html = html.replace("</body>", LIVE_DATA_JS + "\n</body>")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def serve_api(self):
        """Route API requests to the appropriate I0 query function."""
        try:
            from runtime.i0 import i0_status, i0_services, i0_events, i0_protocols
        except ImportError:
            i0_status = i0_services = i0_events = i0_protocols = None

        if self.path == "/api/status":
            data = i0_status() if i0_status else {"error": "runtime.i0 not available"}
        elif self.path == "/api/services":
            data = i0_services() if i0_services else {"error": "runtime.i0 not available"}
        elif self.path == "/api/events":
            data = i0_events(50) if i0_events else {"error": "runtime.i0 not available"}
        elif self.path == "/api/protocols":
            data = i0_protocols() if i0_protocols else {"error": "runtime.i0 not available"}
        elif self.path == "/api/debt":
            data = _load_debt()
        elif self.path == "/api/e2e":
            data = _run_e2e()
        elif self.path == "/api/omo-report":
            data = _omo_report()
        elif self.path == "/api/context":
            data = json.loads(workspace_context()) if _HAS_L4_BRIDGE else {"error": "L4 bridge not available"}
        elif self.path == "/api/cards":
            data = json.loads(cards_status()) if _HAS_L4_BRIDGE else {"error": "L4 bridge not available"}
        elif self.path == "/api/cards/check":
            data = json.loads(cards_check()) if _HAS_L4_BRIDGE else {"error": "L4 bridge not available"}
        elif self.path == "/api/vault/search":
            data = json.loads(vault_search()) if _HAS_L4_BRIDGE else {"error": "L4 bridge not available"}
        else:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))


# ─── Debt Ledger Loader ────────────────────────────────────────────────────

def _load_debt() -> dict:
    """Load OMO debt ledger from the filesystem and return a JSON-safe dict."""
    try:
        from omo.omo_debt_registry import load_debt_ledger

        omo_dir = OMO_ROOT / ".omo"
        if not omo_dir.exists():
            return {"error": f"OMO directory not found at {omo_dir}", "items": []}

        ledger = load_debt_ledger(omo_dir)

        # Normalize items for the dashboard JS
        items = []
        for i in ledger.items:
            items.append({
                "id": i.id,
                "title": i.title,
                "dimension": i.dimension,
                "subdimension": i.subdimension,
                "domain": i.domain,
                "scope": i.scope,
                "severity": i.severity,
                "weight": i.weight,
                "entropy_class": i.entropy_class,
                "lifecycle_state": i.lifecycle_state,
                "owner": i.owner,
                "affected_roots": list(i.affected_roots),
                "evidence_refs": list(i.evidence_refs),
                "mitigation_refs": list(i.mitigation_refs),
                "opened_at": i.opened_at,
                "last_reviewed_at": i.last_reviewed_at,
                "next_review_at": i.next_review_at,
                "gate_level": i.gate_level,
                "history": list(i.history),
                # Normalize: dashboard expects x1_policy_refs (array), x2_freshness, x3_tier
                "x1_policy_refs": [i.x1_policy_ref] if i.x1_policy_ref else [],
                "x1_policy_ref": i.x1_policy_ref,
                "x1": [i.x1_policy_ref] if i.x1_policy_ref else [],
                "x2_freshness": i.x2_freshness,
                "x2": [],
                "x3_tier": i.x3_tier,
                "x3": i.x3_tier,
            })

        return {
            "total": len(items),
            "open": sum(1 for i in ledger.items if i.lifecycle_state != "closed"),
            "closed": sum(1 for i in ledger.items if i.lifecycle_state == "closed"),
            "items": items,
        }
    except ImportError as e:
        return {"error": f"Import error: {e}", "items": []}
    except Exception as e:
        return {"error": str(e), "items": []}


# ─── E2E Check & OMO Report ────────────────────────────────────────────────

def _run_e2e() -> dict:
    """Run the e2e check and return results."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "runtime.e2e"],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        stdout = result.stdout
        m = re.search(r"Result:\s*(\d+)/(\d+)\s*checks\s*passed", stdout)
        if m:
            return {"result": f"{m.group(1)}/{m.group(2)} passed", "output": stdout}
        return {"result": "unparsed", "output": stdout}
    except subprocess.TimeoutExpired:
        return {"result": "timeout", "error": "E2E took >30s"}
    except Exception as e:
        return {"result": "error", "error": str(e)}


def _omo_report() -> dict:
    """Generate OMO summary report."""
    try:
        omo_dir = OMO_ROOT / ".omo"
        items_dir = omo_dir / "debt" / "items"
        files = sorted(items_dir.glob("*.yaml")) if items_dir.exists() else []
        items = []
        for f in files:
            import yaml
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            items.append(d)
        open_count = sum(1 for i in items if i.get("lifecycle_state") not in ("closed", "resolved"))
        closed_count = sum(1 for i in items if i.get("lifecycle_state") in ("closed", "resolved"))
        return {
            "summary": f"{len(items)} items, {open_count} open, {closed_count} closed",
            "total": len(items),
            "open": open_count,
            "closed": closed_count,
        }
    except Exception as e:
        return {"error": str(e), "summary": "Error"}


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    """Start the dashboard HTTP server."""
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"🚀 Cockpit Web Dashboard")
    if _HAS_L4_BRIDGE:
        print(f"   L4 Bridge:  http://127.0.0.1:{PORT}/api/context (workspace_context)")
        print(f"   L4 Bridge:  http://127.0.0.1:{PORT}/api/cards (cards_status)")
        print(f"   L4 Bridge:  http://127.0.0.1:{PORT}/api/cards/check (cards_check)")
    print(f"   I0 Status:  http://127.0.0.1:{PORT}/api/status")
    print(f"   I0 Services: http://127.0.0.1:{PORT}/api/services")
    print(f"   Debt:       http://127.0.0.1:{PORT}/api/debt")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
