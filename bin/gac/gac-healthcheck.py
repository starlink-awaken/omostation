#!/usr/bin/env python3
"""GaC 治理即代码 — 体系健康检查 (ADR-0106, 元治理递归自检).

端到端验证 GaC 体系落地 + 产生效果 (不只文件存在, 验证机制真工作):

  - 11 核心文件落地检查
  - 机制 2/5/6 (gac-validate 跑通 + 0 error)
  - 机制 4 (gac-drift 跑通 + drift 数)
  - 机制 7 (GacRule M2 可解析)
  - --json 数据源有效 (阶段 4 前置)
  - ADR 引用一致 (无 0104 残留)
  - 注册表规则数 + dimension/layer 覆盖

用法:
  python3 bin/gac/gac-healthcheck.py          # 健康检查, exit 0=全绿, 1=有红
  python3 bin/gac/gac-healthcheck.py --json   # JSON 输出 (cron/仪表盘用)

CI 可移植: Path(__file__).resolve().parents[2]. 对标 gac-validate/gac-drift (bin/+--gate 模式).
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# Core GaC files (relative to WORKSPACE)
CORE_FILES = {
    "north_star": ".omo/_knowledge/gac/NORTH-STAR.md",
    "roadmap": ".omo/_knowledge/gac/roadmap-v1.md",
    "stage34_design": ".omo/_knowledge/gac/stage3-4-design.md",
    "adr": ".omo/_knowledge/decisions/0106-gac-governance-as-code.md",
    "registry": ".omo/_truth/registry/governance-checks.yaml",
    "validate": "bin/gac/gac-validate.py",
    "drift": "bin/gac/gac-drift.py",
    "ci_gate": ".github/workflows/gac-gate.yml",
    # 2026-11-15: opc-closeout-crontab 已于 2026-08-22「登记退役」并归档到
    # .omo/cron/_archived-20260822-opc-closeout-crontab，旧路径不再要求存在。
    "agents_md": "AGENTS.md",
    "m2_type": "projects/ecos/src/ecos/ssot/mof/m2/gac_rule.yaml",
    "stage1_design": ".omo/_knowledge/gac/stage1-hook-design.md",
    "hook": "bin/gac/gac-hook-pre-edit.py",
    "dashboard": "bin/gac/governance-dashboard.py",
    "mof_validate": "bin/gac/gac-mof-validate.py",
    "doc_ssot_lint": "bin/ssot/doc-ssot-lint.py",
    "hygiene": "bin/gac/gac-hygiene-check.py",
    "gen_registry": "bin/mof/gen-project-registry.py",
    # 2026-11-15: gac-ingest-legacy.py 已由 #1839 归档到 bin/_archive/migrations/,
    # 旧路径不再要求存在(见债条目 GAC-INGEST-LEGACY-REFS-NOT-FOLLOWED)。
    "bootstrap": "bin/gac/gac-bootstrap.py",
    "executor": "bin/gac/gac-executor.py",
    "local_gate": "bin/gac/gac-local-gate.py",
    "doc_link_check": "bin/ssot/doc-link-check.py",
    "doc_snapshot_check": "bin/ssot/doc-governance-check.py",
    "change_lane_check": "bin/change-lane-check.py",
    "submodule_reachability": "bin/ssot/submodule-reachability-gate.py",
    "submodule_transaction": "bin/ssot/submodule-pointer-transaction.sh",
}


def input_absent(rel: str) -> bool:
    """该路径的缺席属**输入没备齐**，不是缺陷。

    两种：落在未检出的子模块里（干净检出按构造没有），或指向已归档的旧路径。
    判据与 gac-executor 的 \`_under_unchecked_submodule\` 同口径 —— 两处都要能
    把「读不到」和「坏了」分开，否则恒假警报会训练读者忽略整份报告。
    """
    parts = Path(rel).parts
    if len(parts) >= 2 and parts[0] == "projects":
        return not (WORKSPACE / "projects" / parts[1] / ".git").exists()
    return rel.startswith("bin/_archive/")


def check_files() -> tuple[list[str], list[str]]:
    """核心文件落地检查. 返回 (ok_names, missing_paths)."""
    ok, missing = [], []
    for name, rel in CORE_FILES.items():
        if (WORKSPACE / rel).exists():
            ok.append(name)
        else:
            missing.append(rel)
    return ok, missing


def run_tool(script: str, args: list[str]) -> tuple[int, str]:
    """跑 bin/ 脚本, 返回 (exit_code, stdout)。脚本文件缺失时返回 (127, "")。"""
    path = WORKSPACE / script
    if not path.exists():
        return 127, ""
    result = subprocess.run(
        [sys.executable, str(path), *args],
        capture_output=True,
        text=True,
        cwd=WORKSPACE,
    )
    return result.returncode, result.stdout


def parse_json_output(out: str) -> tuple[dict | None, str | None]:
    """解析 `--json` 输出。

    解析失败返回 `(None, 原因)` 而不是 `({}, None)` —— 后者会让调用方把
    「工具没跑起来 / 输出不是 JSON」读成「跑起来且什么都没发现」。
    """
    if not out or not out.strip():
        return None, "empty output"
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        return None, f"non-JSON output: {exc}"
    return (data if isinstance(data, dict) else None), None


def load_rules() -> list[dict]:
    """加载 governance-checks.yaml::gac.rules (多文档 strip frontmatter)."""
    import yaml

    reg = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
    docs = [d for d in yaml.safe_load_all(reg.read_text(encoding="utf-8")) if d]
    if not docs:
        return []
    return docs[-1].get("gac", {}).get("rules", [])


def check_adr_consistency() -> int:
    """ADR 引用一致 (无 0104 残留). 返回残留数."""
    import subprocess

    result = subprocess.run(
        ["rg", "-c", "ADR-0104"]
        + [
            str(WORKSPACE / p)
            for p in [
                ".omo/_knowledge/gac",
                ".omo/_truth/registry/governance-checks.yaml",
                "AGENTS.md",
            ]
        ]
        + [
            str(WORKSPACE / "bin/gac/gac-validate.py"),
            str(WORKSPACE / "bin/gac/gac-drift.py"),
        ],
        capture_output=True,
        text=True,
    )
    # rg -c 每文件一行 count; 无匹配 exit 1
    if result.returncode == 1:
        return 0  # 无残留
    return len(result.stdout.strip().splitlines()) if result.stdout.strip() else 0


def check_m2_type() -> dict:
    """机制 7: GacRule M2 可解析. 返回 {ok, fields, states, mechanisms}."""
    import yaml

    m2_rel = "projects/ecos/src/ecos/ssot/mof/m2/gac_rule.yaml"
    m2 = WORKSPACE / m2_rel
    if not m2.exists():
        return {
            "ok": False,
            "error": "m2/gac_rule.yaml 缺",
            "unavailable": input_absent(m2_rel),
        }
    docs = [d for d in yaml.safe_load_all(m2.read_text(encoding="utf-8")) if d]
    if not docs:
        return {"ok": False, "error": "m2 空文档"}
    g = docs[-1].get("GacRule", {})
    # 机制7深化: gac-mof-validate drift 检测 (规则 vs M2 type, 不只结构可读)
    mv_code, _ = run_tool("bin/gac/gac-mof-validate.py", [])
    return {
        "ok": mv_code == 0,  # M2 drift 检测 (gac-mof-validate 0 drift 才 ok)
        "fields": len(g.get("fields", {})),
        "states": len(g.get("stateMachine", {})),
        "mechanisms": len(g.get("mechanisms", [])),
        "drift_check": "PASS" if mv_code == 0 else "FAIL",
    }


def probe_legacy_drift(script: str = "bin/gac/gac-ingest-legacy.py") -> dict:
    """legacy-drift 项的读数。

    2026-11-14: 该脚本已被 #1839 归档到 `bin/_archive/migrations/` 而引用没跟 ——
    于是 `run_tool` 拿不到输出、json={} ⇒ 读数全是 0、判 ❌。**「源=0 indexed=0」
    与「真的没问题」在输出里长得一样**，而真相是「工具根本没跑」。显式区分:
    工具缺失时报 `tool_missing` 且各计数为 `None`，不再伪装成「扫了 0 个」。
    """
    missing = not (WORKSPACE / script).exists()
    code, out = run_tool(script, ["--check", "--json"]) if not missing else (127, "")
    try:
        data = json.loads(out) if out else {}
    except json.JSONDecodeError:
        data = {}
    return {
        "ok": code == 0,
        "tool_missing": missing,
        # 工具已被 #1839 归档而引用没跟：这不是「测出红」，是**这条链已退役、去留待裁**。
        # 算进 healthy 会让总体恒 ❌（债务条目 GAC-INGEST-LEGACY-REFS-NOT-FOLLOWED 自己写着
        # 「健康检查的总体结论因此长期带红，而这条红传递的信息是 0」）。
        "retired": missing,
        "legacy_count": None if missing else data.get("legacy_count", 0),
        "indexed_count": None if missing else data.get("indexed_count", 0),
        "missing": None if missing else len(data.get("missing", [])),
        "ghost": None if missing else len(data.get("ghost", [])),
    }


def probe_m1_instance_drift(script: str = "bin/gac/gac-m1-sync.py") -> dict:
    """M1 实例 drift 项的读数。

    2026-11-15: 原 `ok = m1_drift == 0` **不看退出码**，于是工具没跑起来时
    diff 为空 ⇒ drift=0 ⇒ 报 ✅ 全 0。实测缺子模块的检出里 `gac-m1-sync`
    输出的是**人类可读报错（非 JSON）** ⇒ 读成 `✅ registry=0 M1=0`，
    而同一份检出在子模块齐全时是 `❌ registry=86 M1=136` ——
    **同一条检查、相反结论**。现在要求「退出码 0 且输出是 JSON 且 drift=0」才算 ✅。
    """
    code, out = run_tool(script, ["--tracked", "--json"])
    data, error = parse_json_output(out)
    diff = data.get("diff", {}) if data else {}
    drift = (
        len(diff.get("missing_in_m1", [])) + len(diff.get("orphan_in_m1", [])) + len(diff.get("stale", []))
    )
    return {
        "ok": code == 0 and error is None and drift == 0,
        # 工具没跑起来（缺子模块时它打人类可读报错）⇒ **读数不可用**，不是测出红。
        "unavailable": code != 0 or error is not None,
        "tool_error": error,
        "registry_rules": data.get("registry_rules", 0) if data else None,
        "m1_instances": data.get("m1_instances", 0) if data else None,
        "missing_in_m1": len(diff.get("missing_in_m1", [])),
        "orphan_in_m1": len(diff.get("orphan_in_m1", [])),
        "stale": len(diff.get("stale", [])),
    }


def healthcheck() -> dict:
    """主健康检查. 返回报告 dict."""
    report: dict = {"timestamp": subprocess.check_output(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]).decode().strip()}

    # 1. 核心文件
    ok_files, missing = check_files()
    missing_unavailable = [rel for rel in missing if input_absent(rel)]
    report["files"] = {
        "ok": len(ok_files),
        "total": len(CORE_FILES),
        "missing": missing,
        # 全部缺席都属「输入没备齐」⇒ 本项读数不可用，不算核心文件缺失。
        "unavailable": bool(missing) and len(missing_unavailable) == len(missing),
        "missing_unavailable": missing_unavailable,
    }

    # 2. gac-validate (机制 2/5/6)
    val_code, val_out = run_tool("bin/gac/gac-validate.py", ["--json"])
    try:
        val_json = json.loads(val_out) if val_out else {}
    except json.JSONDecodeError:
        val_json = {}
    report["validate"] = {
        "ok": val_code == 0,
        "rules": val_json.get("rules", 0),
        "errors": len(val_json.get("errors", [])),
        "warnings": len(val_json.get("warnings", [])),
    }

    # 3. gac-drift (机制 4)
    drift_code, drift_out = run_tool("bin/gac/gac-drift.py", ["--json"])
    try:
        drift_json = json.loads(drift_out) if drift_out else {}
    except json.JSONDecodeError:
        drift_json = {}
    report["drift"] = {
        "ok": drift_code == 0,
        "rules": drift_json.get("rules", 0),
        "drift_count": drift_json.get("drift_count", 0),
    }

    # 4. 注册表 dimension/layer/source_type 覆盖
    rules = load_rules()
    dims = Counter(r.get("dimension", "?") for r in rules)
    layers = Counter(r.get("layer", "?") for r in rules)
    source_types = Counter(r.get("source_type", "native") for r in rules)
    report["coverage"] = {
        "rules": len(rules),
        "dimension": dict(dims),
        "dimension_complete": set(dims) >= {"X1", "X2", "X3", "X4"},
        "layer": dict(layers),
        "source_type": dict(source_types),  # native=GaC SSOT, indexed=收敛的原真策略
    }

    # 5. ADR 引用一致
    report["adr_residue_0104"] = check_adr_consistency()

    # 6. 机制 7 GacRule M2
    report["m2_type"] = check_m2_type()

    # 7. doc-ssot (CR-X4-DOC-SSOT: 文档 SSOT 正交契约)
    ds_code, ds_out = run_tool("bin/ssot/doc-ssot-lint.py", ["--json"])
    try:
        ds_json = json.loads(ds_out) if ds_out else {}
    except json.JSONDecodeError:
        ds_json = {}
    report["doc_ssot"] = {
        "ok": ds_code == 0,
        "conflicts": ds_json.get("conflicts", 0),
        "files_scanned": ds_json.get("files_scanned", 0),
    }

    # 7b. doc snapshot hardcoding guard (entry docs must point to SSOT)
    snap_code, _snap_out = run_tool("bin/ssot/doc-governance-check.py", [])
    report["doc_snapshots"] = {
        "ok": snap_code == 0,
    }

    # 7c. local Markdown link contract for agent-facing docs
    link_code, link_out = run_tool("bin/ssot/doc-link-check.py", ["--json"])
    try:
        link_json = json.loads(link_out) if link_out else {}
    except json.JSONDecodeError:
        link_json = {}
    report["doc_links"] = {
        "ok": link_code == 0,
        "broken_links": link_json.get("broken_links", 0),
        "files_scanned": link_json.get("files_scanned", 0),
    }

    # 7d. root gitlink reachability (no network fetch; pre-push/CI run with --fetch)
    reach_code, reach_out = run_tool("bin/ssot/submodule-reachability-gate.py", ["--source", "head", "--json"])
    try:
        reach_json = json.loads(reach_out) if reach_out else {}
    except json.JSONDecodeError:
        reach_json = {}
    report["submodule_reachability"] = {
        "ok": reach_code == 0,
        "checked": reach_json.get("checked", 0),
        "failures": len(reach_json.get("failures", [])),
    }

    # 8. hygiene (CR-HYG-01/02: 工作区卫生)
    hy_code, hy_out = run_tool("bin/gac/gac-hygiene-check.py", ["--json"])
    try:
        hy_json = json.loads(hy_out) if hy_out else {}
    except json.JSONDecodeError:
        hy_json = {}
    report["hygiene"] = {
        "ok": hy_code == 0,
        "issues": hy_json.get("issues", 0),
        "zero_byte": hy_json.get("zero_byte_count", 0),
        "case_conflicts": hy_json.get("case_conflict_count", 0),
    }

    # 9. registry drift (代码→registry SSOT 链闭环; doc-ssot 第4步)
    gr_code, gr_out = run_tool("bin/mof/gen-project-registry.py", ["--json"])
    try:
        gr_json = json.loads(gr_out) if gr_out else {}
    except json.JSONDecodeError:
        gr_json = {}
    report["registry_drift"] = {
        "ok": gr_code == 0,
        "drift_count": gr_json.get("drift_count", 0),
        "projects_scanned": gr_json.get("projects_scanned", 0),
    }

    # 10. legacy drift (动态收敛: X1-X4+L0 源 vs GaC indexed, 多套并行检测)
    report["legacy_drift"] = probe_legacy_drift()

    # 11. GaC 自举递归 (元治理核心: GaC 治 GaC 自身, CR-X2-GAC-BOOTSTRAP)
    bs_code, bs_out = run_tool("bin/gac/gac-bootstrap.py", ["--json"])
    try:
        bs_json = json.loads(bs_out) if bs_out else {}
    except json.JSONDecodeError:
        bs_json = {}
    report["bootstrap"] = {
        "ok": bs_code == 0,
        "tools_alive": bs_json.get("tools", {}).get("alive", 0),
        "tools_total": bs_json.get("tools", {}).get("total", 0),
        "indexed_missing": bs_json.get("indexed_integrity", {}).get("missing_count", 0),
        "exec_issues": bs_json.get("exec_effective", {}).get("issues_count", 0),
        "schema_issues": bs_json.get("schema_self", {}).get("issues_count", 0),
    }

    # 12. GaC executor 注册 drift (机制3/4深化: 声明 vs 实际存在, CR-X2-GAC-EXEC-DRIFT)
    ex_code, ex_out = run_tool("bin/gac/gac-executor.py", ["--json"])
    try:
        ex_json = json.loads(ex_out) if ex_out else {}
    except json.JSONDecodeError:
        ex_json = {}
    report["executor_drift"] = {
        "ok": ex_code == 0,
        "declared_executors": len(ex_json.get("declared_executors", [])),
        "missing_executors": len(ex_json.get("missing_executors", [])),
        "rules_with_missing": ex_json.get("rules_with_missing_executor", 0),
    }

    # 13. GaC M1 实例 drift (机制7深化: registry↔M1 双向校验, Phase 4B)
    # ADR-0376 G9: --tracked — 基于 git HEAD 提交态而非 working tree,
    # 并发 agent 的 untracked M1 / 分支切换噪声不应误报 health red.
    report["m1_instance_drift"] = probe_m1_instance_drift()

    # 14. CI 平面可观测性 (ADR-0379 E-3): ci-surfaces SSOT vs 实际接线
    # unregistered/gate-parity/double-trigger = error; orphan/overlap = warn.
    ci_code, ci_out = run_tool("bin/gac/check-ci-surfaces.py", ["--json"])
    try:
        ci_json = json.loads(ci_out) if ci_out else {}
    except json.JSONDecodeError:
        ci_json = {}
    report["ci_plane"] = {
        "ok": ci_code == 0,
        "surfaces": ci_json.get("surfaces", 0),
        "wired_tools": ci_json.get("wired_tools", 0),
        "error_count": ci_json.get("error_count", 0),
        "warn_count": ci_json.get("warn_count", 0),
        "errors": ci_json.get("errors", []),
        "warnings": ci_json.get("warnings", []),
    }

    # 14. SSOT 使用率 (ADR-0385 B2): 检查 _truth/registry/ 下 SSOT 文件新鲜度
    ssot_code, ssot_out = run_tool("bin/ssot/ssot-usage.py", ["--json"])
    try:
        ssot_json = json.loads(ssot_out) if ssot_out else {}
    except json.JSONDecodeError:
        ssot_json = {}
    report["ssot_usage"] = {
        "ok": ssot_code == 0,
        "stale_count": ssot_json.get("stale_count", 0),
        "files_count": len(ssot_json.get("files", [])),
    }

    # 总体健康 (含 executor drift + M1 instance drift: 声明的 executor 必须实际存在)
    red, not_measured = classify_health(report)
    report["red_items"] = red
    report["not_measured"] = not_measured
    report["healthy"] = not red
    return report


def _is_red(report: dict, name: str) -> bool:
    """可测项里的真红：该件未被标为未判定，且读数确实是坏。

    \`core_files\` 的 \`ok\` 是**数量**（存在的文件数）而不是布尔 —— 用 \`is False\`
    永远不成立；它的「坏」定义是 missing 非空。
    """
    item = report.get(name) or {}
    if name == "core_files":
        return bool(item.get("missing"))
    return item.get("ok") is False


def classify_health(report: dict) -> tuple[list[str], list[str]]:
    """把各探针的读数分成 (red_items, not_measured)。

    **「可测的红」才算红。** 三态分开是这份聚合唯一重要的事：

    - ``red_items``   —— 读数可用且确实是坏（真问题）；
    - ``not_measured`` —— 读数不可用，原因有二：
        * ``retired`` 链路已退役待裁（工具被归档而引用没跟）；
        * ``unavailable`` / ``unchecked_only`` 工具没跑起来（缺子模块时它打人类可读报错）。

    把后两者折进 ``healthy`` 会让「总体健康」在任何干净检出上恒 ❌，而那条红
    传递的信息量是 0 —— 读者会因此学会忽略整份报告（债务条目
    GAC-INGEST-LEGACY-REFS-NOT-FOLLOWED 自己就写着这句话）。同口径见
    gac-local-gate 的 preflight / not_measured、gac-executor 的 executors_not_checked。
    """
    # 「可测的红」才算红；「没测成」与「已退役待裁」单列, 不混进总体。
    # 与 gac-local-gate 的 not_measured / preflight、以及 gac-executor 自身的
    # executors_not_checked 同口径: 判据不能被输入缺席架空, 但也不能把「读不到」
    # 写成「坏了」—— 后者会训练读者忽略整份报告。
    _measured = {
        "validate": lambda: report["validate"]["ok"],
        "drift": lambda: report["drift"]["ok"],
        "adr_residue_0104": lambda: report["adr_residue_0104"] == 0,
        "coverage": lambda: bool(report["coverage"]["dimension_complete"]),
        "doc_ssot": lambda: report["doc_ssot"]["ok"],
        "doc_snapshots": lambda: report["doc_snapshots"]["ok"],
        "doc_links": lambda: report["doc_links"]["ok"],
        "submodule_reachability": lambda: report["submodule_reachability"]["ok"],
        "hygiene": lambda: report["hygiene"]["ok"],
        "registry_drift": lambda: report["registry_drift"]["ok"],
        "bootstrap": lambda: report["bootstrap"]["ok"],
        "ci_plane": lambda: report["ci_plane"]["ok"],
        "ssot_usage": lambda: report["ssot_usage"]["ok"],
    }
    _conditional = {
        "legacy_drift": lambda: report["legacy_drift"].get("retired"),
        "m1_instance_drift": lambda: report["m1_instance_drift"].get("unavailable"),
        "executor_drift": lambda: report["executor_drift"].get("unchecked_only"),
        "core_files": lambda: report["files"].get("unavailable"),
        "m2_type": lambda: report["m2_type"].get("unavailable"),
    }

    red_items = [name for name, probe in _measured.items() if not probe()]
    for name, flag in _conditional.items():
        if not flag() and _is_red(report, name):
            red_items.append(name)
    return sorted(set(red_items)), sorted(
        name for name, flag in _conditional.items() if flag()
    )


def print_report(report: dict) -> None:
    """人读报告."""
    print(f"═══ GaC 体系健康检查 ({report['timestamp']}) ═══")
    print()

    # 文件
    f = report["files"]
    status = "✅" if not f["missing"] else "❌"
    print(f"▶ 核心文件: {status} {f['ok']}/{f['total']}" + (f" (缺: {f['missing']})" if f["missing"] else ""))

    # validate
    v = report["validate"]
    status = "✅" if v["ok"] else "❌"
    print(f"▶ gac-validate (机制2/5/6): {status} rules={v['rules']} errors={v['errors']} warnings={v['warnings']}")

    # drift
    d = report["drift"]
    status = "✅" if d["drift_count"] == 0 else "⚠️"
    print(
        f"▶ gac-drift (机制4): {status} drift_count={d['drift_count']}"
        + (" (闭环归零)" if d["drift_count"] == 0 else "")
    )

    # 覆盖
    c = report["coverage"]
    dim_status = "✅" if c["dimension_complete"] else "❌"
    print(f"▶ 覆盖: {c['rules']} 规则 | dimension {dim_status} {c['dimension']} | layer {c['layer']}")

    # ADR
    adr_status = "✅" if report["adr_residue_0104"] == 0 else "❌"
    print(f"▶ ADR 引用一致: {adr_status} (0104 残留={report['adr_residue_0104']})")

    # M2
    m = report["m2_type"]
    if m.get("ok"):
        print(
            f"▶ GacRule M2 (机制7): ✅ fields={m['fields']} 状态机={m['states']} 机制={m['mechanisms']} drift={m.get('drift_check', '?')}"
        )
    else:
        print(f"▶ GacRule M2 (机制7): ❌ {m.get('error', 'drift FAIL')}")

    # doc-ssot (CR-X4-DOC-SSOT)
    ds = report["doc_ssot"]
    ds_status = "✅" if ds["ok"] else "❌"
    print(f"▶ doc-ssot (CR-X4-DOC-SSOT): {ds_status} 扫描={ds['files_scanned']} 冲突={ds['conflicts']}")

    snap = report["doc_snapshots"]
    snap_status = "✅" if snap["ok"] else "❌"
    print(f"▶ doc-snapshots (禁止运行时快照): {snap_status}")

    links = report["doc_links"]
    link_status = "✅" if links["ok"] else "❌"
    print(f"▶ doc-links (入口文档链接): {link_status} 扫描={links['files_scanned']} 死链={links['broken_links']}")

    reach = report["submodule_reachability"]
    reach_status = "✅" if reach["ok"] else "❌"
    print(
        f"▶ submodule-reachability (gitlink远端可达): {reach_status} 检查={reach['checked']} 失败={reach['failures']}"
    )

    # hygiene (CR-HYG-01/02)
    h = report["hygiene"]
    h_status = "✅" if h["ok"] else "❌"
    print(f"▶ hygiene (CR-HYG-01/02): {h_status} 0字节={h['zero_byte']} 大小写冲突={h['case_conflicts']}")

    # registry drift (代码→registry SSOT 链)
    gr = report["registry_drift"]
    gr_status = "✅" if gr["ok"] else "❌"
    print(f"▶ registry-drift (代码→SSOT): {gr_status} 扫描={gr['projects_scanned']} drift={gr['drift_count']}")

    # legacy drift (动态收敛: X1-X4+L0 源 vs GaC indexed)
    lg = report["legacy_drift"]
    lg_status = "✅" if lg["ok"] else "❌"
    if lg.get("tool_missing"):
        print(
            f"▶ legacy-drift (收敛同步): {lg_status} 工具缺失: bin/gac/gac-ingest-legacy.py "
            "(已归档至 bin/_archive/migrations/, 引用没跟) —— 本项读数不可用, 不是「扫了 0 个」"
        )
    else:
        print(
            f"▶ legacy-drift (收敛同步): {lg_status} 源={lg['legacy_count']} indexed={lg['indexed_count']} missing={lg['missing']} ghost={lg['ghost']}"
        )

    # GaC 自举递归 (元治理: GaC 治 GaC 自身)
    bs = report["bootstrap"]
    bs_status = "✅" if bs["ok"] else "❌"
    print(
        f"▶ bootstrap (GaC 治 GaC): {bs_status} 工具={bs['tools_alive']}/{bs['tools_total']} indexed缺={bs['indexed_missing']} exec错={bs['exec_issues']} schema错={bs['schema_issues']}"
    )

    # executor 注册 drift (声明 vs 实际存在)
    ex = report["executor_drift"]
    ex_status = "✅" if ex["ok"] else "❌"
    print(
        f"▶ executor-drift (声明vs实际): {ex_status} executor={ex['declared_executors']} missing={ex['missing_executors']} 受影响规则={ex['rules_with_missing']}"
    )

    # M1 实例 drift (机制7深化: registry↔M1 双向校验)
    m1 = report["m1_instance_drift"]
    m1_status = "✅" if m1["ok"] else "❌"
    if m1.get("tool_error"):
        print(f"▶ M1实例drift (机制7): {m1_status} 读数不可用 —— {m1['tool_error']}")
    else:
        print(
            f"▶ M1实例drift (机制7): {m1_status} registry={m1['registry_rules']} M1={m1['m1_instances']} "
            f"缺={m1['missing_in_m1']} 多余={m1['orphan_in_m1']} 过期={m1['stale']}"
        )

    # CI 平面可观测性 (ADR-0379 E-3: ci-surfaces SSOT vs 实际接线)
    ci = report["ci_plane"]
    ci_status = "✅" if ci["ok"] else "❌"
    print(
        f"▶ CI平面 (ADR-0379): {ci_status} surfaces={ci['surfaces']} wired={ci['wired_tools']}/{ci['surfaces']} errors={ci['error_count']} warns={ci['warn_count']}"
    )
    for e in ci["errors"][:5]:
        print(f"    ❌ {e}")
    for w in ci["warnings"][:5]:
        print(f"    ⚠️  {w}")

    # SSOT 使用率 (ADR-0385 B2)
    su = report["ssot_usage"]
    su_status = "✅" if su["ok"] else "❌"
    print(f"▶ SSOT使用率 (ADR-0385): {su_status} files={su['files_count']} stale={su['stale_count']}")

    print()
    red = report.get("red_items") or []
    not_measured = report.get("not_measured") or []
    if red:
        overall = f"❌ 有红 ({len(red)} 项: {', '.join(red)})"
    elif not_measured:
        overall = (
            f"⚠️ 无可测的红, 但有 {len(not_measured)} 项未判定 "
            f"({', '.join(not_measured)}) —— 先备齐输入再读总体"
        )
    else:
        overall = "✅ 全绿 (GaC 体系闭环生效)"
    print(f"═══ 总体: {overall} ═══")


def main() -> int:
    args = sys.argv[1:]
    json_mode = "--json" in args

    report = healthcheck()

    if json_mode:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)

    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
