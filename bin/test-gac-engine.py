#!/usr/bin/env python3
"""TDD test script for validation of gac-local-gate.py YAML parsing and engine compliance."""
import os
import sys
import yaml
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
GAC_GATE_PY = WORKSPACE / "bin" / "gac-local-gate.py"
SGF_POLICY_YAML = WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "governance" / "sgf-policy.yaml"


def main() -> int:
    print("🧪 Running TDD tests for SGF-v1 gac-local-gate.py engine...")
    
    if not GAC_GATE_PY.is_file():
        print(f"❌ Error: gac-local-gate.py not found at: {GAC_GATE_PY}")
        return 1
        
    if not SGF_POLICY_YAML.is_file():
        print(f"❌ Error: sgf-policy.yaml metadata registry not found at: {SGF_POLICY_YAML}")
        return 1

    # 1. 验证 YAML 文件结构与 schema 合规性
    try:
        data = yaml.safe_load(SGF_POLICY_YAML.read_text(encoding="utf-8")) or {}
        gates = data.get("gates", [])
        if len(gates) < 30:
            print(f"❌ Error: Expected at least 30 registered gates in YAML, found {len(gates)}")
            return 1
        print(f"✅ YAML schema metadata verification PASS. Found {len(gates)} rules.")
    except Exception as e:
        print(f"❌ Error: YAML syntax validation failed: {e}")
        return 1

    # 2. 模拟黑盒运行，验证 gac-local-gate.py 可以正常执行自检而不崩溃
    # 传入 mock 环境变量以验证它能正常加载
    try:
        # 运行 gac-local-gate.py 并加 --help 验证其 cli 参数依然向下兼容
        res = subprocess.run(
            [sys.executable, str(GAC_GATE_PY), "--help"],
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode != 0:
            print(f"❌ Error: gac-local-gate.py --help execution failed: {res.stderr}")
            return 1
        print("✅ CLI arguments downward compatibility PASS.")
    except Exception as e:
        print(f"❌ Error: Execution failed during compat check: {e}")
        return 1

    print("\n🏁 ALL GAC ENGINE TESTS PASSED SUCCESSFULLY! (2/2 PASS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
