#!/usr/bin/env python3
"""B.D.S.K. diff static scanner.

This tool reports bounded lexical findings only. It does not run BDSK compute,
prove runtime safety, or authorize a commit, push, merge, or deployment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


class BDSKShadowSandbox:
    """Bounded static scanner for the current Git diff."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root

    def get_diff_text(self) -> str:
        try:
            res = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout or ""
        except Exception:
            return ""

    def simulate(self) -> dict[str, Any]:
        diff_text = self.get_diff_text()
        added_text = "\n".join(
            line[1:]
            for line in diff_text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        findings: list[str] = []

        # ⚡️ Devil 隐性风险硬扫描
        if "SWARM_GIT_DEPTH" not in added_text and "git" in added_text and "shim" in added_text:
            findings.append("⚡️ Devil 警告: 发现疑似 PATH shim 目录内包含 git 调用，但未配置 SWARM_GIT_DEPTH 熔断！")

        if "rm -rf" in added_text or "git reset --hard" in added_text:
            findings.append("⚡️ Devil 高危拦截: 发现破坏性命令 (rm -rf / git reset --hard)，可能造成永久数据丢失！")

        # 🧑‍💻 Builder 结构匹配
        changed_files = [line for line in diff_text.splitlines() if line.startswith("+++ b/")]

        is_clear = len(findings) == 0

        return {
            "status": "STATIC_CLEAR" if is_clear else "STATIC_FINDINGS",
            "proof_state": "static_findings_only",
            "commit_authorized": False,
            "runtime_evaluated": False,
            "changed_files_count": len(changed_files),
            "findings": findings,
            "diff_size_bytes": len(diff_text.encode("utf-8")),
        }


def main() -> int:
    sandbox = BDSKShadowSandbox()
    res = sandbox.simulate()

    print("=========================================================================")
    print(" 🧠 B.D.S.K. Diff 静态扫描")
    print("=========================================================================")
    print(f" 📂 变更文件数: {res['changed_files_count']} | Diff 大小: {res['diff_size_bytes']} bytes")
    print("-------------------------------------------------------------------------")
    print("ℹ️ 本工具只扫描有限文本模式；未运行模型、代码或运行时验证。")

    if res["status"] == "STATIC_CLEAR":
        print("⚡️ 未命中当前已登记的静态模式。未知风险仍保持 unknown。")
        print("=========================================================================")
        print("💡 STATIC_CLEAR：不构成 Commit/Push/Merge 授权。")
        print("=========================================================================")
        return 0
    else:
        print("⚡️ 命中静态风险模式：")
        for f in res["findings"]:
            print(f"   • {f}")
        print("=========================================================================")
        print("💡 STATIC_FINDINGS：需独立验证；本工具仍不授予或撤销提交权限。")
        print("=========================================================================")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
