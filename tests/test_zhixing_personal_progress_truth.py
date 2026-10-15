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
const requests=[], timers=[];
let eventReply={}, responseCounts={logs:0,metrics:0};
function syntheticResponse(reply, fallback) {
  const status=reply.status??200;
  const body=Object.hasOwn(reply,'body')?reply.body:fallback;
  let consumed=false;
  return {status,ok:status>=200&&status<300,
    clone(){return syntheticResponse(reply,fallback);},
    json:async()=>{
      if(consumed)throw Error('response body consumed twice');
      consumed=true;
      if(reply.malformed)throw Error('synthetic invalid JSON');
      return body;
    }};
}
const sandbox={document, location:{protocol:scenario.eventRefreshes?'http:':'file:',hash:'#personal',pathname:'/'},
  sessionStorage:{getItem(){return null;},setItem(){}}, URLSearchParams, URL,
  console:{log(){},warn(){},error(){}},
  setTimeout(callback,delay){timers.push(delay);callback();},clearTimeout(){},
  setInterval(){},clearInterval(){}, requestAnimationFrame(){},
  fetch:async(url,opts={})=>{requests.push({url,method:opts.method||'GET',cache:opts.cache,credentials:opts.credentials});
    const kind=url.startsWith('/api/logs')?'logs':url==='/api/v1/value/metrics'?'metrics':null;
    if(kind){
      const queue=eventReply[kind+'Responses'];
      const reply=queue?queue[Math.min(responseCounts[kind]++,queue.length-1)]:
        {status:eventReply.http_ok===false?503:200};
      if(eventReply.failure||reply.reject)throw Error('synthetic '+kind+' unavailable');
      const fallback=kind==='logs'?{events:eventReply.events||[],value_summary:eventReply.summary||{}}:eventReply.metrics||{};
      return syntheticResponse(reply,fallback);
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
    eventReply=reply; responseCounts={logs:0,metrics:0}; await sandbox.testPersonal.loadPersonalEvents();
    eventValues.push(Object.fromEntries(['kpi-net-saved','kpi-adjudications','kpi-pr-delivery',
      'kpi-code-lines','kpi-violations','ns-v3-score','personal-event-status'].map(id=>[id,get(id).textContent])));
  }
  process.stdout.write(JSON.stringify({eventValues,hero:get('personal').innerHTML,
    status:get('personal-now-status').innerHTML,values,
    radar:get('radar-score-badge').textContent,
    svg:get('radar-svg-container').innerHTML,
    radarHeader:get('personal-radar-card').innerHTML,requests,timers}));
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


def _busy_reply():
    return {"status": 503,
            "body": {"error": "projection_validation_busy", "read_only": True}}


def _endpoint_requests(output, endpoint):
    url = "/api/logs?limit=40&source=all" if endpoint == "logs" else "/api/v1/value/metrics"
    return [request for request in output["requests"] if request["url"] == url]


@pytest.mark.parametrize("endpoint", ["logs", "metrics"])
@pytest.mark.parametrize("busy_attempts", [1, 2])
def test_personal_read_busy_recovers_using_real_success(endpoint, busy_attempts):
    reply = {"events": [{"ts": "2026-10-16T00:00:00Z", "type": "fixture",
                         "source": "a2a-messages"}],
             "metrics": {"north_star_v3": {"composite_score": 11,
                                            "composite_verdict": "OBSERVED"}},
             endpoint + "Responses": [_busy_reply()] * busy_attempts + [{"status": 200}]}
    output = run_asset(eventRefreshes=[reply])
    assert len(_endpoint_requests(output, endpoint)) == busy_attempts + 1
    assert len(_endpoint_requests(output, "metrics" if endpoint == "logs" else "logs")) == 1
    assert output["timers"] == [300, 900][:busy_attempts]
    value = output["eventValues"][-1]
    assert value["personal-event-status"] == "已读取 1 条来源事件 · 活动记录不等于本人采纳或收益"
    assert value["ns-v3-score"] == "11 / 100 (OBSERVED)"
    assert value["kpi-net-saved"] == "NO_DATA"
    assert all(r["method"] == "GET" and r["cache"] == "no-store"
               and r["credentials"] == "omit" for r in output["requests"])


@pytest.mark.parametrize("endpoint", ["logs", "metrics"])
def test_personal_read_persistent_busy_stops_after_three_and_clears_old_value(endpoint):
    previous = {"summary": {"total_net_saved_seconds": 600},
                "metrics": {"north_star_v3": {"composite_score": 90}}}
    output = run_asset(eventRefreshes=[previous, {endpoint + "Responses": [_busy_reply()]}])
    assert len(_endpoint_requests(output, endpoint)) == 4  # one earlier success, then three busy
    assert output["timers"] == [300, 900]
    current = output["eventValues"][-1]
    assert "不可用" in current["personal-event-status"]
    assert current["kpi-net-saved"] == "NO_DATA"
    assert current["ns-v3-score"] == "NO_DATA"


@pytest.mark.parametrize("endpoint", ["logs", "metrics"])
@pytest.mark.parametrize("failure", [
    {"status": 503, "body": {"error": "projection_payload_stale", "read_only": True}},
    {"status": 503, "body": {"error": "projection_code_drift", "read_only": True}},
    {"status": 403, "body": {"error": "projection_validation_busy", "read_only": True}},
    {"status": 500, "body": {"error": "projection_validation_busy", "read_only": True}},
    {"status": 503, "body": {"error": "projection_validation_busy", "read_only": False}},
    {"status": 503, "body": {"error": "projection_validation_busy", "read_only": "true"}},
    {"status": 503, "body": {"error": "projection_validation_busy"}},
    {"status": 503, "body": None},
    {"status": 503, "malformed": True},
    {"reject": True},
])
def test_personal_read_other_failures_never_retry(endpoint, failure):
    output = run_asset(eventRefreshes=[{endpoint + "Responses": [failure, {"status": 200}]}])
    assert len(_endpoint_requests(output, endpoint)) == 1
    assert output["timers"] == []
    assert "不可用" in output["eventValues"][-1]["personal-event-status"]
    assert output["eventValues"][-1]["ns-v3-score"] == "NO_DATA"


@pytest.mark.parametrize("endpoint", ["logs", "metrics"])
def test_personal_read_busy_then_permanent_error_does_not_try_third(endpoint):
    permanent = {"status": 503,
                 "body": {"error": "projection_payload_stale", "read_only": True}}
    output = run_asset(eventRefreshes=[
        {endpoint + "Responses": [_busy_reply(), permanent, {"status": 200}]}])
    assert len(_endpoint_requests(output, endpoint)) == 2
    assert output["timers"] == [300]
    assert "不可用" in output["eventValues"][-1]["personal-event-status"]


def test_personal_read_busy_then_actual_empty_preserves_zero_without_metrics_value():
    summary = {"total_net_saved_seconds": 0, "adjudications_count": 0,
               "adjudications_acceptance_rate": 0}
    output = run_asset(eventRefreshes=[{
        "logsResponses": [_busy_reply(), {"status": 200,
            "body": {"events": [], "value_summary": summary}}],
        "metricsResponses": [{"status": 403}],
    }])
    current = output["eventValues"][-1]
    assert current["kpi-net-saved"] == "0.0 分钟"
    assert current["kpi-adjudications"] == "0 次 (0%)"
    assert current["ns-v3-score"] == "NO_DATA"
    assert "已读取 0 条" in current["personal-event-status"]
    assert "价值指标来源不可用" in current["personal-event-status"]
    assert output["timers"] == [300]


# Separate export scenarios retain the original fifty event/progress cases unchanged.
EXPORT_NODE = NODE.replace(
    "addEventListener(){}, setAttribute(){}, getAttribute(){return null;},",
    """listeners:{}, addEventListener(type,fn){this.listeners[type]=fn;},
    click(){if(this.listeners.click)this.listeners.click();else downloads.push({name:this.download,href:this.href});},
    setAttribute(key,value){this[key]=value;}, getAttribute(){return null;},"""
).replace(
    "const requests=[], timers=[];",
    """const requests=[], timers=[], downloads=[], blobs=[], revoked=[];
    class LocalBlob {constructor(parts,options){this.content=parts.join('');this.type=options.type;}}
    const localURL={createObjectURL(blob){blobs.push(blob);return 'blob:local-'+blobs.length;},
      revokeObjectURL(url){revoked.push(url);}};"""
).replace(
    "URLSearchParams, URL,", "URLSearchParams, URL:localURL, Blob:LocalBlob,"
).replace(
    "loadPersonalEvents}; return;",
    "loadPersonalEvents,buildPersonalDeliverySummary,initPersonalDeliveryExport}; return;"
).replace(
    "  const values=[];",
    """  const values=[];
    const before={preview:get('personal-delivery-preview').value,
      disabled:get('personal-delivery-download').disabled};
    for(const snapshot of scenario.exportSnapshots||[payload]){
      sandbox.D=snapshot;get('personal-delivery-generate').click();
    }
    const preview=get('personal-delivery-preview').value;
    if(scenario.changeBeforeDownload)sandbox.D={portfolio:{actual:999}};
    get('personal-delivery-download').click();
    process.stdout.write(JSON.stringify({before,preview,
      previewHTML:get('personal-delivery-preview').innerHTML,
      readOnly:get('personal-delivery-preview').readOnly,
      downloads,blobs,revoked,requests,hero:get('personal').innerHTML}));
    return;"""
)


def run_delivery_export(**scenario):
    node = shutil.which("node")
    assert node
    asset = Path(os.environ.get("ZHIXING_PERSONAL_TEST_ASSET", ASSET))
    result = subprocess.run([node, "-e", EXPORT_NODE, str(asset), json.dumps(scenario)],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["requests"] == []
    return output


def delivery_snapshot():
    return {
        "generated_at": "2026-10-15T17:49:56Z",
        "portfolio": {"state": "OBSERVED", "source": "github://official/ledger",
                      "sha": "a" * 40, "ledger_sha256": "b" * 64,
                      "observed_at": "2026-10-15T17:48:15Z",
                      "actual": 12, "counts": {"done": 9, "pending": 2, "blocked": 1},
                      "bet_records": [{"id": "BET-OPEN", "title": "待处理", "status": "pending",
                                       "owner": None}, {"id": "BET-CLOSED", "status": "done"}]},
        "tasks": {"source": ".omo/tasks", "recent_done": [
            {"id": "TASK-DONE", "title": "真实交付", "status": "done",
             "completed_at": "2026-10-15T17:45:22Z", "artifacts": [
                 {"path": "/local/交付.md", "status": "ready", "sha256": "c" * 64,
                  "bytes": 3120, "preview": "PRIVATE_ARTIFACT_BODY",
                  "metadata": {"secret": "PRIVATE_METADATA"}}]}]},
        "source_states": {"tasks": {"status": "OK", "observed_at": "2026-10-15T17:47:00Z"},
                          "agent_brief": {"status": "PARTIAL", "observed_at": "2026-10-15T17:40:00Z"}},
        "next_actions": [{"id": "NEXT-ONE", "state": "admission_required", "detail": "先核准入"}]}


def test_delivery_export_preview_download_and_source_binding():
    output = run_delivery_export(payload=delivery_snapshot(), changeBeforeDownload=True)
    text = output["preview"]
    assert "# 项目交付摘要（本页快照）" in text
    for value in ["12", "done=9", "BET-OPEN", "TASK-DONE", "/local/交付.md",
                  "c" * 64, "a" * 40, "b" * 64, "2026-10-15T17:48:15Z",
                  "2026-10-15T17:47:00Z", "NEXT-ONE", "草稿", "收益未报告"]:
        assert value in text
    assert "BET-CLOSED" not in text
    assert "任务done不等于BET/KR/HumanOutcome" in text
    assert "生成交付摘要" in output["hero"] and "下载Markdown" in output["hero"]
    assert output["before"] == {"preview": "", "disabled": True}
    assert output["readOnly"] is True and output["previewHTML"] == ""
    assert len(output["downloads"]) == len(output["blobs"]) == 1
    assert output["downloads"][0]["name"] == "project-delivery-summary-20261015T174956Z.md"
    assert output["blobs"][0] == {"content": text, "type": "text/markdown;charset=utf-8"}
    assert output["revoked"] == [output["downloads"][0]["href"]]
    assert "999" not in text  # Download freezes the visible preview, not a later snapshot.


@pytest.mark.parametrize("bad", [None, [], "bad", {"actual": None, "counts": {"done": None}},
                                 {"actual": -1, "counts": {"done": "9"}}])
def test_delivery_export_missing_malformed_is_unknown(bad):
    output = run_delivery_export(payload={"portfolio": bad, "tasks": {"recent_done": None},
                                          "next_actions": None})
    assert "UNKNOWN" in output["preview"]
    assert "done=0" not in output["preview"] and "0/0" not in output["preview"]
    assert "project-delivery-summary-unknown.md" == output["downloads"][0]["name"]


def test_delivery_export_stale_per_source_not_promoted_by_outer_clock():
    data = delivery_snapshot()
    data["portfolio"]["observed_at"] = "2026-09-01T00:00:00Z"
    data["source_states"]["tasks"] = {"status": "STALE", "observed_at": "2026-09-02T00:00:00Z"}
    output = run_delivery_export(payload=data)
    assert "portfolio" in output["preview"] and "STALE" in output["preview"]
    assert "2026-09-01T00:00:00Z" in output["preview"]
    assert "2026-09-02T00:00:00Z" in output["preview"]
    assert "逐源时钟" in output["preview"] and "当前有效性未证明" in output["preview"]


def test_delivery_export_allowlist_sanitizes_markdown_and_private_extras():
    data = delivery_snapshot()
    unsafe = '<script>[click](https://bad) `code`\n# forged\x00'
    data["tasks"]["recent_done"][0]["title"] = unsafe
    data["next_actions"][0]["detail"] = unsafe
    data["private"] = {"token": "PRIVATE_ROOT_SECRET"}
    data["portfolio"]["metadata"] = {"token": "PRIVATE_PORTFOLIO_SECRET"}
    data["tasks"]["recent_done"][0]["prompt"] = "PRIVATE_USER_PROMPT"
    text = run_delivery_export(payload=data)["preview"]
    for forbidden in ["PRIVATE_", "<script>", "[click]", "`code`", "\n# forged", "\x00"]:
        assert forbidden not in text
    assert "click" in text and "forged" in text


def test_delivery_export_bounds_rows_and_refresh_clears_previous_snapshot():
    data = delivery_snapshot()
    data["next_actions"] = [{"id": "ACTION-"+str(i)} for i in range(8)]
    data["tasks"]["recent_done"] *= 30
    output = run_delivery_export(payload=data)
    assert "ACTION-2" in output["preview"] and "ACTION-3" not in output["preview"]
    assert output["preview"].count("TASK-DONE") == 10
    cleared = run_delivery_export(payload=data, exportSnapshots=[data, {}])
    assert "TASK-DONE" not in cleared["preview"] and "BET-OPEN" not in cleared["preview"]
    assert "UNKNOWN" in cleared["preview"]


def test_delivery_export_uses_explicit_zero_and_does_not_accept_nested_counter():
    data = delivery_snapshot()
    data["portfolio"]["actual"] = 0
    data["portfolio"]["counts"] = {"done": 0, "pending": {"private": 4}}
    text = run_delivery_export(payload=data)["preview"]
    assert "工程BET声明总数=0" in text and "done=0" in text
    assert "pending=UNKNOWN" in text
