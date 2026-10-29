#!/usr/bin/env python3
"""CR-CI-RUNNER-COST: GitHub-hosted runner 付费 OS 守门 (blocking).

这道门守的是**覆盖增量**，不是账单 —— 判据不随仓的可见性变化：

* 一条 macOS / Windows 腿必须覆盖**默认 OS 腿覆盖不到的东西**
  （例：launchd 仅在 darwin 存在；darwin-arm64 二进制只能在 macOS 编译）。
* 「零增量覆盖」的腿是纯浪费：它增加排队时间、flake 面与维护成本，却不换来
  任何 Linux 腿拿不到的信号。omlxc 删掉自己的 macOS 腿就是这个理由 ——
  该条注释写的是「零增量覆盖 —— 删」，**与费用无关**。

成本是**次要**理由，且只在 private 仓上成立。GitHub 对 public 仓的标准托管
runner 免费且无分钟上限（含 macOS）；private 仓按量计费、单价按 OS 分级
（Linux 1x / Windows 2x / macOS 10x）。本仓组当前**全部是 public 仓**
⇒ 加一条 macOS 腿不花钱，但上面的覆盖判据仍然成立。

⇒ 别因为「public 免费」把这道门当冗余删掉：它拦的不是账单，是零增量的腿。

本检查扫描仓内（含子模块检出）的 workflow，把 macOS / Windows 的
GitHub-hosted runner 用法与**显式允许清单**对拍：

* 未登记 → `error`（阻塞）
* 已登记 → `warn`（留痕，理由必须写进清单）

self-hosted runner 免费，不纳入本检查。

判据出处
--------
覆盖增量判据：见上（不随仓的可见性变化）。
成本口径（次要，仅 private 仓）：GitHub Actions 计费 —— public 免费 / private 按量；
macOS 10x、Windows 2x、Linux 1x。
清单口径：`.omo/_truth/registry/ci-surfaces.yaml` 登记本工具（CR-CI-RUNNER-COST）。

用法
----
    python3 bin/gac/check-runner-cost.py            # 人类可读
    python3 bin/gac/check-runner-cost.py --json     # 机器可读
    python3 bin/gac/check-runner-cost.py --self-test  # 检测器自证（合成违规样本）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW_GLOBS = (".github/workflows/*.yml", ".github/workflows/*.yaml")


def _declared_submodule_paths(repo: Path) -> list[str]:
    """从 .gitmodules 取已声明的子模块路径（排序，确定性）。

    刻意**不用** `projects/**` 通配：子模块内部可能存有嵌套克隆
    （实测 `projects/agora/projects/l4-kernel/...`），那不是本仓的声明表面，
    扫它只会造出与 ALLOWED 对不上的假命中。
    """
    gm = repo / ".gitmodules"
    if not gm.is_file():
        return []
    return sorted(
        {
            m.group(1).rstrip("/")
            for m in re.finditer(r"^\s*path\s*=\s*(\S+)", gm.read_text(encoding="utf-8"), re.M)
        }
    )


def _workflow_globs(repo: Path) -> list[str]:
    globs = list(WORKFLOW_GLOBS)
    for sub in _declared_submodule_paths(repo):
        globs.append(f"{sub}/.github/workflows/*.yml")
        globs.append(f"{sub}/.github/workflows/*.yaml")
    return globs

# 只关心 GitHub-hosted 的付费 OS。self-hosted 免费，不拦。
PAID_OS = ("macos", "windows")

# 显式允许清单：(workflow 相对路径, job id) -> 理由。
# 新增条目必须写理由（为什么这条 macOS/Windows 腿不可省）。
ALLOWED: dict[tuple[str, str], str] = {
    ("projects/l4-kernel/.github/workflows/ci.yml", "test"):
        "test_check_process(launchd) 仅 darwin 运行（已加 skipif）—— Linux 腿验证可移植性，macOS 腿保住 launchd 覆盖",
    ("projects/knowledge/gbrain/.github/workflows/release.yml", "build"):
        "bun-darwin-arm64 二进制必须在 macOS runner 上编译，无 Linux 替代",
}


def _os_labels(value) -> set[str]:
    """把 runs-on 归一成小写 label 集合（str / list / dict 三种形状）。"""
    if value is None:
        return set()
    if isinstance(value, str):
        return {value.strip().lower()}
    if isinstance(value, list):
        return {str(v).strip().lower() for v in value}
    if isinstance(value, dict):
        # runs-on: { group: x, labels: [a, b] }
        labels = value.get("labels") or []
        if isinstance(labels, str):
            labels = [labels]
        return {str(v).strip().lower() for v in labels}
    return set()


def _matrix_os(job: dict) -> set[str]:
    """从 strategy.matrix 取 os 轴（含 include 展开）。"""
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    found: set[str] = set()
    os_axis = matrix.get("os")
    if isinstance(os_axis, list):
        found |= {str(v).strip().lower() for v in os_axis}
    elif isinstance(os_axis, str):
        found.add(os_axis.strip().lower())
    for inc in matrix.get("include") or []:
        if isinstance(inc, dict) and inc.get("os"):
            found.add(str(inc["os"]).strip().lower())
    return found


def _job_os(job: dict) -> set[str]:
    """一个 job 实际会落到的 OS label 集合。"""
    runs_on = job.get("runs-on")
    labels = _os_labels(runs_on)
    # runs-on: ${{ matrix.os }} 时真实 OS 来自矩阵
    if any("matrix" in lbl or "inputs" in lbl for lbl in labels):
        labels |= _matrix_os(job)
    return labels


def _is_self_hosted(labels: set[str]) -> bool:
    return any("self-hosted" in lbl for lbl in labels)


def _paid_os(labels: set[str]) -> set[str]:
    return {lbl for lbl in labels if any(lbl.startswith(p) or f"-{p}" in lbl for p in PAID_OS)}


def discover_workflows(repo: Path) -> list[Path]:
    """根仓 + 子模块（若已检出）的 workflow 文件，按相对路径排序。"""
    found: set[Path] = set()
    for pattern in _workflow_globs(repo):
        for p in repo.glob(pattern):
            if p.is_file():
                found.add(p)
    return sorted(found, key=lambda p: str(p.relative_to(repo)))


def scan(repo: Path) -> dict:
    """扫描并返回 {findings, workflows, scanned}."""
    import yaml

    findings: list[dict] = []
    workflows = 0

    for wf in discover_workflows(repo):
        rel = str(wf.relative_to(repo))
        try:
            doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            # 不把「坏了」折叠成「空」：解析失败本身是一条 finding
            findings.append({
                "severity": "error",
                "workflow": rel,
                "job": "-",
                "os": "-",
                "reason": f"workflow YAML 解析失败: {exc}",
            })
            continue
        if not isinstance(doc, dict):
            continue
        workflows += 1
        jobs = doc.get("jobs") or {}
        if not isinstance(jobs, dict):
            continue
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            labels = _job_os(job)
            if _is_self_hosted(labels):
                continue
            paid = _paid_os(labels)
            if not paid:
                continue
            key = (rel, str(job_id))
            if key in ALLOWED:
                findings.append({
                    "severity": "warn",
                    "workflow": rel,
                    "job": str(job_id),
                    "os": sorted(paid),
                    "reason": ALLOWED[key],
                })
            else:
                findings.append({
                    "severity": "error",
                    "workflow": rel,
                    "job": str(job_id),
                    "os": sorted(paid),
                    "reason": "未登记的付费 OS runner —— 若确需保留，请在 "
                              "bin/gac/check-runner-cost.py 的 ALLOWED 里加条目并写明理由",
                })

    errors = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warn"]
    return {
        "findings": findings,
        "errors": len(errors),
        "warnings": len(warnings),
        "workflows": workflows,
        "scanned": len(discover_workflows(repo)),
    }


def _render(report: dict) -> str:
    lines = []
    for f in report["findings"]:
        tag = "ERROR" if f["severity"] == "error" else "WARN "
        os_txt = ",".join(f["os"]) if isinstance(f["os"], list) else f["os"]
        lines.append(f"[{tag}] {f['workflow']} :: job {f['job']} :: {os_txt}")
        lines.append(f"         {f['reason']}")
    if not report["findings"]:
        lines.append("OK 未发现付费 OS (macOS/Windows) GitHub-hosted runner")
    lines.append(
        f"扫描 {report['scanned']} 个 workflow（解析 {report['workflows']} 个）: "
        f"error={report['errors']} warn={report['warnings']}"
    )
    return "\n".join(lines)


def self_test() -> int:
    """检测器自证：合成违规样本必须被命中，合成合规样本必须放行。

    没有这条，"绿" 可能只是检测器压根没命中（AGENTS.md §7「扫源码的门禁必须自证」）。
    """
    import tempfile

    import yaml

    cases = [
        # (name, workflow yaml, expect_paid)
        ("plain-macos", "jobs:\n  a:\n    runs-on: macos-latest\n    steps: []\n", True),
        ("plain-windows", "jobs:\n  a:\n    runs-on: windows-latest\n    steps: []\n", True),
        ("matrix-macos", (
            "jobs:\n  a:\n    runs-on: ${{ matrix.os }}\n"
            "    strategy:\n      matrix:\n        os: [ubuntu-latest, macos-latest]\n"
        ), True),
        ("matrix-include-macos", (
            "jobs:\n  a:\n    runs-on: ${{ matrix.os }}\n"
            "    strategy:\n      matrix:\n"
            "        include:\n          - os: macos-latest\n            node: 20\n"
        ), True),
        ("self-hosted-macos", "jobs:\n  a:\n    runs-on: [self-hosted, macos]\n    steps: []\n", False),
        ("linux-only", "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps: []\n", False),
        ("broken-yaml", "jobs:\n  a:\n   runs-on: macos-latest\n  bad: [\n", None),
    ]

    failures = []
    for name, text, expect in cases:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wf_dir = root / ".github" / "workflows"
            wf_dir.mkdir(parents=True)
            (wf_dir / f"{name}.yml").write_text(text, encoding="utf-8")
            report = scan(root)
            got = bool(report["findings"])
            if expect is None:
                # 坏 YAML 必须被报成 error，而不是静默跳过
                ok = report["errors"] >= 1
                detail = f"errors={report['errors']}"
            else:
                ok = got is expect
                detail = f"paid_detected={got}"
            status = "ok" if ok else "FAIL"
            print(f"  [{status}] {name}: expect={expect} {detail}")
            if not ok:
                failures.append(name)

    # 嵌套克隆 (子模块内存放的 nested checkout) 不是本仓声明表面 —— 必须跳过;
    # 而 .gitmodules 声明的子模块表面必须被扫到。
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".gitmodules").write_text(
            '[submodule "a"]\n\tpath = projects/a\n\turl = https://example.invalid/a.git\n',
            encoding="utf-8",
        )
        nested = root / "projects" / "a" / "projects" / "b" / ".github" / "workflows"
        nested.mkdir(parents=True)
        (nested / "ci.yml").write_text(
            "jobs:\n  t:\n    runs-on: macos-latest\n    steps: []\n", encoding="utf-8"
        )
        got = scan(root)["findings"]
        ok = not got
        print(f"  [{'ok' if ok else 'FAIL'}] nested-clone-skipped: findings={len(got)}")
        if not ok:
            failures.append("nested-clone-skipped")

        declared = root / "projects" / "a" / ".github" / "workflows"
        declared.mkdir(parents=True)
        (declared / "ci.yml").write_text(
            "jobs:\n  t:\n    runs-on: macos-latest\n    steps: []\n", encoding="utf-8"
        )
        got2 = scan(root)["findings"]
        ok2 = len(got2) == 1 and got2[0]["workflow"].startswith("projects/a/")
        print(f"  [{'ok' if ok2 else 'FAIL'}] declared-submodule-scanned: {got2}")
        if not ok2:
            failures.append("declared-submodule-scanned")

    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        return 1
    print("SELF-TEST PASSED")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="GitHub-hosted runner 成本守门")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--self-test", action="store_true", help="检测器自证")
    ap.add_argument("--root", default=None, help="仓库根（默认按脚本位置解析）")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    repo = Path(args.root) if args.root else REPO
    report = scan(repo)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_render(report))

    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
