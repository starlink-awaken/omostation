"""
OntoDerive 规约检查引擎 — 从derive.py拆分
===========================================
13条规约检查(C-01~C-13)，独立模块。

C1-C8 为独立 _check_cNN 辅助函数，C9-C13 通过 check_theory 注册表调用。
"""

import datetime
import re
from pathlib import Path
from typing import Any

try:
    from .constants import V2_ID_PATTERNS  # type: ignore[import-not-found,no-redef]
    from .utils import CachedReader, save_json  # type: ignore[import-not-found,no-redef]
except ImportError:
    from ontoderive.foundation.utils import CachedReader, save_json  # noqa
    from ontoderive.foundation.constants import V2_ID_PATTERNS  # type: ignore[import-not-found,no-redef]


# ── C1-C8 独立检查函数 ──────────────────────────────────────────────


def _check_c01(
    root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any, rf: Any, cr: Any
) -> dict[str, Any]:
    """C-01: 事实基座完整性"""
    all_md = cr.all_md
    facts_exist = len(all_md(facts_dir)) > 0
    return {
        "pid": "C-01",
        "name": "事实基座完整性",
        "passed": facts_exist,
        "severity": "BLOCKER" if not facts_exist else "PASS",
        "detail": f"事实文件: {len(all_md(facts_dir))} 个",
        "fixes": ["创建 facts/data.md 和 facts/policy.md"],
        "file": "",
        "line": 0,
    }


def _check_c02(
    root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any, rf: Any, cr: Any
) -> dict[str, Any]:
    """C-02: 推论体系完整性"""
    all_md = cr.all_md
    infs_exist = len(all_md(inferences_dir)) > 0
    return {
        "pid": "C-02",
        "name": "推论体系完整性",
        "passed": infs_exist,
        "severity": "ERROR" if not infs_exist else "PASS",
        "detail": f"推论文件: {len(all_md(inferences_dir))} 个",
        "fixes": ["创建 inferences/contradictions.md"],
        "file": "",
        "line": 0,
    }


def _check_c03(
    root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any, rf: Any, cr: Any
) -> dict[str, Any]:
    """C-03: 方案文件完整性"""
    all_md = cr.all_md
    schemes = all_md(scheme_dir)
    return {
        "pid": "C-03",
        "name": "方案文件完整性",
        "passed": len(schemes) > 0,
        "severity": "ERROR" if len(schemes) == 0 else "PASS",
        "detail": f"方案文件: {len(schemes)} 个",
        "fixes": [],
        "file": "",
        "line": 0,
    }


def _check_c04(
    root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any, rf: Any, cr: Any
) -> dict[str, Any]:
    """C-04: 事实可追溯性（含file:line + 蕴含图统计）"""
    all_md = cr.all_md
    fact_ids = set()
    for f in all_md(facts_dir):
        text = rf(f)
        fact_ids.update(re.findall(r"(D-F\d+|P-F\d+)", text))

    inf_text = ""
    for f in all_md(inferences_dir):
        inf_text += rf(f)
    schemes = all_md(scheme_dir)
    scheme_text = ""
    for f in schemes:
        scheme_text += rf(f)

    traced_in_inf = sum(1 for fid in fact_ids if fid in inf_text)
    traced_in_scheme = sum(1 for fid in fact_ids if fid in scheme_text)
    untraced = [fid for fid in fact_ids if fid not in scheme_text]
    detail = f"事实{len(fact_ids)}个: 推论引用{traced_in_inf}, 方案引用{traced_in_scheme}"
    # v2.3: 蕴含图运行时统计
    try:
        from ontoderive.theories.logic import build_from_project  # type: ignore[import-not-found,no-redef]

        g = build_from_project(root)
        gs = g.stats()
        detail += f" | 蕴含图: {gs['nodes']}节点/{gs['edges']}边, 深度{gs['max_depth']}"
    except Exception:
        pass
    if untraced:
        detail += f", 未追溯{len(untraced)}个: {','.join(untraced[:3])}"
    return {
        "pid": "C-04",
        "name": "事实可追溯性",
        "passed": traced_in_inf > 0 and traced_in_scheme > 0,
        "severity": "WARN" if traced_in_inf == 0 else "PASS",
        "detail": detail,
        "fixes": ["标注事实编号引用"],
        "file": "",
        "line": 0,
    }


def _check_c05(
    root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any, rf: Any, cr: Any
) -> dict[str, Any]:
    """C-05: 断言可追溯性（含file:line）"""
    all_md = cr.all_md
    total_assertions = 0
    traced_assertions = 0
    untraced_assertions = []
    for doc in all_md(scheme_dir):
        text = rf(doc)
        rel_path = str(doc.relative_to(root))
        text_clean = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text_clean = re.sub(r"^#+\s+.*$", "", text_clean, flags=re.MULTILINE)
        for line_no, line in enumerate(text_clean.split("\n"), 1):
            assertions = re.findall(r"[^。\n]*?(?:应该|必须|需要)[^。]*?[。]", line)
            for a in assertions:
                if len(a) < 15:
                    continue
                total_assertions += 1
                if re.search(r"D-F\d+|P-F\d+|INF-|INF-V2-", a):
                    traced_assertions += 1
                else:
                    untraced_assertions.append(f"{rel_path}:{line_no}")
    rate = (traced_assertions / total_assertions * 100) if total_assertions > 0 else 100
    detail = f"断言{total_assertions}个, 可追溯{traced_assertions}, 率{rate:.0f}%"
    if untraced_assertions:
        detail += f", 未追溯: {untraced_assertions[0]}..."
    return {
        "pid": "C-05",
        "name": "断言可追溯性",
        "passed": rate >= 30,
        "severity": "WARN" if rate < 50 else ("ERROR" if rate < 30 else "PASS"),
        "detail": detail,
        "fixes": ["在含'应该/必须/需要'的句子旁标注事实编号引用"],
        "file": "",
        "line": 0,
    }


def _check_c06(
    root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any, rf: Any, cr: Any
) -> dict[str, Any]:
    """C-06: 关键判断可证伪性（含file:line）"""
    all_md = cr.all_md
    falsifiable_total = 0
    falsifiable_ok = 0
    non_falsifiable = []
    for doc in all_md(scheme_dir):
        text = rf(doc)
        rel_path = str(doc.relative_to(root))
        lines = text.split("\n")
        for line_no, line in enumerate(lines, 1):
            claims = re.findall(
                r"[^。]*(?:投入|产出|营收|建成|上线|完成|达到|成本|利润|转化率)[^。]*?(?:万|亿|年|月|日|%|倍)[^。]*。",
                line,
            )
            for c in claims:
                falsifiable_total += 1
                ctx = text[max(0, text.find(c) - 100) : text.find(c) + len(c) + 100] if c in text else c
                if re.search(r"如果.*?则|若.*?则|假设|条件|除非", ctx):
                    falsifiable_ok += 1
                else:
                    non_falsifiable.append(f"{rel_path}:{line_no}")
    rate_f = (falsifiable_ok / falsifiable_total * 100) if falsifiable_total > 0 else 100
    detail = f"预测断言{falsifiable_total}个, 可证伪{falsifiable_ok}, 率{rate_f:.0f}%"
    if non_falsifiable:
        detail += f", 不可证伪: {non_falsifiable[0]}..."
    return {
        "pid": "C-06",
        "name": "关键判断可证伪性",
        "passed": rate_f >= 15,
        "severity": "WARN" if rate_f < 30 else "PASS",
        "detail": detail,
        "fixes": ["为核心数字断言添加'如果X月后Y没发生则重新评估'条件"],
        "file": "",
        "line": 0,
    }


def _check_c07(
    root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any, rf: Any, cr: Any
) -> dict[str, Any]:
    """C-07: 实体ID合规性（v2.2 TypeValidator）"""
    all_md = cr.all_md
    all_text = ""
    for d in [facts_dir, entities_dir, inferences_dir, scheme_dir]:
        for f in all_md(d):
            all_text += rf(f)

    type_errors = []
    ids_found = set()
    skip_prefixes = ("C-", "P-", "ISC-", "F", "v", "v2", "v3", "E", "e")
    try:
        from ontoderive.foundation.typesystem import TypeValidator  # type: ignore[import-not-found,no-redef]

        tv = TypeValidator()
        for m in re.finditer(r"\b([A-Z][A-Za-z0-9_-]*(?:-[A-Za-z0-9_-]+)*)\b", all_text):
            raw_id = m.group(0)
            if "-" not in raw_id or len(raw_id) < 3:
                continue
            if any(raw_id.startswith(p) for p in skip_prefixes):
                continue
            if raw_id in ids_found:
                continue
            ids_found.add(raw_id)
            r = tv.check_id(raw_id)
            if not r.is_valid:
                type_errors.append(f"{raw_id}({r.errors[0]})")
    except ImportError:
        pass

    detail = f"v2前缀{len(V2_ID_PATTERNS)}种"
    if type_errors:
        detail += f", 类型错误: {len(type_errors)}个 [{'; '.join(type_errors[:3])}]"
    elif len(ids_found) > 0:
        detail += f", 校验通过: {len(ids_found)}个ID"
    return {
        "pid": "C-07",
        "name": "实体ID合规性(v2.2 TypeValidator)",
        "passed": len(type_errors) == 0,
        "severity": "WARN" if type_errors else "PASS",
        "detail": detail,
        "fixes": [],
        "file": "",
        "line": 0,
    }


def _check_c08(
    root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any, rf: Any, cr: Any
) -> dict[str, Any]:
    """C-08: 引擎自检"""
    script_path = Path(__file__).resolve()
    return {
        "pid": "C-08",
        "name": "推导引擎健康度",
        "passed": script_path.exists(),
        "severity": "BLOCKER" if not script_path.exists() else "PASS",
        "detail": f"引擎: {script_path.name}",
        "fixes": [],
        "file": "",
        "line": 0,
    }


# ── 主入口 ──────────────────────────────────────────────────────────


def run_check(root: Any, facts_dir: Any, entities_dir: Any, inferences_dir: Any, scheme_dir: Any, log_dir: Any) -> Any:
    """执行全部13条规约检查，使用CachedReader消除重复I/O"""
    cr = CachedReader()
    rf = cr.rf
    results = []
    severity_counts = {"PASS": 0, "WARN": 0, "ERROR": 0, "BLOCKER": 0}

    def result(
        pid: Any, name: Any, passed: Any, severity: Any, detail: Any, fixes: Any = None, file: Any = "", line: Any = 0
    ) -> Any:
        r = {
            "protocol_id": pid,
            "name": name,
            "passed": passed,
            "severity": severity,
            "detail": detail,
            "fixes": fixes or [],
            "file": file,
            "line": line,
        }
        results.append(r)
        cat = "PASS" if passed else severity
        severity_counts[cat] = severity_counts.get(cat, 0) + 1
        icon = {"PASS": "✅", "WARN": "🟡", "ERROR": "🟠", "BLOCKER": "🔴"}.get(cat, "⚪")
        print(f"  {icon} [{severity}] {pid} — {detail[:80]}")
        return r

    # C1-C8: 通过独立 _check_cNN 辅助函数执行
    for helper in [
        _check_c01,
        _check_c02,
        _check_c03,
        _check_c04,
        _check_c05,
        _check_c06,
        _check_c07,
        _check_c08,
    ]:
        r = helper(root, facts_dir, entities_dir, inferences_dir, scheme_dir, log_dir, rf, cr)
        result(r["pid"], r["name"], r["passed"], r["severity"], r["detail"], r["fixes"], r["file"], r["line"])

    # C9~C13: 委theory_check_registry（策略模式解耦）
    try:
        from .check_theory import THEORY_CHECKS, check_bayesian
    except ImportError:
        from check_theory import THEORY_CHECKS, check_bayesian  # type: ignore[import-not-found,no-redef]

    # C9: 贝叶斯 → 结果缓存供C-10复用
    try:
        r9 = check_bayesian(root)
        result(
            "C-09", r9["name"] if "name" in r9 else "贝叶斯信念传播(智能层)", r9["passed"], r9["severity"], r9["detail"]
        )
        _bayes_distribution = r9.get("distribution")
    except Exception as e:
        result("C-09", "贝叶斯信念传播(智能层)", False, "WARN", str(e)[:50])
        _bayes_distribution = None

    # C10~C13: 通过注册表调用，而非直接import
    for pid, name, check_fn in THEORY_CHECKS:
        if pid == "C-09":
            continue  # 已在上面处理（需要缓存distribution）
        try:
            kwargs = {}
            if pid == "C-10" and _bayes_distribution:
                kwargs["precomputed_confs"] = _bayes_distribution
            r = check_fn(root, **kwargs) if pid == "C-10" else check_fn(root)
            result(pid, name, r["passed"], r["severity"], r["detail"])
        except Exception as e:
            result(pid, name, False, "WARN", f"异常: {str(e)[:50]}")

    # 保存结果
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    save_json(
        log_dir / f"check-result-{ts}.json",
        {
            "checked_at": datetime.datetime.now().isoformat(),
            "total": len(results),
            "passed": severity_counts["PASS"],
            "severities": severity_counts,
            "details": results,
        },
    )
    save_json(
        log_dir / "check-result.json",
        {
            "checked_at": datetime.datetime.now().isoformat(),
            "total": len(results),
            "passed": severity_counts["PASS"],
            "severities": severity_counts,
            "details": results,
        },
    )

    total = len(results)
    passed_count = severity_counts["PASS"]
    print(
        f"[check] 📊 规约检查: {passed_count}/{total} 通过"
        f" (BLOCKER={severity_counts['BLOCKER']}"
        f" ERROR={severity_counts['ERROR']}"
        f" WARN={severity_counts['WARN']})"
    )

    return results, severity_counts
