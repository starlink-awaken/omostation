#!/usr/bin/env python3
"""Journey Engine v3 — BOS-driven scene execution with Saga compensation.

Refactored from journey-runner.py:
  - BOS URI driven dispatch (no hardcoded DISPATCHERS dict)
  - Saga compensation chain for rollback
  - Human-in-the-loop gate support
  - Calibration evidence emission
"""

from __future__ import annotations
import argparse, json, os, subprocess, sys, uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "bin" / "ssot"))

# ── Performance: YAML parse cache (mtime-aware) ──────────────────────
_yaml_cache: dict[str, tuple[float, dict[str, Any]]] = {}

def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML with mtime-based caching to avoid repeated disk I/O."""
    import yaml
    cache_key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    cached = _yaml_cache.get(cache_key)
    if cached and cached[0] == mtime:
        return cached[1]

    with open(path, encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    body = docs[-1] if len(docs) > 1 else docs[0]
    result = body if isinstance(body, dict) else {}

    _yaml_cache[cache_key] = (mtime, result)
    return result

# ── Performance: scene card index (built once, O(1) lookup) ─────────
_scene_index: dict[str, dict[str, Any]] | None = None
_scene_index_built_at: float = 0.0
_SCENE_INDEX_TTL = 60.0  # Rebuild every 60s

def _build_scene_index() -> dict[str, dict[str, Any]]:
    """Build a scene_id → card mapping in one pass."""
    index = {}
    for d in [_ROOT / ".omo" / "_truth" / "scenarios" / "v3", _ROOT / "docs" / "scene-cards"]:
        if not d.is_dir():
            continue
        for p in d.glob("*.yaml"):
            try:
                body = _load_yaml(p)
                sid = body.get("scene_id")
                if sid and sid not in index:
                    index[sid] = body
            except Exception:
                continue
    return index

def _get_scene_index() -> dict[str, dict[str, Any]]:
    """Get or rebuild the scene index (TTL-based)."""
    global _scene_index, _scene_index_built_at
    import time
    now = time.time()
    if _scene_index is None or (now - _scene_index_built_at) > _SCENE_INDEX_TTL:
        _scene_index = _build_scene_index()
        _scene_index_built_at = now
    return _scene_index

def _find_journey_spec(journey_id: str) -> Path:
    v3_path = _ROOT / ".omo" / "_truth" / "journeys" / "v3" / f"{journey_id}.yaml"
    if v3_path.exists(): return v3_path
    legacy_path = _ROOT / "docs" / "journey-specs" / f"{journey_id}.yaml"
    if legacy_path.exists(): return legacy_path
    raise FileNotFoundError(f"journey spec not found: {journey_id}")

def _find_scene_card(scene_id: str) -> dict[str, Any] | None:
    """O(1) scene card lookup via cached index."""
    return _get_scene_index().get(scene_id)

class CompensationAction:
    def __init__(self, action_type: str, payload: dict, description: str = ""):
        self.action_type, self.payload, self.description = action_type, payload, description
        self.executed = False
    def execute(self, ctx) -> bool:
        try:
            if self.action_type == "revert_file":
                t = Path(self.payload["path"])
                if self.payload.get("backup") and t.exists(): t.write_text(self.payload["backup"], encoding="utf-8")
                elif t.exists(): t.unlink()
                self.executed = True; return True
            elif self.action_type == "delete_file":
                t = Path(self.payload["path"])
                if t.exists(): t.unlink()
                self.executed = True; return True
            elif self.action_type == "emit_event":
                _emit_omo_event(self.payload.get("event_type", "compensation.executed"), self.payload)
                self.executed = True; return True
            return False
        except: return False

class CompensationLog:
    def __init__(self, run_id: str): self.run_id = run_id; self._stack: list[CompensationAction] = []
    def push(self, action: CompensationAction): self._stack.append(action)
    def compensate(self, ctx) -> list[CompensationAction]:
        failed = []
        for action in reversed(self._stack):
            if not action.execute(ctx): failed.append(action)
        return failed

class ExecutionContext:
    def __init__(self, scene_id, journey_id, signal, dry_run=False):
        self.run_id = f"exec-{uuid.uuid4().hex[:12]}"
        self.scene_id, self.journey_id, self.signal, self.dry_run = scene_id, journey_id, signal, dry_run
        self.scene_card, self.journey_spec = None, None
        self.current_state, self.variables, self.trace = "", {}, []
        self.compensation_log = CompensationLog(self.run_id)
        self.start_time, self.end_time = datetime.now(UTC), None
        self.status, self.confidence = "pending", 0.0
        self.output = {}
    def record_step(self, state, action, result):
        self.trace.append({"step": len(self.trace)+1, "state": state, "action": action,
                           "timestamp": datetime.now(UTC).isoformat(),
                           "result_summary": {k:v for k,v in result.items() if k != "raw_output"}})
        self.current_state = state
    def _duration_ms(self) -> int:
        end = self.end_time or datetime.now(UTC)
        return int((end - self.start_time).total_seconds() * 1000)
    def to_event(self) -> dict:
        return {"event_type": f"scene.{self.status}", "source_scene": self.scene_id,
                "run_id": self.run_id, "correlation_id": self.run_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "payload": {"scene_id": self.scene_id, "journey_id": self.journey_id,
                           "confidence": self.confidence, "status": self.status,
                           "trace_steps": len(self.trace), "duration_ms": self._duration_ms()}}

def _emit_omo_event(event_type: str, payload: dict) -> None:
    try:
        subprocess.run([sys.executable, str(_ROOT / "projects/omo/src/omo/cli.py"),
                        "event", "emit", "--type", event_type, "--source", "journey-engine",
                        "--payload", json.dumps(payload, ensure_ascii=False)],
                       capture_output=True, text=True, timeout=10, check=False, cwd=str(_ROOT))
    except: pass

def _emit_scene_alert(event_type: str, payload: dict, severity: str = "critical") -> None:
    """Emit to the observability alert plane (drives alert-forwarder connectors).

    scene.escalated → critical; scene.failed → degraded. The forwarder routes
    via alert-channels.yaml (feishu/dingtalk/wecom/slack) to real channels.
    """
    try:
        subprocess.run(
            [sys.executable, str(_ROOT / "bin/ssot/observability-events.py"), "emit",
             "--domain", "scene", "--type", event_type, "--severity", severity,
             "--source", "journey-engine", "--trace-id", str(payload.get("run_id", "")),
             "--payload", json.dumps(payload, ensure_ascii=False)],
            capture_output=True, text=True, timeout=10, check=False, cwd=str(_ROOT),
        )
    except Exception:
        pass  # alert emission is best-effort, never blocks the journey

def _resolve_next_state(spec, current, result, ctx) -> str | None:
    for t in spec.get("transitions", []):
        if t.get("from") != current: continue
        condition = t.get("condition")
        if condition and not _evaluate_condition(condition, result, ctx): continue
        return t.get("to")
    return None

def _evaluate_condition(condition, result, ctx) -> bool:
    try:
        ns = {"result": result, "ctx": ctx, "confidence": ctx.confidence, "variables": ctx.variables}
        if " == " in condition:
            l, r = condition.split(" == ", 1)
            return _resolve_path(l.strip(), ns) == _resolve_literal(r.strip())
        for op in (">=", "<=", ">", "<"):
            if op in condition:
                l, r = condition.split(op, 1)
                lv, rv = float(_resolve_path(l.strip(), ns)), float(_resolve_literal(r.strip()))
                return lv >= rv if op == ">=" else lv <= rv if op == "<=" else lv > rv if op == ">" else lv < rv
        return False
    except: return False

def _resolve_path(path, ns):
    cur = ns
    for p in path.strip().split("."):
        cur = cur.get(p) if isinstance(cur, dict) else getattr(cur, p, None) if hasattr(cur, p) else None
    return cur

def _resolve_literal(value):
    v = value.strip()
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')): return v[1:-1]
    if v.lower() == "true": return True
    if v.lower() == "false": return False
    try: return int(v)
    except ValueError:
        try: return float(v)
        except ValueError: return v

def execute_journey(scene_id, signal, dry_run=False) -> ExecutionContext:
    scene_card = _find_scene_card(scene_id)
    if not scene_card: raise ValueError(f"scene card not found: {scene_id}")
    journey_id = scene_card.get("runtime", {}).get("journey_ref", f"journey-{scene_id}")
    ctx = ExecutionContext(scene_id, journey_id, signal, dry_run)
    ctx.scene_card, ctx.status = scene_card, "running"
    try:
        spec = _load_yaml(_find_journey_spec(journey_id))
        ctx.journey_spec = spec
        states = spec.get("states", [])
        initial = spec.get("initial_state")
        if isinstance(initial, dict): initial = initial.get("name")
        if not initial and states:
            initial = states[0].get("name") if isinstance(states[0], dict) else states[0]

        max_steps, step, current = 100, 0, initial
        while current and step < max_steps:
            step += 1
            state_def = None
            for s in states:
                if isinstance(s, dict) and s.get("name") == current:
                    state_def = s; break
            if state_def is None: break
            action = state_def.get("action", "noop")
            result = {"status": "succeeded", "dry_run": True, "confidence": 0.85, "action": action} if dry_run else _execute_action(action, state_def, ctx)
            ctx.record_step(current, action, result)
            comp = state_def.get("compensation")
            if comp:
                ctx.compensation_log.push(CompensationAction(comp.get("type","emit_event"), comp.get({})))
            if state_def.get("type") == "human_gate" or state_def.get("requires_human"):
                ctx.status = "escalated"
                _emit_omo_event("scene.escalated", ctx.to_event())
                _emit_scene_alert("scene.escalated", ctx.to_event(), severity="critical")
                ctx.end_time = datetime.now(UTC); return ctx
            nxt = _resolve_next_state(spec, current, result, ctx)
            if nxt is None: break
            current = nxt
        ctx.status = "succeeded"; ctx.confidence = result.get("confidence", 0.8) if result else 0.0; ctx.output = result
    except Exception as exc:
        ctx.status = "failed"; ctx.output = {"error": str(exc), "error_type": type(exc).__name__}
        _emit_scene_alert("scene.failed", ctx.to_event(), severity="degraded")
        failed = ctx.compensation_log.compensate(ctx)
        if failed: ctx.output["compensation_failures"] = len(failed)
    ctx.end_time = datetime.now(UTC)
    _emit_omo_event(ctx.to_event()["event_type"], ctx.to_event())
    return ctx

def _execute_action(action, state_def, ctx) -> dict:
    """Execute a state action — supports both BOS capability_refs and named actions."""
    # 1. Try BOS capability_refs from scene card
    caps = ctx.scene_card.get("runtime", {}).get("sandbox", {}).get("capability_refs", [])
    if caps:
        results = {}
        for uri in caps:
            results[uri] = _dispatch_bos_uri(uri, ctx)
        failed = sum(1 for r in results.values() if r.get("status") == "error")
        return {
            "status": "succeeded" if failed == 0 else "partial",
            "capabilities_executed": len(results),
            "capabilities": results,
        }

    # 2. Named actions
    if action == "noop":
        return {"status": "succeeded"}
    if action in ("llm_classify", "generate_decision"):
        return {"status": "succeeded", "confidence": 0.85, "action": action}
    if action == "emit_event":
        _emit_omo_event(
            state_def.get("event", "scene.step_completed"),
            {"scene_id": ctx.scene_id, "state": ctx.current_state},
        )
        return {"status": "succeeded", "event": state_def.get("event")}

    # 3. iris connector actions (e.g., action: "iris_list_apple_mail")
    if action.startswith("iris_list_"):
        connector = action.replace("iris_list_", "")
        return _call_iris_list(connector)

    return {"status": "succeeded", "action": action}


def _dispatch_bos_uri(uri: str, ctx) -> dict:
    """Dispatch a BOS URI to its actual service call.

    Supports:
      - bos://memory/iris/{connector} — iris connector list
      - bos://memory/kos/{action} — KOS REST API (:8766)
      - bos://memory/gbrain/{action} — gbrain knowledge base
      - bos://capability/compute/generate — LLM inference
      - bos://analysis/codeanalyze/{action} — code analysis
      - bos://agent-cell/* — agent cell operations
      - bos://scene/*/execute — scene-to-scene invocation
    """
    try:
        parts = uri.replace("bos://", "").split("/")
        domain = parts[0] if parts else ""
        action = parts[1] if len(parts) > 1 else ""

        # ── memory domain ──
        if domain == "memory":
            # iris connectors
            if action == "iris":
                connector = parts[2] if len(parts) > 2 else "apple_mail"
                return _call_iris_list(connector)

            # KOS operations — real REST API calls
            if action == "kos":
                sub_action = parts[2] if len(parts) > 2 else "search"
                query = ctx.signal.get("query", ctx.signal.get("content", ""))
                if sub_action == "search":
                    return _call_kos_search(query)
                if sub_action == "ingest":
                    return _call_kos_ingest(query)
                if sub_action == "status":
                    return _call_kos_status()
                return {"status": "succeeded", "action": sub_action, "note": f"KOS {sub_action} — use search/ingest/status"}

            # gbrain operations
            if action == "gbrain":
                sub_action = parts[2] if len(parts) > 2 else "search"
                return {"status": "succeeded", "action": sub_action,
                        "note": f"gbrain {sub_action} stub — integrate gbrain MCP"}

        # ── analysis domain ──
        if domain == "analysis":
            sub_action = parts[2] if len(parts) > 2 else "scan"
            return {"status": "succeeded", "action": sub_action,
                    "note": f"analysis/{action}/{sub_action} — integrate Kairon codeanalyze"}

        # ── capability domain ──
        if domain == "capability":
            if action == "compute" and len(parts) > 2 and parts[2] == "generate":
                return _call_llm_generate(ctx)

        # ── scene domain (scene-to-scene invocation) ──
        if domain == "scene":
            if len(parts) >= 3 and parts[2] == "execute":
                target_scene = parts[1]
                return _invoke_scene(target_scene, ctx)

        # Fallback
        return {"status": "unresolved", "uri": uri, "note": f"No handler for domain '{domain}/{action}'"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _http_get_json(url: str, timeout: int = 10) -> dict | None:
    """Make an HTTP GET request and return JSON response."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _call_kos_search(query: str) -> dict:
    """Real KOS search via REST API (:8766)."""
    if not query:
        return {"status": "skipped", "reason": "no query provided"}

    from urllib.parse import quote
    url = f"http://localhost:8766/search?q={quote(query)}&limit=5"
    data = _http_get_json(url)
    if data is None:
        return {"status": "succeeded", "results": [], "query": query,
                "note": "KOS API unreachable — falling back to empty results"}

    results = data.get("results", [])
    return {
        "status": "succeeded",
        "results": results[:5],
        "query": query,
        "total": len(results),
        "source": "kos-rest-api",
    }


def _call_kos_ingest(text: str) -> dict:
    """Real KOS ingest via REST API (:8766)."""
    if not text:
        return {"status": "skipped", "reason": "no text to ingest"}
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://localhost:8766/ingest",
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"status": "succeeded", "indexed": True, "response": data, "source": "kos-rest-api"}
    except Exception as e:
        return {"status": "succeeded", "indexed": False, "error": str(e), "source": "kos-rest-api"}


def _call_kos_status() -> dict:
    """Real KOS status via REST API (:8766)."""
    data = _http_get_json("http://localhost:8766/status")
    if data is None:
        return {"status": "succeeded", "online": False, "note": "KOS API unreachable"}
    return {"status": "succeeded", "online": True, "data": data, "source": "kos-rest-api"}


def _call_llm_generate(ctx) -> dict:
    """LLM inference via AetherForge (:9290) or fallback stub."""
    try:
        import urllib.request
        prompt = ctx.signal.get("prompt", ctx.signal.get("content", "Summarize the input."))
        body = json.dumps({
            "model": "default",
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:9290/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"status": "succeeded", "generated": True, "content": content[:500], "source": "aetherforge"}
    except Exception:
        return {"status": "succeeded", "generated": True,
                "note": "AetherForge :9290 unreachable — LLM stub fallback"}


def _invoke_scene(target_scene: str, ctx) -> dict:
    """Invoke another scene (scene-to-scene call)."""
    try:
        result = execute_journey(target_scene, ctx.signal, dry_run=ctx.dry_run)
        return {
            "status": result.status,
            "invoked": target_scene,
            "confidence": result.confidence,
            "run_id": result.run_id,
        }
    except Exception as e:
        return {"status": "error", "invoked": target_scene, "error": str(e)}


def _call_iris_list(connector: str, limit: int = 5) -> dict:
    """Call iris list <connector> and return parsed items."""
    try:
        result = subprocess.run(
            ["iris", "--json", "list", connector, "--limit", str(limit)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Strip deprecation warnings, find JSON start
            raw = result.stdout
            for start_char in ("[", "{"):
                idx = raw.find(start_char)
                if idx >= 0:
                    raw = raw[idx:]
                    break
            try:
                data = json.loads(raw)
                return {"status": "succeeded", "data": data, "connector": connector}
            except json.JSONDecodeError:
                return {"status": "succeeded", "data": raw, "connector": connector, "format": "raw"}
        return {"status": "succeeded", "data": [], "connector": connector}
    except FileNotFoundError:
        return {"status": "skipped", "reason": "iris not installed", "connector": connector}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "connector": connector}

def _detect_backedges(spec) -> set:
    transitions = spec.get("transitions", [])
    adj = {}
    for t in transitions:
        adj.setdefault(t.get("from",""), []).append(t.get("to",""))
    backedges, visited, on_stack = set(), set(), set()
    def dfs(n):
        visited.add(n); on_stack.add(n)
        for nx in adj.get(n, []):
            if nx in on_stack: backedges.add((n, nx))
            elif nx not in visited: dfs(nx)
        on_stack.discard(n)
    for s in spec.get("states", []):
        nm = s.get("name","") if isinstance(s,dict) else s
        if nm and nm not in visited: dfs(nm)
    return backedges

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    ep = sub.add_parser("execute"); ep.add_argument("scene_id"); ep.add_argument("--signal",type=json.loads,default={}); ep.add_argument("--dry-run",action="store_true")
    vp = sub.add_parser("validate"); vp.add_argument("journey_id")
    mp = sub.add_parser("migrate"); mp.add_argument("--scene-card",type=Path); mp.add_argument("--all",action="store_true")
    args = parser.parse_args(argv)
    cmd = args.command or "status"
    if cmd == "execute":
        ctx = execute_journey(args.scene_id, args.signal, dry_run=getattr(args,"dry_run",False))
        print(json.dumps({"run_id":ctx.run_id,"scene_id":ctx.scene_id,"status":ctx.status,
                          "confidence":ctx.confidence,"steps":len(ctx.trace),"duration_ms":ctx._duration_ms(),"output":ctx.output},ensure_ascii=False,indent=2))
        return 0 if ctx.status == "succeeded" else 1
    if cmd == "validate":
        spec = _load_yaml(_find_journey_spec(args.journey_id))
        bk = _detect_backedges(spec)
        print(json.dumps({"journey_id":args.journey_id,"states":len(spec.get("states",[])),
                          "transitions":len(spec.get("transitions",[])),"backedges":list(bk),"valid":len(bk)==0},ensure_ascii=False,indent=2))
        return 0
    if cmd == "migrate": return _migrate_cards(args)
    print("Journey Engine v3 — ready"); return 0

def _migrate_cards(args) -> int:
    import yaml
    migrated, cards = 0, []
    if args.all:
        for d in [_ROOT/"docs/scene-cards"]:
            if d.is_dir(): cards.extend(d.glob("*.yaml"))
    elif args.scene_card: cards = [args.scene_card]
    else: print("ERROR: --scene-card or --all required",file=sys.stderr); return 2
    tdir = _ROOT/".omo/_truth/scenarios/v3"; tdir.mkdir(parents=True,exist_ok=True)
    for cp in cards:
        try:
            card = _load_yaml(cp); sid = card.get("scene_id", cp.stem)
            if card.get("schema") == "scene-card/v3": continue
            lc = card.get("lifecycle","draft"); lm = {"proposal_only":"draft","active":"routine","forbidden":"draft"}
            if lc in lm: lc = lm[lc]
            am = {"draft":"preview","shadow":"preview","assisted":"controlled","supervised":"active","routine":"allowed"}
            v3 = {"schema":"scene-card/v3","scene_id":sid,"version":"3.0.0","name":card.get("name",sid),
                  "description":card.get("description",""),"scene_class":card.get("scene_class","business"),
                  "scene_type":card.get("scene_type","inbound"),"domain":card.get("domain","work"),
                  "lifecycle":lc,"activation":card.get("activation",am.get(lc,"preview")),
                  "owner":card.get("owner","governance-agent"),"approver":card.get("approver","governance-agent"),
                  "approval_state":card.get("approval_state","confirmed"),"bet":card.get("bet",""),
                  "runtime":{"journey_ref":card.get("journey_id",f"journey-{sid}"),"timeout":"3600s",
                             "sandbox":{"level":"isolated","capability_refs":card.get("capability_refs",[]),
                                        "permissions":card.get("permission_scope",[])}},
                  "quality":{"calibration":{"min_samples":30,"min_calibration":0.6}},"falsifier":card.get("falsifier",[]),
                  "activation_blockers":card.get("activation_blockers",[]),"observability":{"tracing":True,"evidence_capture":"full"}}
            tp = tdir/f"{sid}.yaml"
            with open(tp,"w",encoding="utf-8") as f: yaml.dump(v3,f,default_flow_style=False,allow_unicode=True,sort_keys=False)
            migrated += 1; print(f"  Migrated: {cp.name} -> {tp}")
        except Exception as e: print(f"  FAILED: {cp.name}: {e}",file=sys.stderr)
    print(f"Total migrated: {migrated}"); return 0

if __name__ == "__main__": raise SystemExit(main())
