#!/usr/bin/env python3
"""织星驾驶舱（:43191）场景面板 — 版本化资产的幂等注入与漂移检测.

问题（2026-09-17 实证）: `~/.local/share/zhixing-dashboard/` **不受版本控制**，
多 agent 并发编辑同一 `template.html` 互相覆盖 —— 本场景面板已被覆盖丢 2 次
（一次因 metrics redesign，一次连带修好的 `ens[n.type]` bug 一起回退）。

解法: 面板代码作为**版本化资产** `bin/panorama/assets/scene-panel.html` 存于仓库，
本脚本幂等注入部署目录；由 cron 每小时巡检自愈（同 fix-remotes 的兜底模式）。

子命令:
    ensure   幂等注入缺失的面板片段（不改动其它内容）
    check    仅检测是否漂移（缺失 → exit 1，供 cron/hook 告警）
    status   报告当前注入状态
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
ASSET = _ROOT / "bin" / "panorama" / "assets" / "scene-panel.html"
DASHBOARD_DIR = Path.home() / ".local/share/zhixing-dashboard"
TEMPLATE = DASHBOARD_DIR / "template.html"

# 注入锚点（不依赖行号）
ANCHOR_NAV = '<a href="#knowledge-memory"'
ANCHOR_SECTION = '<section id="skills-inventory"'
ANCHOR_SCRIPT = "document.addEventListener('DOMContentLoaded'"
ANCHOR_CALL = "window.addEventListener('hashchange'"
ANCHOR_REFRESH = "renderPanorama(d);"

MARKER_SECTION = 'id="scene-system"'
MARKER_FN = "function renderSceneSystem"
# 注意: 必须带分号, 否则会误匹配函数定义 "function renderSceneSystem(D){"
MARKER_CALL = "renderSceneSystem(D);"


def _load_asset() -> dict[str, str]:
    """从资产文件切出 nav / section / script 三段."""
    text = ASSET.read_text(encoding="utf-8")
    nav = re.search(r"<!-- NAV -->\n(.*?)\n", text, re.S)
    sec = re.search(r"<!-- SECTION -->\n(.*?)\n<!-- SCRIPT -->", text, re.S)
    scr = re.search(r"<script>\n(.*?)\n</script>", text, re.S)
    if not (nav and sec and scr):
        raise ValueError(f"资产片段不完整: {ASSET}")
    return {"nav": nav.group(1), "section": sec.group(1), "script": scr.group(1)}


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


def status() -> dict[str, object]:
    if not TEMPLATE.is_file():
        return {"template": str(TEMPLATE), "exists": False}
    html = TEMPLATE.read_text(encoding="utf-8")
    return {
        "template": str(TEMPLATE),
        "exists": True,
        "nav": 'href="#scene-system"' in html,
        "section": MARKER_SECTION in html,
        "script": MARKER_FN in html,
        "call_embedded": MARKER_CALL in html,  # 带分号, 区分函数定义
        "call_live": "renderSceneSystem(d)" in html,
    }


def ensure(dry_run: bool = False) -> dict[str, object]:
    """幂等注入缺失片段; 返回每个片段的动作 (inserted/kept/anchor_missing)."""
    if not TEMPLATE.is_file():
        print(f"❌ 部署模板不存在: {TEMPLATE}")
        return {"ok": False, "reason": "template_missing"}
    parts = _load_asset()
    html = TEMPLATE.read_text(encoding="utf-8")
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
        html, ok = _insert_before(html, ANCHOR_SCRIPT, "<script>\n" + parts["script"] + "\n</script>")
        actions["script"] = "inserted" if ok else "anchor_missing"
    if MARKER_CALL in html:
        actions["call_embedded"] = "kept"
    else:
        html, ok = _insert_after_line(html, ANCHOR_CALL, "renderSceneSystem(D);")
        actions["call_embedded"] = "inserted" if ok else "anchor_missing"
    if "renderSceneSystem(d)" in html:
        actions["call_live"] = "kept"
    else:
        # 实时刷新路径: fetch 成功后一并重渲染场景面板
        pattern = re.compile(r"(\n(\s*)renderPanorama\(d\);)", re.M)
        m = pattern.search(html)
        if m:
            indent = m.group(2)
            html = html[:m.end(1)] + f"\n{indent}renderSceneSystem(d);" + html[m.end(1):]
            actions["call_live"] = "inserted"
        else:
            actions["call_live"] = "anchor_missing"

    changed = any(v == "inserted" for v in actions.values())
    if changed and not dry_run:
        backup = DASHBOARD_DIR / (TEMPLATE.name + ".before-scene-panel-sync")
        shutil.copy2(TEMPLATE, backup)
        tmp = TEMPLATE.with_suffix(".html.tmp")
        tmp.write_text(html, encoding="utf-8")
        tmp.replace(TEMPLATE)
    return {"ok": all(v != "anchor_missing" for v in actions.values()),
            "dry_run": dry_run, "changed": changed, "actions": actions}


def check() -> int:
    info = status()
    if not info.get("exists"):
        print(f"❌ 驾驶舱模板不存在: {info['template']}", file=sys.stderr)
        return 1
    missing = [k for k in ("nav", "section", "script", "call_embedded", "call_live")
               if not info.get(k)]
    if missing:
        print(f"⚠️  场景面板漂移: 缺失 {missing} — 运行 "
              f"`python3 bin/gac/zhixing-panel-sync.py ensure` 自愈", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")
    ep = sub.add_parser("ensure", help="幂等注入缺失片段")
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
                  f"changed={result.get('changed')} {result.get('actions')}")
        return 0 if result.get("ok") else 1
    if command == "check":
        return check()
    import json
    print(json.dumps(status(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
