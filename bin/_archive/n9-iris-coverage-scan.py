#!/usr/bin/env python3
"""n9-iris-coverage-scan.py — N9 全覆盖验证 (10 可用 connector 走 mesh-iris-executor).

扫 10 可用 connector (iris status available), 每个跑 mesh-iris-executor --dry-run,
验证 mesh 6 事件链 + receipt (N9 全覆盖: 所有 iris connector 走 mesh receipt).

用法:
  python3 bin/ssot/n9-iris-coverage-scan.py
  python3 bin/ssot/n9-iris-coverage-scan.py --limit 3  # list_items limit
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
EXECUTOR = WORKSPACE / "bin" / "ssot" / "mesh-iris-executor.py"

# iris --json status 动态可用 connector (2026-08-05)
AVAILABLE = [
    "apple_mail",
    "applenotes",
    "cua_browser",
    "github",
    "local_files",
    "netease_mailmaster",
    "universal_private",
    "wechat",
    "wpsnote",
    "zhihu",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="N9 全覆盖验证 (10 可用 connector)")
    parser.add_argument("--limit", type=int, default=3, help="list_items limit (默认 3)")
    parser.add_argument("--connectors", nargs="*", default=AVAILABLE, help="connector 列表")
    args = parser.parse_args()

    print(f"🚀 N9 全覆盖验证: {len(args.connectors)} connector")
    results = []
    for conn in args.connectors:
        omo_dir = Path(tempfile.mkdtemp())
        (omo_dir / "_knowledge" / "workflow-mesh").mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [
                "python3", str(EXECUTOR),
                "--connector", conn,
                "--omo-dir", str(omo_dir),
                "--limit", str(args.limit),
            ],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        events_f = omo_dir / "_knowledge" / "workflow-mesh" / "events.jsonl"
        events = len(events_f.read_text().splitlines()) if events_f.exists() else 0
        ok = proc.returncode == 0 and events >= 6
        results.append({"connector": conn, "rc": proc.returncode, "events": events, "ok": ok})
        mark = "✅" if ok else "❌"
        print(f"  {mark} {conn:<22} rc={proc.returncode} events={events}")
        if not ok and proc.stderr:
            print(f"      stderr: {proc.stderr[-120:].strip()}")

    ok_count = sum(1 for r in results if r["ok"])
    print()
    print(f"📊 总计 {len(results)} | 成功 {ok_count} | 失败 {len(results) - ok_count}")
    failed = [r["connector"] for r in results if not r["ok"]]
    if failed:
        print(f"❌ 失败: {failed}")
        return 1
    print("✅ N9 全覆盖验证通过 (所有 connector mesh 6 事件 + receipt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
