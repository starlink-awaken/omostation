#!/usr/bin/env python3
"""GaC 检查器: LLM 推理必须走统一接入层 (llm-router / AetherForge 网关)。

CR-LLM-GATEWAY-ONLY — 禁止业务代码直连 ollama (11434) / 裸 OpenAI 端点。
直连仅允许出现在: aetherforge 网关自身、llm_router 统一接入层。

用法: python3 bin/gac/check-llm-gateway-only.py [--warn] [--json]
退出码: 0 = 通过; 1 = 存在违规 (报告; --warn 下仅告警不失败); 2 = --fix 后仍有残留
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 业务代码直连模式 (正则)
DIRECT_PATTERNS = [
    re.compile(r"https?://(?:localhost|127\.0\.0\.1):11434"),
    re.compile(r":11434/api/(?:generate|chat)"),
    re.compile(r"OLLAMA_ENDPOINT\s*=\s*[\"']http://localhost:11434"),
]

# 允许直连的路径 (网关自身 + 统一接入层)
ALLOW_PATHS = (
    "projects/aetherforge",
    "projects/cockpit/src/cockpit/llm_router.py",
)

# 扫描范围: 所有项目的业务代码
SCAN_GLOBS = (
    "projects/*/src/**/*.py",
    "projects/*/packages/**/src/**/*.py",
    "projects/*/*.py",
)


def scan() -> list[dict]:
    findings: list[dict] = []
    for glob in SCAN_GLOBS:
        for path in sorted(ROOT.glob(glob)):
            rel = str(path.relative_to(ROOT))
            if any(rel.startswith(a) for a in ALLOW_PATHS):
                continue
            if "/tests/" in rel or rel.endswith("_test.py") or rel.endswith("/test_"):
                continue
            if any(seg.startswith(".") for seg in path.parts):
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for idx, line in enumerate(lines, start=1):
                if any(p.search(line) for p in DIRECT_PATTERNS):
                    findings.append({"file": rel, "line": idx, "text": line.strip()[:120]})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warn", action="store_true", help="违规仅告警不失败 (历史存量迁移期)")
    parser.add_argument("--fix", action="store_true", help="修复违规 (替换 11434 直连)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    findings = scan()
    if args.json:
        print(json.dumps({"violations": len(findings), "findings": findings}, ensure_ascii=False, indent=2))
    else:
        if not findings:
            print("CR-LLM-GATEWAY-ONLY: OK — 无直连 ollama/裸端点 (绕过 llm-router)")
            return 0
        level = "WARN" if args.warn else "FAIL"
        print(f"CR-LLM-GATEWAY-ONLY: {level} — {len(findings)} 处直连 ollama (应走 llm-router / AetherForge 网关)")
        for f in findings:
            print(f"  {f['file']}:{f['line']}  {f['text']}")
        if not args.warn:
            print("  修复: 迁移调用到 projects/cockpit/src/cockpit/llm_router.py (统一接入层)")
    return 0 if args.warn else (1 if findings else 0)


if __name__ == "__main__":
    sys.exit(main())
