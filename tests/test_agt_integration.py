from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "projects/ecos/src/ecos/ssot/mof/m1/component"
BOSROUTE_DIR = ROOT / "projects/ecos/src/ecos/ssot/mof/m1/bosroute"
PROPOSAL_DIR = ROOT / ".omo/_knowledge/workflow-mesh/external-resource-pack-proposals"
INTEGRATION_CONFIG = ROOT / "projects/agora/etc/agt-integration.yaml"
X3_VALUE_STACK = ROOT / ".omo/_truth/x3-value-stack.yaml"
X1_POLICIES = ROOT / ".omo/_truth/x1-governance-policies.yaml"
L0_CONSTRAINTS = ROOT / "projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml"


def test_agt_proposal_exists() -> None:
    proposals = list(PROPOSAL_DIR.glob("*agt*"))
    assert len(proposals) >= 1, "AGT external resource proposal not found"
    proposal = yaml.safe_load(proposals[0].read_text(encoding="utf-8"))
    assert proposal["pack_id"] == "agt-toolkit-v5"
    assert proposal["status"] == "proposal_only"
    assert proposal["license"] == "MIT"
    assert len(proposal.get("components", [])) == 8


def test_agt_m1_components_registered() -> None:
    components = list(COMPONENT_DIR.glob("COMP-EXT-AGT-*.yaml"))
    assert len(components) == 8, f"Expected 8 AGT components, found {len(components)}"
    ids = {c.stem for c in components}
    expected = {
        "COMP-EXT-AGT-kernel",
        "COMP-EXT-AGT-mesh",
        "COMP-EXT-AGT-runtime",
        "COMP-EXT-AGT-sre",
        "COMP-EXT-AGT-gateway",
        "COMP-EXT-AGT-marketplace",
        "COMP-EXT-AGT-lightning",
        "COMP-EXT-AGT-hypervisor",
    }
    assert ids == expected, f"Component IDs mismatch: {ids}"


def test_agt_m1_components_have_valid_status() -> None:
    for path in COMPONENT_DIR.glob("COMP-EXT-AGT-*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["type"] == "Component"
        assert data["status"] in {"active", "degraded", "stopped", "archived"}
        assert data["m3_parent"] == "StructuralElement.Component"
        assert "state_history" in data


def test_agt_bosroutes_registered() -> None:
    routes = list(BOSROUTE_DIR.glob("BOSROUTE-AGT-*.yaml"))
    assert len(routes) == 8, f"Expected 8 AGT BOSRoutes, found {len(routes)}"
    ids = {r.stem for r in routes}
    expected = {
        "BOSROUTE-AGT-POLICY",
        "BOSROUTE-AGT-TRUST",
        "BOSROUTE-AGT-SANDBOX",
        "BOSROUTE-AGT-SRE",
        "BOSROUTE-AGT-MCP-SECURITY",
        "BOSROUTE-AGT-MARKETPLACE",
        "BOSROUTE-AGT-LIGHTNING",
        "BOSROUTE-AGT-HYPERVISOR",
    }
    assert ids == expected, f"BOSRoute IDs mismatch: {ids}"


def test_agt_bosroutes_have_valid_uris() -> None:
    expected_uris = {
        "BOSROUTE-AGT-POLICY": "bos://governance/agt/policy",
        "BOSROUTE-AGT-TRUST": "bos://capability/agt/trust",
        "BOSROUTE-AGT-SANDBOX": "bos://capability/agt/sandbox",
        "BOSROUTE-AGT-SRE": "bos://capability/agt/sre",
        "BOSROUTE-AGT-MCP-SECURITY": "bos://capability/agt/mcp-security",
        "BOSROUTE-AGT-MARKETPLACE": "bos://capability/agt/marketplace",
        "BOSROUTE-AGT-LIGHTNING": "bos://capability/agt/lightning",
        "BOSROUTE-AGT-HYPERVISOR": "bos://governance/agt/hypervisor",
    }
    for stem, uri in expected_uris.items():
        path = BOSROUTE_DIR / f"{stem}.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["name"] == uri, f"{stem}: expected {uri}, got {data['name']}"
        assert data["subtype"] == "BOSRoute"
        assert data["properties"]["protocol"] == "BOS_URI"
        assert "cross_references" in data


def test_agt_bos_services_registered() -> None:
    data = yaml.safe_load(
        (ROOT / "projects/agora/etc/bos-services.yaml").read_text(encoding="utf-8")
    )
    services = data.get("services", [])
    agt_uris = {
        "bos://governance/agt/policy",
        "bos://capability/agt/trust",
        "bos://capability/agt/sandbox",
        "bos://capability/agt/sre",
        "bos://capability/agt/mcp-security",
        "bos://capability/agt/marketplace",
        "bos://capability/agt/lightning",
        "bos://governance/agt/hypervisor",
    }
    found_uris = {s["uri"] for s in services if "agt" in s.get("uri", "")}
    assert agt_uris == found_uris, f"Missing AGT BOS URIs: {agt_uris - found_uris}"


def test_agt_x3_trust_domain_registered() -> None:
    docs = list(yaml.safe_load_all(X3_VALUE_STACK.read_text(encoding="utf-8")))
    data = docs[1] if len(docs) > 1 else docs[0]
    assert "AGT" in data["domains"], "AGT domain not found in x3-value-stack.yaml"
    agt = data["domains"]["AGT"]
    assert agt["x3_value"]["implemented"] is True
    assert "trust_score" in agt["x3_value"]["dimensions"]


def test_agt_x1_audit_hashchain_policy_registered() -> None:
    docs = list(yaml.safe_load_all(X1_POLICIES.read_text(encoding="utf-8")))
    data = docs[1] if len(docs) > 1 else docs[0]
    policies = data["policies"]
    policy_ids = {p["policy_id"] for p in policies}
    assert "X1-AGT-AUDIT-HASHCHAIN-202608" in policy_ids


def test_agt_owasp_asi_constraints_registered() -> None:
    data = yaml.safe_load(L0_CONSTRAINTS.read_text(encoding="utf-8"))
    agt_constraints = data.get("agt_constraints", [])
    constraint_ids = {c["id"] for c in agt_constraints}
    for i in range(1, 11):
        cid = f"CR-AGT-ASI-{i:02d}"
        assert cid in constraint_ids, f"Missing constraint: {cid}"


def test_agt_integration_config_exists() -> None:
    assert INTEGRATION_CONFIG.exists()
    data = yaml.safe_load(INTEGRATION_CONFIG.read_text(encoding="utf-8"))
    assert data["status"] == "proposal_only"
    assert "AGT" in data.get("title", "")
    components = data.get("components", [])
    uris = {c["bos_uri"] for c in components}
    assert "bos://capability/agt/sandbox" in uris
    assert "bos://capability/agt/sre" in uris
    assert "bos://capability/agt/mcp-security" in uris
    ids = {c["id"] for c in components}
    assert "agt-sandbox" in ids
    assert "agt-sre" in ids
    assert "agt-mcp-security" in ids


def test_agt_backend_flag_in_gac_local_gate() -> None:
    script = (ROOT / "bin/gac/gac-local-gate.py").read_text(encoding="utf-8")
    assert "--agt-backend" in script
    assert "run_agt_policy_engine" in script
    assert "agt_backend" in script
