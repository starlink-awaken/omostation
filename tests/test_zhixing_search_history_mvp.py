"""Run the delivered search IIFE and the existing HUD keyboard listener in Node."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest


_resolver_file = Path(__file__).resolve().parents[1] / "bin/lib/repo_root.py"
_spec = importlib.util.spec_from_file_location("search_mvp_repo_root", _resolver_file)
assert _spec is not None and _spec.loader is not None
_resolver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_resolver)
ASSETS = _resolver.code_root() / "bin/panorama/assets/host"


NODE = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const p = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const KEY = 'zx-search-history';
class Target {
  constructor(){ this.listeners = {}; }
  addEventListener(type, fn, options){
    (this.listeners[type] ||= []).push({fn, capture:options === true || !!options?.capture, once:!!options?.once});
  }
  emit(type, e = {}, capture = false){
    for (const item of [...(this.listeners[type] || [])]) {
      if (item.capture !== capture) continue;
      item.fn.call(this, e);
      if (item.once) this.listeners[type] = this.listeners[type].filter(x => x !== item);
    }
  }
}
class Element extends Target {
  constructor(tag, doc){ super(); this.tagName = tag.toUpperCase(); this.doc = doc; this.children = []; this.style = {}; this.className = ''; this.value = ''; this._text = ''; }
  set textContent(v){ this._text = String(v); this.children = []; }
  get textContent(){ return this._text + this.children.map(x => x.textContent).join(''); }
  set innerHTML(v){ throw Error('Search must render untrusted content through text nodes'); }
  appendChild(n){ this.children.push(n); return n; }
  replaceChildren(...nodes){ this.children = nodes; this._text = ''; }
  focus(){ this.doc.activeElement = this; }
  click(){ this.emit('click', {target:this}); }
}
function create(options = {}) {
  const doc = new Target();
  doc.readyState = options.late ? 'loading' : 'complete';
  let mounted = !options.late;
  const nodes = {};
  for (const [id,tag] of [['search-overlay','div'],['search-input','input'],['search-results','div'],['search-toggle','button'],['omni-command-modal','div']]) nodes[id] = new Element(tag, doc);
  nodes['search-overlay'].style.display = nodes['omni-command-modal'].style.display = 'none';
  doc.activeElement = new Element('body', doc);
  doc.getElementById = id => mounted ? nodes[id] || null : null;
  doc.createElement = tag => new Element(tag, doc);
  const win = new Target();
  const map = options.map || new Map(Object.entries(options.saved || {}));
  const state = {hudOpens:0, hudCloses:0, nav:[]};
  const storage = {
    getItem(k){ if (options.storage === 'all' || options.storage === 'read') throw Error('SecurityError'); return map.get(k) ?? null; },
    setItem(k,v){ if (options.storage === 'all' || options.storage === 'write') throw Error('QuotaExceededError'); map.set(k,v); },
    removeItem(k){ if (options.storage === 'all') throw Error('SecurityError'); map.delete(k); }
  };
  if (options.storage === 'access') Object.defineProperty(win, 'localStorage', {get(){throw Error('SecurityError');}});
  else win.localStorage = storage;
  function openCommandPalette(){ state.hudOpens++; nodes['omni-command-modal'].style.display = 'flex'; }
  function closeCommandPalette(){ state.hudCloses++; nodes['omni-command-modal'].style.display = 'none'; }
  win.openCommandPalette = openCommandPalette;
  win.closeCommandPalette = closeCommandPalette;
  const context = vm.createContext({window:win, document:doc, D:options.data || {agents:[],gates:[],recent_events:{}}, go:id=>state.nav.push(id), openCommandPalette, closeCommandPalette, omniResults:[], selectedOmniIndex:-1, renderOmniResults(){}, selectOmniItem(){}, console});
  if (options.hudFirst) vm.runInContext(p.hudKeyboard, context);
  vm.runInContext(p.search, context);
  if (!options.hudFirst) vm.runInContext(p.hudKeyboard, context);
  function key(key, extras = {}, target = nodes['search-input']) {
    const e = {key, ctrlKey:false, metaKey:false, altKey:false, repeat:false, isComposing:false, keyCode:0, defaultPrevented:false, stopped:false, target, preventDefault(){this.defaultPrevented = true;}, stopPropagation(){this.stopped = true;}, ...extras};
    doc.emit('keydown', e, true);
    if (!e.stopped) target.emit('keydown', e);
    if (!e.stopped) doc.emit('keydown', e);
    if (!e.stopped) win.emit('keydown', e);
    return e;
  }
  function type(value){ nodes['search-input'].value = value; nodes['search-input'].emit('input', {target:nodes['search-input']}); }
  function commit(value){ type(value); key('Enter'); }
  function find(cls, node = nodes['search-results']) {
    return [...(node.className.split(' ').includes(cls) ? [node] : []), ...node.children.flatMap(x => find(cls,x))];
  }
  function ready(){ mounted = true; doc.readyState = 'interactive'; doc.emit('DOMContentLoaded'); }
  return {nodes, doc, win, state, map, ready, key, type, commit, find, open(){nodes['search-toggle'].click();}, history(){return JSON.parse(map.get(KEY) || '[]');}};
}
const t = create(p.options);
switch (p.scenario) {
  case 'late_dom':
    assert.equal(t.nodes['search-toggle'].listeners.click, undefined);
    t.ready(); t.open();
    assert.equal(t.nodes['search-overlay'].style.display, 'flex');
    t.doc.emit('DOMContentLoaded');
    assert.equal(t.nodes['search-toggle'].listeners.click.length, 1);
    break;
  case 'commit_not_input':
    t.open(); t.type('周'); t.type('周报'); assert.deepEqual(t.history(), []);
    t.key('Enter'); assert.deepEqual(t.history(), ['周报']);
    break;
  case 'limit_dedupe':
    t.open(); for(let i=0;i<9;i++) t.commit('查询'+i);
    assert.deepEqual(t.history(), ['查询8','查询7','查询6','查询5','查询4','查询3','查询2','查询1']);
    t.commit(' 查询4 '); assert.equal(t.history()[0], '查询4'); assert.equal(t.history().length, 8);
    t.commit('Report'); t.commit(' report '); assert.equal(t.history()[0], 'report');
    assert.equal(t.history().filter(x=>x.toLowerCase()==='report').length, 1);
    break;
  case 'persistent_rerun': {
    t.open(); t.commit('周报'); t.key('Escape'); t.open();
    assert.match(t.nodes['search-results'].textContent, /最近搜索/);
    const reopened = create({map:t.map}); reopened.open();
    reopened.find('zx-search-history-query')[0].click();
    assert.equal(reopened.nodes['search-input'].value, '周报');
    assert.match(reopened.find('zx-search-result')[0].textContent, /接下来做什么/);
    reopened.find('zx-search-result')[0].click();
    assert.deepEqual(reopened.state.nav, ['next']);
    break;
  }
  case 'clear':
    t.map.set('unrelated', 'keep'); t.open(); t.commit('周报'); t.key('Escape'); t.open();
    t.find('zx-search-history-clear')[0].click();
    assert.deepEqual(t.history(), []); assert.equal(t.map.get('unrelated'), 'keep');
    t.key('Escape'); t.open(); assert.equal(t.find('zx-search-history-query').length, 0);
    break;
  case 'malformed':
    t.open(); assert.equal(t.find('zx-search-history-query').length, 0);
    t.type('周报'); t.find('zx-search-result')[0].click();
    assert.deepEqual(t.state.nav, ['next']);
    break;
  case 'storage_failure':
    t.open(); t.commit('周报'); t.key('Escape'); t.open();
    assert.equal(t.find('zx-search-history-query')[0].textContent, '周报');
    t.find('zx-search-history-clear')[0].click();
    t.type('周报'); t.find('zx-search-result')[0].click(); assert.deepEqual(t.state.nav,['next']);
    break;
  case 'aliases':
    t.open(); t.type(p.query); t.find('zx-search-result')[0].click();
    assert.deepEqual(t.state.nav, ['next']); assert.deepEqual(t.history(), [p.query]);
    assert.equal(t.nodes['search-overlay'].style.display, 'none');
    break;
  case 'malicious': {
    t.open();
    assert.equal(t.find('zx-search-history-query')[0].textContent, p.malicious);
    t.find('zx-search-history-query')[0].click(); t.key('Escape'); t.open();
    t.type('INJECT');
    assert.match(t.find('zx-search-result')[0].textContent, /<img/);
    t.find('zx-search-result')[0].click();
    assert.equal(t.state.nav.length, 0);
    break;
  }
  case 'ime':
    t.open(); t.type('周'); t.nodes['search-input'].emit('compositionstart'); t.key('Enter');
    assert.deepEqual(t.history(), []);
    t.nodes['search-input'].emit('compositionend'); t.type('周报');
    t.key('Enter', {isComposing:true}); t.key('Enter', {keyCode:229}); assert.deepEqual(t.history(), []);
    t.key('Enter'); assert.deepEqual(t.history(), ['周报']);
    break;
  case 'keyboard_owners':
    t.win.openCommandPalette(); assert.equal(t.state.hudOpens,1);
    assert.equal(t.key('K', {metaKey:true}).defaultPrevented, true);
    assert.equal(t.nodes['search-overlay'].style.display, 'flex');
    assert.equal(t.nodes['omni-command-modal'].style.display, 'none');
    assert.equal(t.state.hudOpens,1);
    t.key('Escape'); assert.equal(t.nodes['search-overlay'].style.display,'none');
    t.key('k',{ctrlKey:true}); assert.equal(t.state.hudOpens,1);
    t.key('Escape'); t.win.openCommandPalette(); assert.equal(t.state.hudOpens,2);
    assert.equal(t.nodes['omni-command-modal'].style.display,'flex');
    t.key('Escape'); assert.equal(t.nodes['omni-command-modal'].style.display,'none');
    break;
  case 'number_navigation':
    t.doc.activeElement = t.doc.createElement('body'); t.key('1'); assert.deepEqual(t.state.nav,['orient']);
    t.open(); t.key('9'); assert.deepEqual(t.state.nav,['orient']);
    break;
  default: throw Error('Unknown scenario');
}
console.log('PASS '+p.scenario);
"""


def run_search(scenario, **extra):
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    search = template.split("/* === Global Search & Keyboard Navigation === */", 1)[1].split(
        "/* === View Customization === */", 1
    )[0]
    hud = (ASSETS / "ecosystem_ui.js.asset").read_text(encoding="utf-8")
    keyboard = hud.split("// 全局键盘监听 (⌘K / ESC / 上下选择)", 1)[1].split(
        "// 绑定输入事件", 1
    )[0]
    node = shutil.which("node")
    assert node, "Node is required for actual delivered JavaScript behavior"
    result = subprocess.run(
        [node, "-e", NODE],
        input=json.dumps({"search": search, "hudKeyboard": keyboard, "scenario": scenario, **extra}),
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"PASS {scenario}"


@pytest.mark.parametrize("scenario", [
    "late_dom", "commit_not_input", "limit_dedupe", "persistent_rerun", "clear", "ime", "number_navigation",
])
def test_search_lifecycle_and_history(scenario):
    run_search(scenario, options={"late": scenario == "late_dom"})


@pytest.mark.parametrize("query", ["周报", "已完成任务", "成品"])
def test_existing_weekly_route(query):
    run_search("aliases", query=query)


@pytest.mark.parametrize("saved", ["{bad JSON", "{}", '["周报", 7]'])
def test_bad_storage_does_not_prevent_search(saved):
    run_search("malformed", options={"saved": {"zx-search-history": saved}})


@pytest.mark.parametrize("storage", ["all", "write", "access"])
def test_storage_rejection_keeps_session_search_usable(storage):
    run_search("storage_failure", options={"storage": storage})


@pytest.mark.parametrize("hud_first", [True, False])
def test_one_cmd_k_owner_in_both_real_listener_orders(hud_first):
    run_search("keyboard_owners", options={"hudFirst": hud_first})


def test_query_and_snapshot_text_cannot_inject_handlers():
    malicious = '<img src=x onerror="globalThis.INJECT=1">'
    run_search("malicious", malicious=malicious, options={
        "saved": {"zx-search-history": json.dumps([malicious])},
        "data": {"agents": [{"worktree": malicious, "branch": "INJECT"}], "gates": [], "recent_events": {}},
    })


def test_template_inline_scripts_still_parse(tmp_path):
    node = shutil.which("node")
    assert node, "Node is required to validate template JavaScript"
    template = (ASSETS / "template.html").read_text(encoding="utf-8")
    scripts = [(attrs, body) for attrs, body in re.findall(r"<script\b([^>]*)>(.*?)</script>", template, re.S)
               if "application/json" not in attrs and "src=" not in attrs]
    assert scripts
    for index, (_, body) in enumerate(scripts):
        source = tmp_path / f"template-{index}.js"
        source.write_text(body, encoding="utf-8")
        result = subprocess.run([node, "--check", str(source)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
