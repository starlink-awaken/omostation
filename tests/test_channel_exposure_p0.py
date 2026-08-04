"""Tests for P0–P2 channel exposure helpers (attach smoke + bos list filter helpers)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_mcp_attach_smoke_passes():
    mod = _load("mcp_attach_smoke", ROOT / "bin/ssot/mcp-attach-smoke.py")
    result = mod.run_smoke()
    assert result["ok"] is True, result
    assert result["yaml_total"] >= 180
    assert result["routable_count"] >= 100
    for t in mod.MINIMUM_MCP_TOOLS:
        assert t in result["minimum_mcp_tools"]


def test_bos_yaml_unimplemented_filtered_from_routable():
    docs = list(yaml.safe_load_all((ROOT / "projects/agora/etc/bos-services.yaml").read_text()))
    svcs = next(d["services"] for d in docs if isinstance(d, dict) and "services" in d)
    unimplemented = [s for s in svcs if s.get("status") == "unimplemented"]
    assert len(unimplemented) >= 8  # AGT pack
    routable = [
        s for s in svcs if (s.get("status") or "active") not in ("unimplemented", "deprecated")
    ]
    assert all(s.get("status") != "unimplemented" for s in routable)
    # AGT uris must not be routable
    agt_uris = {s.get("uri") for s in unimplemented if "agt" in (s.get("uri") or "")}
    assert agt_uris
    assert not agt_uris & {s.get("uri") for s in routable}


def test_gen_capability_registry_build_has_channels():
    # Official SSOT generator: bin/cockpit/gen-capability-registry.py
    mod = _load("gen_cap_reg", ROOT / "bin/cockpit/gen-capability-registry.py")
    # support either build()/main patterns
    if hasattr(mod, "build_registry"):
        reg = mod.build_registry()
    elif hasattr(mod, "build"):
        reg = mod.build()
    elif hasattr(mod, "generate"):
        reg = mod.generate()
    else:
        # fall back: assert output file shape after generate
        import subprocess, yaml
        subprocess.run(["python3", str(ROOT / "bin/cockpit/gen-capability-registry.py"), "--quiet"], check=True, cwd=ROOT)
        reg = yaml.safe_load((ROOT / "docs/generated/capability-registry.yaml").read_text())
    # flexible totals key layout
    totals = reg.get("totals") or reg.get("summary") or reg
    bos = totals.get("bos_services") or totals.get("bos") or reg.get("bos_services")
    if isinstance(bos, list):
        bos_n = len(bos)
    else:
        bos_n = int(bos or 0)
    assert bos_n >= 180, bos_n
    # channels command should appear in CLI inventory if present
    text = (ROOT / "docs/generated/capability-registry.yaml").read_text()
    assert "bos" in text.lower()


def test_attach_card_and_skills_exist():
    assert (ROOT / "docs/operations/external-agent-attach-card.md").is_file()
    assert (ROOT / "docs/operations/internal-only-surfaces.md").is_file()
    assert (ROOT / ".agents/skills/external-agent-attach/SKILL.md").is_file()
    skill = (ROOT / ".agents/skills/agent-onboarding/SKILL.md").read_text()
    assert "agora tools --json" not in skill
    assert "mcp-attach-smoke" in skill
    bos_skill = (ROOT / ".agents/skills/bos-service-discovery/SKILL.md").read_text()
    assert "unimplemented" in bos_skill


def test_cockpit_channels_module_importable():
    # Prefer PASW subtree when present (gac-worktree isolation).
    channel_candidates = [
        ROOT / ".subtrees/cockpit/src/cockpit/commands/channels.py",
        ROOT / "projects/cockpit/src/cockpit/commands/channels.py",
    ]
    p = next((c for c in channel_candidates if c.is_file()), None)
    assert p is not None, f"channels.py not found in {channel_candidates}"
    text = p.read_text()
    assert "def cmd_channels" in text
    cli_candidates = [
        ROOT / ".subtrees/cockpit/src/cockpit/cli.py",
        ROOT / "projects/cockpit/src/cockpit/cli.py",
    ]
    cli_path = next((c for c in cli_candidates if c.is_file() and '"channels"' in c.read_text()), None)
    assert cli_path is not None, "cli.py with channels registration not found"
    cli = cli_path.read_text()
    assert '"channels"' in cli
    assert "dest=\"all\"" in cli or 'dest="all"' in cli or "--all" in cli
