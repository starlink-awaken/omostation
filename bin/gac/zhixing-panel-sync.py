#!/usr/bin/env python3
"""织星驾驶舱（:43191）面板资产 — 版本化、幂等注入与漂移自愈.

问题（2026-09-17/18 实证）: `~/.local/share/zhixing-dashboard/` **不受版本控制**，
多 agent 并发编辑同一 `template.html` 互相覆盖 —— 场景面板已被覆盖丢 2 次，
另有一次外来语法错误直接损坏整个页面脚本。

解法: 面板代码作为**版本化资产**存于仓库, 本脚本幂等注入部署目录:

| 资产 | 部署位置 |
|---|---|
| `bin/panorama/assets/scene-panel.html`                 | 场景面板 nav/section/script/调用点 四片段 |
| `bin/panorama/assets/panels/{logs,metrics,value}.html` | 三板块 section 标记块 |
| `bin/panorama/assets/panels/{logs,metrics,value}.js`   | 三板块脚本标记块 |
| refresh.py 白名单补丁                                   | panel_events/history/value 三键透传 |

注入使用显式标记: 已迁移时**按标记替换**（永不重复插入）; 未迁移时按锚点首次迁移:

    <!-- ZHIXING-PANEL:logs:BEGIN -->   … <!-- ZHIXING-PANEL:logs:END -->
    /* ZHIXING-PANEL-JS:logs:BEGIN */   … /* ZHIXING-PANEL-JS:logs:END */

子命令:
    ensure   幂等注入所有面板 + refresh.py 白名单（注入前自动备份）
    check    漂移检测（任一缺失 → exit 1，供 cron/hook 告警）
    status   报告各面板注入状态
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # cron 下 python3 可能是 3.9 (<3.11 无 datetime.UTC)
    from datetime import timezone as _timezone
    UTC = _timezone.utc
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = _ROOT / "bin" / "panorama" / "assets"
PANEL_DIR = ASSET_DIR / "panels"
DASHBOARD_DIR = Path.home() / ".local/share/zhixing-dashboard"
TEMPLATE = DASHBOARD_DIR / "template.html"
REFRESH_PY = DASHBOARD_DIR / "refresh.py"

# ── 标记式面板（section + 脚本块）───────────────────────────────────────
# 注入顺序: 先 metrics（锚点用非面板的 #health）→ logs → value。
# 这样即使三块被整体覆盖删除（历史真实故障: 面板被覆盖丢 2 次），
# 也能按「插入到下一块之前」重建, 而不是只能靠已存在的 <section> 定位。
MARKER_PANELS = {"metrics": "metrics", "logs": "logs", "value": "value"}
SECTION_FALLBACK_ANCHOR = {
    "metrics": '<section id="health"',
    "logs": '<section id="metrics"',
    "value": '<section id="logs"',
}
HTML_ANCHOR = "<!-- ZHIXING-PANEL:{name}:BEGIN -->"
HTML_END = "<!-- ZHIXING-PANEL:{name}:END -->"
JS_ANCHOR = "/* ZHIXING-PANEL-JS:{name}:BEGIN */"
JS_END = "/* ZHIXING-PANEL-JS:{name}:END */"
# JS 块插入位置: 必须在 `const D=…` 之后、面板调用点之前
JS_INSERT_ANCHOR = "/* Call populate functions with error handling */"

# ── 场景面板（四片段, 历史实现保持兼容）───────────────────────────────
ANCHOR_NAV = '<a href="#knowledge-memory"'
ANCHOR_SECTION = '<section id="skills-inventory"'
ANCHOR_SCRIPT = "document.addEventListener('DOMContentLoaded'"
ANCHOR_CALL = "window.addEventListener('hashchange'"
MARKER_SECTION = 'id="scene-system"'
MARKER_FN = "function renderSceneSystem"
MARKER_CALL = "renderSceneSystem(D);"  # 带分号, 以区分函数定义

# ── refresh.py 白名单补丁 ──────────────────────────────────────────────
REFRESH_ANCHOR = '            data["metrics_kpi"] = _p.get("metrics_kpi", {})'
REFRESH_PATCH = '''
            # 驾驶舱三板块真实数据 (logs/metrics/value)
            data["panel_events"] = _p.get("panel_events", {})
            data["panel_history"] = _p.get("panel_history", {})
            data["panel_value"] = _p.get("panel_value", {})'''
REFRESH_MARK = 'data["panel_events"]'


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _insert_before(text: str, anchor: str, payload: str) -> tuple[str, bool]:
    idx = text.find(anchor)
    if idx < 0:
        return text, False
    return text[:idx] + payload + "\n" + text[idx:], True


def _insert_after_line(text: str, anchor: str, payload: str) -> tuple[str, bool]:
    idx = text.find(anchor)
    if idx < 0:
        return text, False
    eol = text.find("\n", idx)
    if eol < 0:
        return text + "\n" + payload, True
    return text[:eol + 1] + payload + "\n" + text[eol + 1:], True


def _replace_region(text: str, begin: str, end: str, body: str) -> tuple[str, bool]:
    """替换 begin/end 之间的内容, 保留标记本身。"""
    b = text.find(begin)
    if b < 0:
        return text, False
    e = text.find(end, b + len(begin))
    if e < 0:
        return text, False
    return text[:b + len(begin)] + "\n" + body.strip() + "\n" + text[e:], True


def _has_region(text: str, begin: str, end: str) -> bool:
    return begin in text and end in text


# ══ 标记式面板 ═════════════════════════════════════════════════════════
def _panel_assets(name: str) -> tuple[str, str]:
    html_path, js_path = PANEL_DIR / f"{name}.html", PANEL_DIR / f"{name}.js"
    if not html_path.is_file() or not js_path.is_file():
        raise FileNotFoundError(f"面板资产缺失: {html_path} / {js_path}")
    return _read(html_path), _read(js_path)


def _panel_block(name: str, body: str) -> str:
    return "\n".join([HTML_ANCHOR.format(name=name), body.strip(), HTML_END.format(name=name)])


def _migrate_section(html: str, name: str, body: str, section_id: str) -> tuple[str, str]:
    """未迁移: 把整个 <section id="...">…</section> 换成带标记的资产内容。

    若该 section 已**整体消失**（被并发覆盖删除），退化为按下一块的位置重建 ——
    这是历史真实故障模式, 必须能自愈而不能只报 section_missing。
    """
    block = _panel_block(name, body)
    pattern = re.compile(r'<section id="' + re.escape(section_id) + r'"[^>]*>.*?</section>', re.S)
    match = pattern.search(html)
    if match:
        return html[:match.start()] + block + html[match.end():], "migrated"

    anchor = SECTION_FALLBACK_ANCHOR.get(name)
    if anchor:
        restored, ok = _insert_before(html, anchor, block + "\n")
        if ok:
            return restored, "restored"
    # 最后兜底: 追加到主内容区末尾
    for tail in ("</main>", "</body>"):
        restored, ok = _insert_before(html, tail, block + "\n")
        if ok:
            return restored, "restored_append"
    return html, "section_missing"


def apply_marker_panel(html: str, name: str, section_id: str) -> tuple[str, dict]:
    body_html, body_js = _panel_assets(name)
    begin, end = HTML_ANCHOR.format(name=name), HTML_END.format(name=name)
    actions: dict[str, str] = {}

    if _has_region(html, begin, end):
        html, ok = _replace_region(html, begin, end, body_html)
        actions["section"] = "replaced" if ok else "marker_broken"
    else:
        html, actions["section"] = _migrate_section(html, name, body_html, section_id)

    js_begin, js_end = JS_ANCHOR.format(name=name), JS_END.format(name=name)
    if _has_region(html, js_begin, js_end):
        html, ok = _replace_region(html, js_begin, js_end, body_js)
        actions["script"] = "replaced" if ok else "marker_broken"
    else:
        block = js_begin + "\n" + body_js.strip() + "\n" + js_end + "\n"
        html, ok = _insert_before(html, JS_INSERT_ANCHOR, block)
        actions["script"] = "inserted" if ok else "anchor_missing"
    return html, actions


# ══ 场景面板（四片段）══════════════════════════════════════════════════
def _scene_parts() -> dict[str, str]:
    text = _read(ASSET_DIR / "scene-panel.html")
    nav = re.search(r"<!-- NAV -->\n(.*?)\n", text, re.S)
    sec = re.search(r"<!-- SECTION -->\n(.*?)\n<!-- SCRIPT -->", text, re.S)
    scr = re.search(r"<script>\n(.*?)\n</script>", text, re.S)
    if not (nav and sec and scr):
        raise ValueError("场景面板资产片段不完整")
    return {"nav": nav.group(1), "section": sec.group(1), "script": scr.group(1)}


def apply_scene_panel(html: str) -> tuple[str, dict]:
    parts = _scene_parts()
    actions: dict[str, str] = {}
    if MARKER_SECTION in html:
        actions["section"] = "kept"
    else:
        html, ok = _insert_before(html, ANCHOR_SECTION, parts["section"])
        actions["section"] = "inserted" if ok else "anchor_missing"
    if 'href="#scene-system"' in html:
        actions["nav"] = "kept"
    else:
        html, ok = _insert_after_line(html, ANCHOR_NAV, parts["nav"])
        actions["nav"] = "inserted" if ok else "anchor_missing"
    if MARKER_FN in html:
        actions["script"] = "kept"
    else:
        html, ok = _insert_before(html, ANCHOR_SCRIPT,
                                  "<script>\n" + parts["script"] + "\n</script>")
        actions["script"] = "inserted" if ok else "anchor_missing"
    if MARKER_CALL in html:
        actions["call_embedded"] = "kept"
    else:
        html, ok = _insert_after_line(html, ANCHOR_CALL, "renderSceneSystem(D);")
        actions["call_embedded"] = "inserted" if ok else "anchor_missing"
    if "renderSceneSystem(d)" in html:
        actions["call_live"] = "kept"
    else:
        match = re.search(r"(\n(\s*)renderPanorama\(d\);)", html)
        if match:
            indent = match.group(2)
            html = html[:match.end(1)] + f"\n{indent}renderSceneSystem(d);" + html[match.end(1):]
            actions["call_live"] = "inserted"
        else:
            actions["call_live"] = "anchor_missing"
    return html, actions


# ══ refresh.py 白名单 ══════════════════════════════════════════════════
def apply_refresh_allowlist() -> str:
    if not REFRESH_PY.is_file():
        return "source_missing"
    text = _read(REFRESH_PY)
    if REFRESH_MARK in text:
        return "kept"
    if REFRESH_ANCHOR not in text:
        return "anchor_missing"
    shutil.copy2(REFRESH_PY, DASHBOARD_DIR / (REFRESH_PY.name + ".before-panel-sync"))
    REFRESH_PY.write_text(text.replace(REFRESH_ANCHOR, REFRESH_ANCHOR + REFRESH_PATCH, 1),
                          encoding="utf-8")
    return "patched"


# ══ 状态 / 执行 ════════════════════════════════════════════════════════
def status() -> dict:
    if not TEMPLATE.is_file():
        return {"template": str(TEMPLATE), "exists": False}
    html = _read(TEMPLATE)
    panels = {
        name: (_has_region(html, HTML_ANCHOR.format(name=name), HTML_END.format(name=name))
               and _has_region(html, JS_ANCHOR.format(name=name), JS_END.format(name=name)))
        for name in MARKER_PANELS
    }
    return {
        "template": str(TEMPLATE),
        "exists": True,
        "panels": panels,
        "scene_panel": (all(m in html for m in (MARKER_SECTION, MARKER_FN, MARKER_CALL))
                        and "renderSceneSystem(d)" in html),
        "refresh_allowlist": REFRESH_PY.is_file() and REFRESH_MARK in _read(REFRESH_PY),
    }


def ensure(dry_run: bool = False) -> dict:
    if not TEMPLATE.is_file():
        print(f"❌ 部署模板不存在: {TEMPLATE}")
        return {"ok": False, "reason": "template_missing"}
    html = _read(TEMPLATE)
    actions: dict[str, dict] = {}
    ok = True
    for name, section_id in MARKER_PANELS.items():
        html, panel_actions = apply_marker_panel(html, name, section_id)
        actions[name] = panel_actions
        if {"anchor_missing", "section_missing", "marker_broken"} & set(panel_actions.values()):
            ok = False
    html, scene_actions = apply_scene_panel(html)
    actions["scene"] = scene_actions
    if "anchor_missing" in scene_actions.values():
        ok = False

    changed = any(v in ("inserted", "replaced", "migrated", "restored", "restored_append")
                  for panel in actions.values() for v in panel.values())
    if changed and not dry_run:
        shutil.copy2(TEMPLATE, DASHBOARD_DIR / (TEMPLATE.name + ".before-panel-sync"))
        tmp = TEMPLATE.with_suffix(".html.tmp")
        tmp.write_text(html, encoding="utf-8")
        tmp.replace(TEMPLATE)
    if not dry_run:
        actions["refresh_allowlist"] = {"action": apply_refresh_allowlist()}
        try:
            import importlib.util
            host_path = Path(__file__).with_name("zhixing_host_sync.py")
            spec = importlib.util.spec_from_file_location("zhixing_host_sync", host_path)
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            host_status = module.status
        except Exception as exc:  # noqa: BLE001 - visibility must fail closed
            actions["host_files"] = {"action": "check_failed", "error": type(exc).__name__}
            ok = False
        else:
            actions["host_files"] = {
                "action": "checked",
                "ok": host_status().get("ok", False),
            }
            if actions["host_files"]["ok"] is False:
                ok = False
    return {"ok": ok, "dry_run": dry_run, "changed": changed, "actions": actions}


def check() -> int:
    info = status()
    if not info.get("exists"):
        print(f"❌ 驾驶舱模板不存在: {info['template']}", file=sys.stderr)
        return 1
    drifted = [n for n, present in info["panels"].items() if not present]
    if not info["scene_panel"]:
        drifted.append("scene")
    if not info["refresh_allowlist"]:
        drifted.append("refresh_allowlist")
    if drifted:
        print(f"⚠️  面板漂移: 缺失 {drifted} — 运行 "
              f"`python3 bin/gac/zhixing-panel-sync.py ensure` 自愈", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")
    ep = sub.add_parser("ensure", help="幂等注入所有面板 + refresh.py 白名单")
    ep.add_argument("--dry-run", action="store_true")
    ep.add_argument("--quiet", action="store_true")
    sub.add_parser("check", help="漂移检测 (缺失 exit 1)")
    sub.add_parser("status", help="注入状态")
    args = parser.parse_args(argv)
    command = args.command or "status"

    if command == "ensure":
        result = ensure(dry_run=getattr(args, "dry_run", False))
        if not getattr(args, "quiet", False):
            print(f"[zhixing-panel-sync] {datetime.now(UTC).isoformat()} "
                  f"changed={result.get('changed')}")
            print(json.dumps(result.get("actions", {}), ensure_ascii=False, indent=1))
        return 0 if result.get("ok") else 1
    if command == "check":
        return check()
    print(json.dumps(status(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
