"""Execute the governed personal-page asset without network or production actions."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ASSET = Path(__file__).resolve().parents[1] / "bin/panorama/assets/host/workbench_ui.js.asset"
NODE = r"""
const fs = require('fs'), vm = require('vm');
const scenario = JSON.parse(process.argv[2]), nodes = new Map();
function element(id='') {
  const el = {id, innerHTML:'', textContent:'', style:{}, dataset:{}, value:'',
    classList:{add(){},remove(){},toggle(){},contains(){return false;}},
    addEventListener(){}, setAttribute(){}, getAttribute(){return null;},
    querySelectorAll(){return [];}, querySelector(){return null;},
    appendChild(child){if(child.id)nodes.set(child.id,child);},
    insertBefore(child){if(child.id)nodes.set(child.id,child);}, remove(){}, closest(){return null;}};
  el.parentNode=el; return el;
}
function get(id) {if(!nodes.has(id))nodes.set(id,element(id));return nodes.get(id);}
const document = {getElementById:id=>id==='personal-radar-card'?(nodes.get(id)||null):get(id), createElement:()=>element(),
  head:element(), body:element(), querySelectorAll:()=>[], querySelector:()=>null,
  addEventListener(){}};
const payload = scenario.payload || {};
const requests=[];
let eventReply={};
const sandbox={document, location:{protocol:scenario.eventRefreshes?'http:':'file:',hash:'#personal',pathname:'/'},
  sessionStorage:{getItem(){return null;},setItem(){}}, URLSearchParams, URL,
  console:{log(){},warn(){},error(){}}, setTimeout(){},clearTimeout(){},
  setInterval(){},clearInterval(){}, requestAnimationFrame(){},
  fetch:async(url,opts={})=>{requests.push({url,method:opts.method||'GET'});
    if(url.startsWith('/api/logs')){
      if(eventReply.failure)throw Error('synthetic logs unavailable');
      return {ok:eventReply.http_ok!==false,json:async()=>({events:[],value_summary:eventReply.summary||{}})};
    }
    if(url==='/api/v1/value/metrics'){
      if(eventReply.failure)throw Error('synthetic metrics unavailable');
      return {ok:eventReply.http_ok!==false,json:async()=>eventReply.metrics||{}};
    }
    if(scenario.failure)throw Error('synthetic unavailable');
    return {ok:scenario.http_ok!==false,json:async()=>({data:scenario.radar||{}})};}};
sandbox.window=sandbox; sandbox.D=payload;
sandbox.addEventListener=()=>{};
sandbox.history={replaceState(){}};
let source=fs.readFileSync(process.argv[1],'utf8');
// Keep the complete asset executable; expose only existing functions and stop
// before unrelated startup queries. No production test hooks are added.
const marker='  const initialScroll = Number(scrollPositions[route().view]) || 0;';
if(!source.includes(marker))throw Error('asset startup boundary changed');
source=source.replace(marker,
  'window.testPersonal={hydratePersonalLiveStats,renderPersonalBase,loadRadarData,mountHealthRadar,loadPersonalEvents}; return;\n'+marker);
vm.runInNewContext(source,sandbox,{timeout:3000});
(async()=>{
  sandbox.testPersonal.renderPersonalBase();
  const values=[];
  for(const snapshot of scenario.snapshots||[payload]){
    sandbox.D=snapshot; sandbox.testPersonal.hydratePersonalLiveStats();
    values.push({rate:get('personal-bet-rate').textContent,
      detail:get('personal-bet-detail').textContent,
      route:get('personal-route-principal').textContent,
      value:get('personal-route-value').textContent});
  }
  if(scenario.checkRadar){sandbox.testPersonal.mountHealthRadar();await sandbox.testPersonal.loadRadarData();}
  const eventValues=[];
  for(const reply of scenario.eventRefreshes||[]){
    eventReply=reply; await sandbox.testPersonal.loadPersonalEvents();
    eventValues.push(Object.fromEntries(['kpi-net-saved','kpi-adjudications','kpi-pr-delivery',
      'kpi-code-lines','kpi-violations','ns-v3-score','personal-event-status'].map(id=>[id,get(id).textContent])));
  }
  process.stdout.write(JSON.stringify({eventValues,hero:get('personal').innerHTML,
    status:get('personal-now-status').innerHTML,values,
    radar:get('radar-score-badge').textContent,
    svg:get('radar-svg-container').innerHTML,
    radarHeader:get('personal-radar-card').innerHTML,requests}));
})().catch(e=>{console.error(e);process.exitCode=1;});
"""


def run_asset(**scenario):
    node = shutil.which("node")
    assert node, "Node.js is required for actual asset behavior"
    asset = Path(os.environ.get("ZHIXING_PERSONAL_TEST_ASSET", ASSET))
    result = subprocess.run([node, "-e", NODE, str(asset), json.dumps(scenario)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert all(item["method"] == "GET" for item in output["requests"])
    return output


def test_engineering_ratio_has_bounded_labels_and_no_completion_claim():
    result = run_asset(payload={"portfolio": {"actual": 549, "counts": {"done": 541}},
                                "strategic": {"status": "PARTIAL"},
                                "panel_value": {"state": "not_proven", "acceptance": {"current": None}}})
    assert result["values"][0]["rate"] == "98.5%"
    assert "工程BET完成比例" in result["hero"]
    assert "不代表本人采纳或愿景达成" in result["hero"]
    for claim in ["全量就绪", "全部跑通", "稳定运行期", "V5.0", "主权自治",
                  "0 次", "100% 红线零违背", "ed25519:xm-sovereign-root-v1",
                  "熔断器: ARMED", "外部泄露 0 字节", "0ms 熔断", "make gac-local-gate · PASS"]:
        assert claim not in result["hero"] + result["status"]
    assert "未核实" in result["hero"]


@pytest.mark.parametrize("portfolio", [{}, {"actual": 0, "counts": {"done": 0}},
    {"actual": -1, "counts": {"done": 1}}, {"actual": "bad", "counts": {"done": 1}},
    {"actual": 10, "counts": {"done": -1}}, {"actual": 10, "counts": {"done": 11}}])
def test_missing_or_invalid_engineering_denominator_is_not_a_rate(portfolio):
    value = run_asset(payload={"portfolio": portfolio})["values"][0]
    assert value["rate"] == "NO_DATA"
    assert "live" not in value["route"]


def test_zero_completion_and_refresh_do_not_become_human_value():
    result = run_asset(snapshots=[{"portfolio": {"actual": 10, "counts": {"done": 0}},
                                  "metrics_kpi": {"total_events_24h": 132}}, {}])
    assert result["values"][0]["rate"] == "0%"
    assert result["values"][1]["rate"] == "NO_DATA"
    assert all("收益未报告" in value["value"] for value in result["values"])


@pytest.mark.parametrize("radar", [{}, {"overall_health_score": None},
    {"overall_health_score": "97.5"}, {"overall_health_score": "bad"}])
def test_missing_or_invalid_radar_score_is_not_fabricated(radar):
    result = run_asset(checkRadar=True, radar=radar)
    assert result["radar"] == "综合健康度: NO_DATA"
    assert "100% 物理真实硬锚定" not in result["radarHeader"]
    assert "97.5%" not in result["radarHeader"]


def test_real_zero_radar_score_and_polygon_are_preserved():
    result = run_asset(checkRadar=True, radar={"overall_health_score": 0,
        "planes": [{"score": 0, "symbol": "A", "name": "治理"}]})
    assert result["radar"] == "综合健康度: 0%"
    assert 'points="150,150" fill="rgba(37,99,235,0.18)"' in result["svg"]


def test_observed_positive_radar_score_is_preserved_without_missing_plane_fill():
    result = run_asset(checkRadar=True, radar={"overall_health_score": 82.5,
        "planes": [{"symbol": "A", "name": "缺失"}]})
    assert result["radar"] == "综合健康度: 82.5%"
    assert "95%" not in result["svg"]
    assert "<circle" not in result["svg"]


@pytest.mark.parametrize("failure,http_ok", [(True, True), (False, False)])
def test_radar_failure_does_not_display_a_positive_score(failure, http_ok):
    result = run_asset(checkRadar=True, failure=failure, http_ok=http_ok,
                       radar={"overall_health_score": 98})
    assert result["radar"] == "综合健康度: NO_DATA"
    assert "100% 物理真实硬锚定" not in result["radarHeader"]
    assert "97.5%" not in result["radarHeader"]


def test_actual_http_event_refresh_keeps_absence_unknown():
    result = run_asset(eventRefreshes=[{}])
    value = result["eventValues"][0]
    for name in ["kpi-net-saved", "kpi-adjudications", "kpi-pr-delivery",
                 "kpi-code-lines", "kpi-violations"]:
        assert value[name] == "NO_DATA"
    assert "96%" not in value["personal-event-status"]
    assert len(result["requests"]) == 2


def test_actual_http_event_refresh_preserves_explicit_zero():
    value = run_asset(eventRefreshes=[{"summary": {
        "total_net_saved_formatted": "0.0 分钟", "total_net_saved_seconds": 0,
        "adjudications_count": 0, "adjudications_acceptance_rate": 0,
        "total_pr_delivered": 0, "total_code_lines_delivered": 0,
        "governance_violations_intercepted": 0}}])["eventValues"][0]
    assert value["kpi-net-saved"] == "0.0 分钟"
    assert value["kpi-adjudications"] == "0 次 (0%)"
    assert value["kpi-pr-delivery"] == "0 个 PR"
    assert value["kpi-violations"] == "0 次熔断拦截"


@pytest.mark.parametrize("next_reply", [{}, {"failure": True}, {"http_ok": False}])
def test_actual_http_event_refresh_clears_previous_positive_values(next_reply):
    previous = {"summary": {"total_net_saved_formatted": "10 分钟", "total_net_saved_seconds": 600,
        "adjudications_count": 2, "adjudications_acceptance_rate": "50%",
        "total_pr_delivered": 3, "total_code_lines_delivered": 100,
        "governance_violations_intercepted": 4},
        "metrics": {"north_star_v3": {"composite_score": 90}}}
    values = run_asset(eventRefreshes=[previous, next_reply])["eventValues"]
    assert values[0]["kpi-adjudications"] == "2 次 (50%)"
    assert values[0]["kpi-net-saved"] == "10 分钟"
    for name in ["kpi-net-saved", "kpi-adjudications", "kpi-pr-delivery",
                 "kpi-code-lines", "kpi-violations"]:
        assert values[1][name] == "NO_DATA"
    assert "90" not in values[1]["ns-v3-score"]
    if next_reply:
        assert "不可用" in values[1]["personal-event-status"]
