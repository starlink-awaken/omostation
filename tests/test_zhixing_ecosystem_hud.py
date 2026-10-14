"""Execute the complete managed HUD with fake fetch; never contact a live service."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "bin/panorama/assets/host/ecosystem_ui.js.asset"

# The real script runs in a small DOM harness. UI functions, async chains and
# request bodies are exercised, rather than reimplementing their predicates.
NODE_HARNESS = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8');
const scenario = JSON.parse(process.argv[2]);
const nodes = new Map(), alerts = [], requests = [], streams = [];
function element(id) {
  const classes = new Set();
  return {id, innerHTML:'', textContent:'', className:'', style:{display:'none'},
    childNodes:[], classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),
      toggle:x=>classes.has(x)?classes.delete(x):classes.add(x),contains:x=>classes.has(x)},
    appendChild(x){this.childNodes.push(x);}, removeChild(){this.childNodes.shift();},
    querySelector(){return null;},querySelectorAll(){return [];},
    setAttribute(){},addEventListener(){}};
}
for (const id of ['persona-guidance-bar','sovereign-cockpit-drawer-modal',
  'sovereign-cockpit-drawer-content','sovereign-adjudication-toast',
  'card-prop-p1','stamp-p1','action-bar-p1','kpi-net-saved','kpi-adjudications',
  'telemetry-terminal-logs']) nodes.set(id,element(id));
nodes.get('kpi-net-saved').textContent='未记录';
nodes.get('kpi-adjudications').textContent='未记录';
const document = {getElementById:id=>nodes.get(id)||null,
  querySelectorAll:selector=>selector.startsWith('#')&&nodes.has(selector.slice(1))?[nodes.get(selector.slice(1))]:[],
  querySelector(){return null;},createElement:()=>element(''),addEventListener(){},
  body:element('body')};
let listQueue = [], post = null;
function response(spec) {
  if (spec.network) return Promise.reject(new Error('network failure'));
  if (spec.deferred) return spec.deferred;
  return Promise.resolve({ok:(spec.status||200)>=200&&(spec.status||200)<300,
    status:spec.status||200,json:()=>spec.invalidJSON?Promise.reject(new Error('invalid JSON')):Promise.resolve(spec.body)});
}
const context = {document, console:{warn(){},log(){},error:console.error}, URLSearchParams, Date, Set,
  addEventListener(){},
  location:{search:'',hash:''}, localStorage:{getItem(){return null;},setItem(){}},
  alert:x=>alerts.push(x),setTimeout(){},clearTimeout(){},
  EventSource:class {constructor(url){this.url=url;this.listeners={};streams.push(this);}
    addEventListener(name,fn){this.listeners[name]=fn;}},
  fetch:(url,options)=>{
    requests.push({url,options});
    if(url.includes('/proposals/list')) return response(listQueue.shift()||{network:true});
    if(url.includes('/proposals/adjudicate')) return response(post);
    return response({body:{data:{summary:{}}}});
  }};
context.window=context;vm.createContext(context);vm.runInContext(source,context);
const settle=async()=>{for(let i=0;i<12;i++) await Promise.resolve();};
const bar=()=>nodes.get('persona-guidance-bar').innerHTML;
const drawer=()=>nodes.get('sovereign-cockpit-drawer-content').innerHTML;
const pending={id:'p1',title:'proposal',status:'pending',agent_id:'fixture',proposal_type:'general'};
const empty={data:{proposals:[],summary:{pending_count:0}},schema_version:'observer-query/v1',
  state:'PARTIAL',read_only:true,role_is_authority:false,instruction_capable:false,
  generated_at:new Date().toISOString(),freshness:{state:'FRESH',ttl_seconds:600}};
async function read(spec) {listQueue.push(spec);context.initPersonaSystem();await settle();}
function unavailable() {
  assert.match(bar(),/读取不可用/);assert.match(drawer(),/读取不可用/);
  assert(!bar().includes('无待决提案'));assert(!drawer().includes('无待决提案'));
  assert(!drawer().includes('proposal'));
}
(async()=>{
  if(scenario.mode==='read'){
    listQueue.push(scenario.response);context.initPersonaSystem();
    assert.match(bar(),/读取中/);context.openSovereignCockpitDrawer();assert.match(drawer(),/读取中/);
    await settle();
    if(scenario.expected==='error') unavailable();
    else {assert.match(bar(),scenario.expected==='empty'?/无待决提案/:/1 项待决/);
      assert.match(drawer(),scenario.expected==='empty'?/无待决提案/:/1 项待决/);}
  } else if(scenario.mode==='sequence') {
    context.openSovereignCockpitDrawer();
    await read({network:true});unavailable();
    await read({body:empty});assert.match(bar(),/无待决提案/);assert.match(drawer(),/来源时间/);
    await read({body:{data:{proposals:[pending]}}});assert.match(bar(),/1 项待决/);assert.match(drawer(),/proposal/);
    context.togglePinSovereignInPage();assert.match(bar(),/1 项待决/);
    context.openSovereignCockpitDrawer();await read({status:503,body:{error:'unavailable'}});unavailable();
    await read({body:empty});assert.match(drawer(),/无待决提案/);
  } else if(scenario.mode==='race') {
    let resolve;listQueue.push({deferred:new Promise(r=>resolve=r)});context.initPersonaSystem();
    await read({body:{data:{proposals:[pending]}}});assert.match(bar(),/1 项待决/);
    resolve({ok:true,status:200,json:async()=>empty});await settle();assert.match(bar(),/1 项待决/);
  } else if(scenario.mode==='text') {
    await read({body:{data:{proposals:[{...pending,title:'<img src=x onerror=alert(1)>',
      description:'<script>bad()</script>',agent_id:'<svg onload=bad()>',proposal_type:'<b>type</b>',
      payload:{remediation_cmd:'<iframe>',diff_summary:'</pre><script>bad()</script>'}}]}}});
    context.openSovereignCockpitDrawer();assert(drawer().includes('&lt;img'));
    for(const tag of ['<img','<script','<svg','<iframe']) assert(!drawer().includes(tag));
  } else if(scenario.mode==='post') {
    await read({body:{data:{proposals:[pending]}}});post=scenario.response;
    listQueue.push({body:empty});await context.quickAdjudicate('p1','approved');await settle();
    const req=requests.find(r=>r.options?.method==='POST');assert(req);
    assert.equal(req.url,'/api/v1/proposals/adjudicate');
    assert.deepEqual(Object.keys(JSON.parse(req.options.body)).sort(),['adjudicator','id','reviewer_note','verdict']);
    if(scenario.success){assert.match(nodes.get('stamp-p1').textContent,/后端记录/);assert.equal(alerts.length,0);}
    else {assert.equal(nodes.get('stamp-p1').textContent,'');assert.equal(alerts.length,1);
      assert(!nodes.get('card-prop-p1').classList.contains('adjudicated'));assert.match(bar(),/1 项待决/);}
    assert.equal(nodes.get('kpi-net-saved').textContent,'未记录');
    assert.equal(nodes.get('kpi-adjudications').textContent,'未记录');
    assert(!nodes.get('action-bar-p1').textContent.includes('夏明星签署生效'));
  } else if(scenario.mode==='sse') {
    context.initLiveTelemetryStream();const s=streams[0];s.onopen();
    s.listeners.connected({data:JSON.stringify({vram_usage:'43.2GB/152GB'})});
    s.listeners.pulse({data:JSON.stringify({cycle:1,timestamp:new Date().toISOString()})});
    const messages=nodes.get('telemetry-terminal-logs').childNodes.map(n=>n.innerHTML).join('');
    assert.match(messages,/回路健康未记录/);assert(!messages.includes('4/4'));
    assert(!messages.includes('43.2GB'));
  }
  assert(!bar().includes('全域绿灯'));assert(!drawer().includes('100% 合规'));
  process.stdout.write('PASS '+scenario.mode);
})().catch(e=>{console.error(e);process.exitCode=1;});
"""


def run_js(scenario):
    node = shutil.which("node")
    assert node, "Node.js is required to verify actual HUD behavior"
    result = subprocess.run([node, "-e", NODE_HARNESS, str(ASSET), json.dumps(scenario)],
                            text=True, capture_output=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("PASS"), result.stdout


@pytest.mark.parametrize("response", [
    {"network": True}, {"status": 405, "body": {"error": "read_only_get_only"}},
    {"status": 503, "body": {"data": {"proposals": []}}}, {"invalidJSON": True},
    {"body": {"_stub": True, "status": "ok", "data": []}},
    {"body": {"_stub": True, "data": {"proposals": []}}},
    {"body": {"data": {"proposals": []}, "ok": False}},
    {"body": {"data": {"proposals": [], "status": "failed"}}},
    {"body": {"data": {"proposals": {}}}}, {"body": {"status": "ok"}},
    {"body": {"data": {"proposals": [None]}}},
    {"body": {"data": {"proposals": [{"id": "p1", "title": "x", "status": "unknown"}]}}},
    {"body": {"data": {"proposals": [{"id": "x');bad()//", "title": "x", "status": "pending"}]}}},
    {"body": {"data": {"proposals": []}, "generated_at": "2000-01-01T00:00:00Z",
              "freshness": {"state": "FRESH", "ttl_seconds": 600}}},
    {"body": {"data": {"proposals": []}, "freshness": {"state": "STALE"}}},
])
def test_unusable_reads_never_claim_zero(response):
    run_js({"mode": "read", "response": response, "expected": "error"})


@pytest.mark.parametrize("proposals,expected", [([], "empty"), ([
    {"id": "p1", "title": "proposal", "status": "pending"}], "pending")])
def test_valid_queue_scope_only(proposals, expected):
    run_js({"mode": "read", "response": {"body": {"data": {"proposals": proposals}}},
            "expected": expected})


@pytest.mark.parametrize("mode", ["sequence", "race", "text", "sse"])
def test_actual_hud_transitions_text_and_transport(mode):
    run_js({"mode": mode})


@pytest.mark.parametrize("response", [
    {"network": True}, {"invalidJSON": True},
    {"status": 405, "body": {"error": "read_only_get_only"}},
    {"status": 500, "body": {"status": "ok"}},
    {"body": {"_stub": True, "status": "ok", "data": []}},
    {"body": {"status": "ok"}}, {"body": {"data": {"ok": False}}},
    {"body": {"data": {"id": "other", "status": "approved"}}},
    {"body": {"data": {"id": "p1", "status": "approved"}}},
    {"body": {"ok": False, "data": {"id": "p1", "status": "approved",
        "adjudicated_at": "2026-10-14T00:00:00Z", "audit_digest": "sha256:" + "a" * 64}}},
    {"body": {"data": {"success": False, "id": "p1", "status": "approved",
        "adjudicated_at": "2026-10-14T00:00:00Z", "audit_digest": "sha256:" + "a" * 64}}},
])
def test_post_failure_never_signs_or_invents_value(response):
    run_js({"mode": "post", "response": response, "success": False})


def test_matching_audited_backend_record_is_not_human_signature():
    run_js({"mode": "post", "success": True, "response": {"body": {"data": {
        "id": "p1", "status": "approved", "adjudicated_at": "2026-10-14T00:00:00Z",
        "audit_digest": "sha256:" + "a" * 64}}}})


def test_removed_static_truth_and_preserved_public_controls():
    source = ASSET.read_text()
    for unsupported in ["377 BET", "91.7%", "15.8h", "152 个 PR", "336 次漂移",
                        "43.2", "152GB", "16模型", "16 模型", "PASW 隔离生效中",
                        "全域绿灯", "4/4 绿色", "curVal + 45.0", "nextAdj"]:
        assert unsupported not in source
    for control in ["initPersonaSystem", "switchPersona", "openSovereignCockpitDrawer",
                    "closeSovereignCockpitDrawer", "togglePinSovereignInPage",
                    "selectAgentRole", "quickAdjudicate", "initLiveTelemetryStream"]:
        assert "window." + control + " = function" in source
    assert 'href="#personal"' in source


def test_native_mapping_and_selected_publication_preserve_other_payloads(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("hud_host_sync", ROOT / "bin/gac/zhixing-host-sync.py")
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    assets = sync._selected_assets(["ecosystem_ui.js"])
    assert assets == (("ecosystem_ui.js", "ecosystem_ui.js.asset"),)
    assert len([pair for pair in sync.HOST_FILES if pair[0] == "ecosystem_ui.js"]) == 1
    host, releases = tmp_path / "source", tmp_path / "releases"
    host.mkdir(); releases.mkdir()
    (host / "ecosystem_ui.js.asset").write_bytes(ASSET.read_bytes())
    monkeypatch.setattr(sync, "HOST_DIR", host)
    monkeypatch.setattr(sync, "RELEASES_DIR", releases)
    monkeypatch.setattr(sync, "CURRENT_LINK", tmp_path / "current")
    baseline_source = tmp_path / "baseline"
    baseline_source.mkdir()
    (baseline_source / "ecosystem_ui.js.asset").write_text("// prior retained HUD fixture\n")
    (baseline_source / "untouched.py.asset").write_text("unchanged baseline\n")

    def commit_identity(directory):
        subprocess.run(["git", "init", "-q", str(directory)], check=True)
        subprocess.run(["git", "-C", str(directory), "add", "."], check=True)
        subprocess.run(["git", "-C", str(directory), "-c", "user.name=fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
        return subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True).strip()

    old = commit_identity(baseline_source)
    new = commit_identity(host)
    assert old != new
    baseline = sync._prepare_version(assets + (("untouched.py", "untouched.py.asset"),),
                                     old, source_dir=baseline_source)
    assert baseline["ok"], baseline
    old_dir = releases / old
    assert sync._switch_current(old_dir)["ok"]
    before = {p.name: p.read_bytes() for p in old_dir.iterdir()}
    result = sync._prepare_version(assets, new)
    assert result["ok"], result
    version = releases / new
    assert (version / "ecosystem_ui.js").read_bytes() == ASSET.read_bytes()
    assert (version / "ecosystem_ui.js").read_bytes() != before["ecosystem_ui.js"]
    assert (version / "untouched.py").read_bytes() == before["untouched.py"]
    manifest = json.loads((version / sync.RELEASE_MANIFEST).read_text())
    assert manifest["selected_assets"] == ["ecosystem_ui.js"]
    assert result["manifest"][0]["sha"] == hashlib.sha256(ASSET.read_bytes()).hexdigest()[:16]
    assert manifest["files"]["ecosystem_ui.js"] == hashlib.sha256(ASSET.read_bytes()).hexdigest()
    assert {p.name: p.read_bytes() for p in old_dir.iterdir()} == before
    assert sync.CURRENT_LINK.resolve() == old_dir
