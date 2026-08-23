#!/usr/bin/env python3
"""Archived unwired Scene Daemon prototype.

归档原因: 未接入 CI/Make/cron/LaunchAgent/registry/test，且与权威
``signal-poller → journey-runner → scene-outcome-recorder`` 执行链重复。
重新启用前必须补齐持久去重、准入/审批、清理证明、测试与减法配额。

用法:
    python3 bin/_archive/2026-08-scene-daemon-unwired/scene-daemon.py --status
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENE_DIR = REPO / "docs" / "scene-cards"
SIGNAL_SOURCES = REPO / ".omo" / "_truth" / "registry" / "signal-sources.yaml"
STATE_FILE = REPO / ".omo" / "state" / "scene-daemon-state.jsonl"


def load_signal_sources() -> list[dict]:
    """加载信号源配置."""
    import yaml
    if not SIGNAL_SOURCES.exists():
        return []
    try:
        data = yaml.safe_load(SIGNAL_SOURCES.read_text()) or []
        if isinstance(data, dict):
            return data.get("sources", [])
        return data if isinstance(data, list) else []
    except Exception:
        return []


def poll_signal(source: dict) -> list[dict]:
    """轮询单个信号源, 返回新信号列表."""
    transport = source.get("transport", "")
    path = source.get("path", "")
    new_signals = []

    if transport == "local_filesystem" and path:
        # 检查本地文件变更
        p = Path(path).expanduser()
        if p.exists():
            try:
                # 简化的文件变更检测 (mtime)
                mtime = p.stat().st_mtime
                last_poll = source.get("_last_poll", 0)
                if mtime > last_poll:
                    new_signals.append({
                        "source_id": source.get("id"),
                        "type": "file_change",
                        "path": str(p),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    source["_last_poll"] = mtime
            except Exception:
                pass

    return new_signals


def match_scene(signal: dict, scenes: list[dict]) -> dict | None:
    """匹配信号到场景."""
    source_id = signal.get("source_id", "")
    for scene in scenes:
        # 通过 scene_binding 匹配
        if scene.get("scene_binding") == source_id:
            return scene
        # 通过 scene_id 匹配
        if scene.get("scene_id") == source_id:
            return scene
    return None


def execute_journey(journey_id: str) -> dict:
    """执行绑定旅程."""
    try:
        sys.path.insert(0, str(REPO / "projects" / "ecos" / "src"))
        from ecos.l1.runtime.journey_runner import JourneyRunner
        runner = JourneyRunner()
        result = runner.execute_journey(journey_id)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def load_scenes() -> list[dict]:
    """加载所有 scene-card."""
    import yaml
    scenes = []
    if not SCENE_DIR.exists():
        return scenes
    for f in sorted(SCENE_DIR.glob("*.yaml")):
        try:
            text = f.read_text()
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    fm = yaml.safe_load(text[3:end]) or {}
                    if isinstance(fm, dict):
                        # 获取 body 中的 scene_id / journey_id
                        body = yaml.safe_load_all(text[end+3:])
                        for doc in body:
                            if isinstance(doc, dict):
                                fm.update({k: v for k, v in doc.items() if k not in fm})
                        scenes.append(fm)
        except Exception:
            continue
    return scenes


def run_once(dry_run: bool = False) -> dict:
    """单次轮询."""
    sources = load_signal_sources()
    scenes = load_scenes()
    results = []

    for source in sources:
        signals = poll_signal(source)
        for signal in signals:
            scene = match_scene(signal, scenes)
            if scene:
                journey_id = scene.get("journey_id", "")
                status = scene.get("status", "shadow")

                if status == "shadow":
                    results.append({
                        "signal": signal.get("source_id"),
                        "scene": scene.get("scene_id"),
                        "action": "skipped_shadow",
                    })
                    continue

                if dry_run:
                    results.append({
                        "signal": signal.get("source_id"),
                        "scene": scene.get("scene_id"),
                        "journey": journey_id,
                        "action": "dry_run",
                    })
                else:
                    exec_result = execute_journey(journey_id)
                    results.append({
                        "signal": signal.get("source_id"),
                        "scene": scene.get("scene_id"),
                        "journey": journey_id,
                        "action": "executed",
                        "result": exec_result,
                    })

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources_polled": len(sources),
        "matches": len(results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Scene Daemon")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--interval", type=int, default=300, help="轮询间隔(秒)")
    args = parser.parse_args()

    if args.status:
        scenes = load_scenes()
        active = [s for s in scenes if s.get("status") in ("pilot", "active")]
        print(json.dumps({
            "total_scenes": len(scenes),
            "active": len(active),
            "scenes": {s.get("scene_id"): s.get("status") for s in scenes},
        }, ensure_ascii=False, indent=2))
        return

    if args.once:
        result = run_once(dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 持续运行模式
    print(f"Scene daemon started, interval={args.interval}s")
    while True:
        result = run_once()
        if result["matches"] > 0:
            print(json.dumps(result, ensure_ascii=False))
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
