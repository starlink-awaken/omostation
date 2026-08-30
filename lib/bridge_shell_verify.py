#!/usr/bin/env python3
"""ADR-0441 原语 3：bridge shell sha 指纹与转发目标周期核验。

对 registry bridge_shells 逐条核验：
1. shell 文件存在，sha256 与登记一致（薄壳被篡改/误改即 fail）
2. 转发目标存在（fail-loud 契约的静态对应物）
任一失败 exit 1（workflow verification 硬门）。
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml

REGISTRY = Path(__file__).resolve().parents[1] / ".omo/_truth/registry/documents-content-plane-migrations.yaml"


def verify(registry_path: Path = REGISTRY, workspace: Path | None = None) -> int:
    workspace = workspace or Path(__file__).resolve().parents[1]
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    shells = data.get("bridge_shells") or []
    if not shells:
        print("bridge-shell-verify: no bridge_shells registered — skip")
        return 0
    # shell 在 Documents（内容面），target 在 Workspace（控制面）——ADR-0441 方向语义
    documents_root = Path(os.environ.get("L4_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
    failed = 0
    for shell in shells:
        shell_path = documents_root / shell["shell"]
        target_path = workspace / shell["target"]
        problems = []
        if not shell_path.is_file():
            problems.append(f"shell missing: {shell['shell']}")
        else:
            digest = hashlib.sha256(shell_path.read_bytes()).hexdigest()
            if digest != shell.get("sha256"):
                problems.append(f"sha mismatch: {digest[:12]}… != registered {str(shell.get('sha256'))[:12]}…")
        if not target_path.is_file():
            problems.append(f"target missing: {shell['target']}")
        if problems:
            failed += 1
            for pr in problems:
                print(f"FAIL {shell['shell']}: {pr}")
        else:
            print(f"OK   {shell['shell']} (sha + target verified)")
    if failed:
        print(f"bridge-shell-verify: {failed} failure(s)")
        return 1
    print("bridge-shell-verify: all bridge shells verified")
    return 0


def main() -> int:
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
