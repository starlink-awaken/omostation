#!/usr/bin/env python3
"""gac-bootstrap — GaC 自举递归检测 (元治理核心: GaC 治 GaC 自身).

GaC 治理一切, GaC 自己也要被治 (NORTH-STAR 元治理递归). 本工具是 GaC 用自己的
机制检测自身完整性的自举点:

  层1 注册表 drift   → CR-X2-GAC-DRIFT (已有, 本工具不重复)
  层2 schema 自洽    → gac-mof-validate (机制7, M2 type 驱动)
  层3 工具活/死      → bin/gac-*.py ∪ bin/gac/*.py 可解析且有 __main__ (零分母判红)
  层4 source_ref 完整 → 全部**路径型** source_ref 的存在性 (旧判据只看 indexed, 覆盖 6/90)
  层5 执行有效       → executor 真注册检测 (防声明不执行)
  层6 执行平面       → ci-surfaces 声明的执行 vs 四平面实测 (防登记了却没人跑)

层6 的四个平面按**结构**取, 不按文本子串取, 因为"文件里提到"≠"被执行":
  runtime = gac-local-gate.py 运行时 GATES_LIST 的 command (importlib 取, 不是正则扫源码)
  ci      = .github/workflows/*.yml 里 jobs.*.steps[].run 的命令体 (排除注释与 echo 文案)
  hooks   = .githooks/* 里含 python3/bash/run_py/*run_stage 的调用行
  policy  = sgf-policy.yaml 的 command 列表 (经 gac-local-gate.SGF_POLICY_YAML 同源的解析结果)

阻断口径读 CR-X2-GAC-BOOTSTRAP 自己的 `enforcement` 字段, 不在本文件硬编码日期:
  advisory (现状) → 层3 dead / 层4 非 indexed 缺席 / 层6 平面缺席 只点名, 不改变退出码
  blocking        → 上述 gap 计入退出码
层3 **零分母** (glob 落空 = 仪器没接上) 与 层4 **indexed 子集** 缺席始终阻断, 与历史行为一致.

用法:
  python3 bin/gac/gac-bootstrap.py           # 自举检测, 有问题返回 1
  python3 bin/gac/gac-bootstrap.py --json    # JSON 输出 (gac-healthcheck 消费)

退出码: 0 = GaC 自身完整, 1 = 自举发现 gap
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
CI_SURFACES = WORKSPACE / ".omo" / "_truth" / "registry" / "ci-surfaces.yaml"
HOOKS_DIR = WORKSPACE / ".githooks"
# `.githooks/pre-commit` 只有 9 行, 整篇委托给 hook-runner.sh (AGENTS.md §6: 「在那里
# grep 不到任何东西」)。真正的 hook 调用面有 18 处 `run_check` 落在那里, 只扫
# `.githooks/` 会把 hooks 平面读成空集 (2026-11-12 实测: 0 个 .py token)。
HOOK_RUNNER = WORKSPACE / "bin" / "gac" / "hook-runner.sh"
CRON_REGISTRY = WORKSPACE / ".omo" / "cron" / "registry.yaml"
# cron 作业只有 reality 表明「已装机」才算执行面: declared_only / pending
# 是「声明但未被验证装机」, 算进去就是把声明当执行。
CRON_REACHED_REALITY = {"installed", "crontab_installed"}
WORKFLOWS_DIR = WORKSPACE / ".github" / "workflows"
LOCAL_GATE = WORKSPACE / "bin" / "gac" / "gac-local-gate.py"
GAC_TOOLS = sorted(
    p
    for p in set(WORKSPACE.glob("bin/gac-*.py")) | set((WORKSPACE / "bin" / "gac").glob("*.py"))
    if p.name != "__init__.py"  # 包标记不是工具, 没有 __main__ 是天经地义
)
RULE_ID_SELF = "CR-X2-GAC-BOOTSTRAP"

PATH_REF_RE = re.compile(r"^[\w.\-/@]+\.(?:py|sh|ya?ml|md|json|toml)$")
PY_TOKEN_RE = re.compile(r"[\w./$-]+/[\w.-]+\.py")
HOOK_CALL_RE = re.compile(r"\b(?:python3?|bash|run_py|\w*run_stage|run_check)\b")
ROOT_VAR_RE = re.compile(r"^\$?\{?(?:ROOT|WORKSPACE|REPO_ROOT|_ROOT|WORKSPACE_ROOT)\}?/")
# 只声明 manual 的工具不参与平面点名: 没有平面跑它是登记的本意, 不是谎报.
AUTOMATED_TRIGGERS = {"gac_local_gate", "per_pr", "push", "ci_gate", "scheduled", "pr"}


def load_rules() -> list[dict]:
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    return docs[-1].get("gac", {}).get("rules", []) if docs else []


def load_doc_registry() -> dict:
    docs = [d for d in yaml.safe_load_all(REGISTRY.read_text(encoding="utf-8")) if d]
    return docs[-1].get("gac", {}) if docs else {}


def self_enforcement() -> tuple[bool, str]:
    """层3/4/6 的发现物是否阻断: 读本规则自己的 enforcement 字段 (口径与契约同源)."""
    for r in load_rules():
        if r.get("id") == RULE_ID_SELF:
            blocking = str(r.get("enforcement", "advisory")) == "blocking"
            return blocking, str(r.get("review_before", ""))
    return False, ""


def check_tools_alive() -> dict:
    """层3: GaC 工具存活检测 (语法正确 + __main__ 入口).

    不跑实际工作 (避免 --help 触发 drift/healthcheck 全量执行的 timeout/副作用).
    存活 = Python 语法可解析 + 有 __main__ 入口 (可被 python tool.py 调起).
    """
    import ast

    if not GAC_TOOLS:
        return {
            "alive": 0,
            "dead": ["层3 仪器未接上: bin/gac-*.py ∪ bin/gac/*.py 匹配 0 个 (零分母不得判绿)"],
            "total": 0,
            "audited": 0,
            "instrument_dead": True,
        }

    alive, dead = [], []
    for tool in GAC_TOOLS:
        name = tool.name
        try:
            source = tool.read_text(encoding="utf-8")
            ast.parse(source)  # 语法正确性
            if "__name__" in source and "__main__" in source:
                alive.append(name)
            else:
                dead.append(f"{name} (无 __main__ 入口)")
        except SyntaxError as e:
            dead.append(f"{name} (语法错: {e})")
        except OSError as e:
            dead.append(f"{name} (读失败: {e})")
    return {
        "alive": len(alive),
        "dead": dead,
        "total": len(GAC_TOOLS),
        "audited": len(alive) + len(dead),
        "instrument_dead": False,
    }


def _source_ref_base(ref: Any) -> str:
    return str(ref or "").split("::")[0].split("#")[0].strip()


def check_indexed_integrity() -> dict:
    """层4: 全部路径型 source_ref 的文件存在性 (GaC 治 indexed 完整 + 治其余登记).

    旧判据只走 `source_type == indexed` (90 条规则里 6 条), 于是 69 条带路径的登记
    从未被看过一眼. 现在按路径形状取, 子模块未检出的记 `device_unavailable`
    而不是判绿, 也不是判红.
    """
    rules = load_rules()
    missing: list[dict] = []
    device_unavailable: list[dict] = []
    checked = 0
    for r in rules:
        base = _source_ref_base(r.get("source_ref"))
        if not PATH_REF_RE.match(base):
            continue
        checked += 1
        stype = str(r.get("source_type", ""))
        kind = "indexed" if stype == "indexed" else "other"
        if base.startswith("projects/"):
            sub = "/".join(base.split("/")[:2])
            if not (WORKSPACE / sub / ".git").exists():
                device_unavailable.append({"id": r["id"], "ref": base, "reason": f"子模块 {sub} 未检出, 无法判定"})
                continue
            kind = "submodule"
        if not (WORKSPACE / base).exists():
            missing.append({"id": r["id"], "missing_ref": base, "kind": kind})
    indexed_missing = [m for m in missing if m["kind"] == "indexed"]
    return {
        "ok": len(missing) == 0,
        "missing_count": len(missing),
        "missing": missing,
        "indexed_missing_count": len(indexed_missing),
        "checked": checked,
        "rules": len(rules),
        "device_unavailable": device_unavailable,
    }


def check_exec_effective() -> dict:
    """层5: executor 执行有效性 (每条规则至少一个真注册 executor).

    检测: executor 非空 + 在 schema.executor_enum 内 (防声明不执行/拼错 executor).
    """
    rules = load_rules()
    valid_executors = set(load_doc_registry().get("schema", {}).get("executor_enum", []))
    issues = []
    for r in rules:
        execs = r.get("executor", [])
        if not execs:
            issues.append({"id": r["id"], "reason": "无 executor"})
            continue
        invalid = [e for e in execs if valid_executors and e not in valid_executors]
        if invalid:
            issues.append({"id": r["id"], "reason": f"非法 executor: {invalid}"})
    return {"ok": len(issues) == 0, "issues_count": len(issues), "issues": issues}


def check_schema_self_consistent() -> dict:
    """层2: schema 自洽 (required 字段 + enum 对齐, 复用 gac-validate 逻辑轻量版)."""
    rules = load_rules()
    schema = load_doc_registry().get("schema", {})
    required = schema.get("required", [])
    dim_enum = set(schema.get("dimension_enum", []))
    layer_enum = set(schema.get("layer_enum", []))
    issues = []
    for r in rules:
        for f in required:
            if not r.get(f):
                issues.append(f"{r.get('id', '?')}: 缺 {f}")
        if r.get("dimension") and dim_enum and r["dimension"] not in dim_enum:
            issues.append(f"{r['id']}: dimension 非法")
        if r.get("layer") and layer_enum and r["layer"] not in layer_enum:
            issues.append(f"{r['id']}: layer 非法")
    return {"ok": len(issues) == 0, "issues_count": len(issues), "rules": len(rules)}


def _load_local_gate() -> tuple[list[dict], str, dict | None]:
    """importlib 取运行时 GATES_LIST —— 唯一可信的"实际会跑什么"读数.

    返回 (gates, policy_source, policy). policy_source=sgf|default|unavailable.
    """
    if not LOCAL_GATE.is_file():
        return [], "unavailable", None
    saved = sys.path[:]
    sys.path[:0] = [str(WORKSPACE), str(WORKSPACE / "bin"), str(WORKSPACE / "bin" / "lib")]
    try:
        spec = importlib.util.spec_from_file_location("gac_local_gate_for_bootstrap", LOCAL_GATE)
        if spec is None or spec.loader is None:
            return [], "unavailable", None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        try:
            spec.loader.exec_module(mod)
        except SystemExit:
            pass
        except Exception as e:  # 装置不可用 != 没有问题, 也 != 没有问题被证明
            return [], f"unavailable ({type(e).__name__}: {e})", None
        gates = list(getattr(mod, "GATES_LIST", []) or [])
        src = "sgf"
        if getattr(mod, "POLICY", None) is getattr(mod, "DEFAULT_POLICY", None):
            src = "default"
        policy_path = getattr(mod, "SGF_POLICY_YAML", None)
        policy = None
        if policy_path is not None:
            try:
                if Path(policy_path).is_file():
                    policy = yaml.safe_load(Path(policy_path).read_text(encoding="utf-8")) or {}
            except Exception:
                policy = None
        return gates, src, policy
    finally:
        sys.path[:] = saved


def _command_tokens(cmd: Any) -> set[str]:
    if isinstance(cmd, list):
        return {str(x) for x in cmd if isinstance(x, str)}
    if isinstance(cmd, str):
        return set(cmd.split())
    return set()


def _py_tokens(text: str, skip_comments: bool = False) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if skip_comments and line.startswith("#"):
            continue
        out |= set(PY_TOKEN_RE.findall(line))
    return out


def _collect_run_bodies(node: Any, key: str = "run") -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, str):
                out.append(v)
            else:
                out.extend(_collect_run_bodies(v, key))
    elif isinstance(node, list):
        for x in node:
            out.extend(_collect_run_bodies(x, key))
    return out


def _norm_hit(tokens: set[str], tool: str) -> bool:
    for tok in tokens:
        t = ROOT_VAR_RE.sub("", tok).lstrip("./")
        if not t:
            continue
        if t == tool or tool.endswith("/" + t) or t.endswith(tool):
            return True
    return False


def _runtime_plane() -> tuple[set[str], int, str, dict | None]:
    """runtime 平面读数: (command 里的 .py token, gate 条数, 策略来源, 策略原文).

    单独成函数是为了让用例能把口径换成"正则扫 gac-local-gate.py 源码" —— 那种口径
    会把 DEFAULT_POLICY 的字面量当成已接线, 正是本层要防的假绿.
    """
    gates, policy_source, policy = _load_local_gate()
    tokens: set[str] = set()
    for g in gates:
        tokens |= {t for t in _command_tokens(g.get("command")) if t.endswith(".py")}
        tokens |= {t for t in _command_tokens(g.get("check")) if t.endswith(".py")}
    return tokens, len(gates), policy_source, policy


def check_plane_coverage() -> dict:
    """层6: ci-surfaces 登记声明的执行 vs 四个真实平面.

    登记面写 `workflow: gac-gate.yml` / `triggers: [gac_local_gate]` 而四平面全无,
    就是"登记了但没人跑" —— 旧层5 只查 executor 枚举合法性, 看不见这件事.
    """
    if not CI_SURFACES.is_file():
        return {
            "ok": True,
            "available": False,
            "note": f"登记面缺席: {CI_SURFACES.relative_to(WORKSPACE)}",
            "surfaces": 0,
            "declared": 0,
            "reached": 0,
            "manual_exempt": 0,
            "violations": [],
            "planes": {},
        }

    runtime_tokens, gates_n, policy_source, policy = _runtime_plane()

    ci_tokens: set[str] = set()
    runner_covered: set[str] = set()
    wf_files = sorted(WORKFLOWS_DIR.glob("*.y*ml")) if WORKFLOWS_DIR.is_dir() else []
    for wf in wf_files:
        try:
            doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        except Exception:
            continue
        for body in _collect_run_bodies(doc):
            ci_tokens |= _py_tokens(body, skip_comments=True)
            # registry-driven 承接面: workflow 里 `ci-check-runner.py --workflow <自己>`
            # 也算执行了登记项 (ci-check-runner.run_surfaces 按 workflow 字段选).
            if "ci-check-runner.py" in body:
                runner_covered |= set(re.findall(r"--workflow\s+([\w.-]+\.y*ml)", body))

    hook_tokens: set[str] = set()
    hook_files: list[Path] = []
    if HOOKS_DIR.is_dir():
        hook_files = [p for p in sorted(HOOKS_DIR.iterdir()) if p.is_file() and p.suffix != ".md"]
    if HOOK_RUNNER.is_file():
        hook_files.append(HOOK_RUNNER)
    for hp in hook_files:
        try:
            lines = hp.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if HOOK_CALL_RE.search(line):
                hook_tokens |= set(PY_TOKEN_RE.findall(line))

    cron_tokens: set[str] = set()
    cron_declared_only: set[str] = set()
    if CRON_REGISTRY.is_file():
        for job in (yaml.safe_load(CRON_REGISTRY.read_text(encoding="utf-8")) or {}).get("jobs") or []:
            if not isinstance(job, dict):
                continue
            cmd = str(job.get("command") or "")
            found = {t for t in _py_tokens(cmd) if t.endswith(".py")}
            if str(job.get("reality") or "") in CRON_REACHED_REALITY:
                cron_tokens |= found
            else:
                cron_declared_only |= found

    policy_tokens: set[str] = set()
    if isinstance(policy, dict):
        found: list[Any] = [policy]
        while found:
            node = found.pop()
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in ("command", "check") and isinstance(v, (list, str)):
                        policy_tokens |= {t for t in _command_tokens(v) if t.endswith(".py")}
                    else:
                        found.append(v)
            elif isinstance(node, list):
                found.extend(node)

    planes = {
        "runtime": {
            "gates": gates_n,
            "policy_source": policy_source,
            "paths": len(runtime_tokens),
        },
        "ci": {
            "workflows": len(wf_files),
            "paths": len(ci_tokens),
            "runner_covered": sorted(runner_covered),
        },
        "hooks": {"files": len(hook_files), "paths": len(hook_tokens)},
        "policy": {"available": isinstance(policy, dict), "paths": len(policy_tokens)},
        "cron": {
            "paths": len(cron_tokens),
            "declared_only": len(cron_declared_only),
        },
    }
    devices_unavailable = [k for k, v in planes.items() if not v.get("paths") and not v.get("available", True)]

    try:
        surfaces = (yaml.safe_load(CI_SURFACES.read_text(encoding="utf-8")) or {}).get("surfaces", [])
    except Exception as e:
        return {
            "ok": True,
            "available": False,
            "note": f"登记面解析失败: {type(e).__name__}: {e}",
            "surfaces": 0,
            "declared": 0,
            "reached": 0,
            "manual_exempt": 0,
            "violations": [],
            "planes": planes,
        }

    declared = reached = manual_exempt = skipped = 0
    violations: list[dict] = []
    for s in surfaces:
        if not isinstance(s, dict):
            continue
        tool = str(s.get("tool", ""))
        if not tool.endswith(".py"):
            continue
        if str(s.get("status", "active")) != "active":
            skipped += 1
            continue
        wf = str(s.get("workflow") or "(none)")
        triggers = [str(t) for t in (s.get("triggers") or [])]
        claims_plane = wf != "(none)" or bool(set(triggers) & AUTOMATED_TRIGGERS) or bool(s.get("gate"))
        if not claims_plane:
            if triggers:
                manual_exempt += 1
            skipped += 1
            continue
        declared += 1
        hit = {
            "runtime": _norm_hit(runtime_tokens, tool),
            "ci": _norm_hit(ci_tokens, tool) or (wf in runner_covered),
            "hooks": _norm_hit(hook_tokens, tool),
            "policy": _norm_hit(policy_tokens, tool),
            "cron": _norm_hit(cron_tokens, tool),
        }
        if any(hit.values()):
            reached += 1
            continue
        # 装置不可用的平面不能用来证明"没跑": 若某个平面读不到, 结论降级
        if policy_source != "sgf":
            violations.append(
                {
                    "tool": tool,
                    "reason": (f"runtime/policy 平面装置不可用 (policy_source={policy_source}), 不下「无人执行」结论"),
                    "verdict": "device_unavailable",
                }
            )
            continue
        reason = ("五平面全缺席 (runtime GATES_LIST / CI workflow run: / .githooks 调用行 / "
                   "sgf-policy command / cron 已装机作业)")
        if wf != "(none)" and not (WORKFLOWS_DIR / wf).is_file():
            reason += f"; 声称的 workflow 文件不存在: {wf}"
        elif wf != "(none)" and wf not in {p.name for p in wf_files}:
            reason += f"; 声称的 workflow 文件不存在: {wf}"
        if s.get("gate") and wf == "(none)" and not triggers:
            reason = "声明 gate=true 但无 trigger 无 workflow, 且" + reason
        violations.append(
            {
                "tool": tool,
                "reason": reason,
                "workflow_claim": wf,
                "triggers": triggers,
                "gate": bool(s.get("gate")),
                "verdict": "declared_no_execution_plane",
            }
        )

    return {
        "ok": len(violations) == 0,
        "available": True,
        "surfaces": len(surfaces),
        "declared": declared,
        "reached": reached,
        "manual_exempt": manual_exempt,
        "skipped": skipped,
        "violations_count": len(violations),
        "violations": violations,
        "planes": planes,
        "devices_unavailable": devices_unavailable,
        "instrument_dead": declared == 0,
    }


def run_bootstrap(as_json: bool = False) -> int:
    """主自举检测."""
    blocking, review_before = self_enforcement()
    report: dict[str, Any] = {
        "tools": check_tools_alive(),
        "indexed_integrity": check_indexed_integrity(),
        "exec_effective": check_exec_effective(),
        "schema_self": check_schema_self_consistent(),
        "plane_coverage": check_plane_coverage(),
        "enforcement": {"blocking": blocking, "review_before": review_before},
    }
    t = report["tools"]
    sr = report["indexed_integrity"]
    pl = report["plane_coverage"]
    # 始终阻断: 仪器故障(层3 零分母/runtime 不可用) · 层4 indexed 子集 · 层2/层5
    hard_fail = (
        t.get("instrument_dead")
        or bool(t["dead"] and blocking)
        or sr["indexed_missing_count"] > 0
        or report["exec_effective"]["ok"] is False
        or report["schema_self"]["ok"] is False
        or (bool(pl.get("instrument_dead")) and pl.get("available"))
    )
    # advisory 期内只点名: 层3 dead / 层4 其余缺席 / 层6 平面缺席
    advisory_fail = sr["missing_count"] > 0 or not pl.get("ok", True) or bool(t["dead"])
    report["ok"] = not hard_fail and not (blocking and advisory_fail)
    report["blocking"] = bool(hard_fail)
    report["advisory_gaps"] = bool(advisory_fail)

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1

    print("═══ GaC 自举递归检测 (GaC 治 GaC 自身) ═══")
    t_status = "✅" if not t["dead"] else ("❌" if blocking else "⚠️")
    print(f"▶ 层3 工具活/死: {t_status} {t['alive']}/{t['total']} (audited={t.get('audited', 0)})")
    for d in t["dead"][:5]:
        print(f"    {'❌' if blocking else '⚠️'} {d}")
    if len(t["dead"]) > 5:
        print(f"    … 另 {len(t['dead']) - 5} 项 (--json 全量)")

    ii_status = "✅" if sr["ok"] else ("❌" if blocking else "⚠️")
    print(
        f"▶ 层4 source_ref 完整: {ii_status} 路径型 {sr['checked']}/{sr['rules']} 规则"
        f" 缺席={sr['missing_count']} (indexed 缺席={sr['indexed_missing_count']}, 始终阻断)"
    )
    for m in sr["missing"][:8]:
        print(f"    {'❌' if blocking else '⚠️'} {m['id']}: {m['missing_ref']} [{m['kind']}]")
    if sr["missing_count"] > 8:
        print(f"    … 另 {sr['missing_count'] - 8} 项 (--json 全量)")
    for d in sr["device_unavailable"][:3]:
        print(f"    ⛔ 装置不可用 {d['id']}: {d['reason']}")

    ee = report["exec_effective"]
    ee_status = "✅" if ee["ok"] else "❌"
    print(f"▶ 层5 执行有效: {ee_status} 非法/无 executor={ee['issues_count']}")
    for i in ee["issues"][:3]:
        print(f"    ❌ {i['id']}: {i['reason']}")

    pl_status = "✅" if pl.get("ok") else ("❌" if blocking else "⚠️")
    if not pl.get("available"):
        print(f"▶ 层6 执行平面: ⛔ {pl.get('note', '装置不可用')}")
    else:
        pn = pl["planes"]["runtime"]
        print(
            f"▶ 层6 执行平面: {pl_status} 声明执行 {pl['declared']}/{pl['surfaces']} 登记项,"
            f" 命中 {pl['reached']}, 点名 {pl['violations_count']},"
            f" manual 豁免 {pl['manual_exempt']} (runtime {pn['gates']} gates / policy={pn['policy_source']})"
        )
        for v in pl["violations"][:12]:
            print(f"    {'❌' if blocking else '⚠️'} {v['tool']} — {v['reason']}")
        if pl["violations_count"] > 12:
            print(f"    … 另 {pl['violations_count'] - 12} 项 (--json 全量)")

    ss = report["schema_self"]
    ss_status = "✅" if ss["ok"] else "❌"
    print(f"▶ 层2 schema 自洽: {ss_status} {ss['rules']} 规则 issues={ss['issues_count']}")

    print()
    mode = "blocking" if blocking else f"advisory (转阻断读 {RULE_ID_SELF}.enforcement, review_before={review_before})"
    if report["ok"]:
        extra = " 有点名未阻断" if advisory_fail else ""
        print(f"═══ 总体: ✅ GaC 自身完整 (元治理递归闭环) [{mode}]{extra} ═══")
    else:
        print(f"═══ 总体: ❌ GaC 自举发现 gap [{mode}] ═══")
    return 0 if report["ok"] else 1


def main() -> int:
    args = sys.argv[1:]
    return run_bootstrap(as_json="--json" in args)


if __name__ == "__main__":
    sys.exit(main())
