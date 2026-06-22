"""Workflow Executor — 执行工作流定义

核心函数:
- execute_workflow(): 旧接口，向后兼容的完整执行器
- execute_m1_workflow(): 新接口，通过 BackendRegistry 路由
- execute_step(): 原始硬编码 action 执行器 (委派 actions.py)
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from ecos.workflow.backend_registry import resolve  # noqa: E402
from ecos.workflow.loader import load_workflow  # noqa: E402
from ecos.workflow.validator import (  # noqa: E402
    X2BudgetDeducer,
    X3CostRecorder,
    check_execution_result,
    generate_m0_snapshot,
    validate_workflow,
)

logger = logging.getLogger("ecos.workflow.executor")


# L0 audit (可选导入)
try:
    from l0_audit import validate_operation, log_operation  # type: ignore[import-not-found]  # noqa: E402
except ImportError:
    validate_operation = lambda *a, **kw: None  # noqa: E731
    log_operation = lambda *a, **kw: None  # noqa: E731


# =========================================================================
# 新接口: execute_m1_workflow — 通过 BackendRegistry 路由
# =========================================================================

def execute_m1_workflow(name: str, params: dict | None = None,
                        dry_run: bool = False) -> dict:
    """执行 M1 工作流·通过 BackendRegistry 路由到对应后端

    Args:
        name: 工作流名称 (M1 ID 或 definitions 名称)
        params: 执行参数
        dry_run: 干跑模式，只打印不执行

    Returns:
        执行结果 dict
    """
    wf = load_workflow(name)
    if not wf:
        return {"error": f"工作流不存在: {name}"}

    m1_node = _normalize_m1(wf)
    wf_name = m1_node.get("name", name)
    is_m1 = m1_node.get("source") == "m1"

    results = {
        "workflow": name,
        "display": wf_name,
        "source": "m1" if is_m1 else "definition",
        "started": datetime.now().isoformat(),
        "steps": [],
        "passed": 0,
        "failed": 0,
    }

    logger.info("Executing workflow: %s (backend=%s, mode=%s)",
                wf_name,
                m1_node.get("execution", {}).get("backend", "default"),
                m1_node.get("execution", {}).get("mode", "workflow"))

    if wf.get("description"):
        logger.info("  %s", wf["description"])

    steps = wf.get("steps", [])
    if not steps:
        return {**results, "error": "工作流无步骤定义"}

    # L0 audit: pre-check
    validate_operation("_workflow", "workflow_execute", f"bos://_workflow/{name}")

    if dry_run:
        for i, step in enumerate(steps, 1):
            step_name = step.get("name", f"step-{i}")
            results["steps"].append({
                "name": step_name,
                "status": "dry_run",
                "action": step.get("action", ""),
            })
        results["finished"] = datetime.now().isoformat()
        return results

    # 通过 BackendRegistry 解析后端并执行
    try:
        # ── 治理管线: pre-flight checks ──
        violations = validate_workflow(m1_node)
        if violations:
            results["violations"] = violations
            if any(v.get("severity") == "error" for v in violations):
                logger.warning("Workflow blocked by %d validation violations", len(violations))
                results["error"] = f"治理约束未通过: {len(violations)} 个违规"
                results["finished"] = datetime.now().isoformat()
                return results
            logger.info("Workflow validation: %d warnings (non-blocking)", len(violations))

        budget_status = X2BudgetDeducer.check_budget(m1_node)
        if not budget_status.get("ok") and budget_status.get("budget"):
            logger.warning("Budget warnings: %s", budget_status.get("warnings"))
            if budget_status.get("warnings") and any("余额不足" in w for w in budget_status.get("warnings", [])):
                results["error"] = f"X2 熔断: Token 余额不足 ({budget_status.get('balance', 0)})"
                results["finished"] = datetime.now().isoformat()
                logger.info("X2 circuit break triggered for workflow: %s", name)
                return results

        # ── 执行 ──
        backend_fn = resolve(wf)
        backend_result = backend_fn(wf, params)

        if "steps" in backend_result:
            results["steps"] = backend_result["steps"]
            results["passed"] = backend_result.get("passed", 0)
            results["failed"] = backend_result.get("failed", 0)
        else:
            # 后端的简略返回模式
            ok = backend_result.get("passed", True)
            results["steps"].append({
                "name": wf_name,
                "status": "ok" if ok else "failed",
                "result": backend_result,
            })
            if ok:
                results["passed"] += 1
            else:
                results["failed"] += 1
    except Exception as e:
        logger.error("Workflow execution failed: %s", e)
        results["failed"] += 1
        results["steps"].append({
            "name": "execute",
            "status": "error",
            "error": str(e),
        })

    # ── 治理管线: post-flight checks ──
    results["finished"] = datetime.now().isoformat()

    # X2: 真实扣减（写入共享账本）
    X2BudgetDeducer.deduct(name, m1_node)

    # X4: 一致性检查
    if "error" not in results:
        x4_violations = check_execution_result(m1_node, results)
        if x4_violations:
            results["post_violations"] = x4_violations
            for v in x4_violations:
                logger.warning("Post-flight violation: %s", v["message"])

    # X3: 成本归因
    X3CostRecorder.record(name, results)

    # M0: 运行时快照
    m0_path = generate_m0_snapshot(name, m1_node, results)
    if m0_path:
        results["m0_snapshot"] = m0_path

    # Log workflow completion
    log_operation({
        "timestamp": datetime.now().isoformat(),
        "domain": "_workflow",
        "operation": f"workflow:{name}",
        "uri": f"bos://_workflow/{name}",
        "passed": results["failed"] == 0,
        "violations": [],
    })

    return results


def _normalize_m1(wf: dict) -> dict:
    """归一化 M1 节点字段"""
    wf["source"] = "m1" if "bos_uri" in wf else "definition"
    if "execution" not in wf:
        wf["execution"] = {}
    return wf


# =========================================================================
# 旧接口: execute_workflow — 向后兼容
# =========================================================================

def execute_workflow(name: str, params: dict | None = None,
                     dry_run: bool = False) -> dict:
    """执行工作流·每步 L0 审计·向后兼容接口

    当 M1 节点有 execution.backend 字段时走新后端路由。
    没有时保持原有硬编码 action 行为。
    """
    wf = load_workflow(name)
    if not wf:
        return {"error": f"工作流不存在: {name}"}

    m1_node = _normalize_m1(wf)
    wf_name = m1_node.get("name", name)
    is_m1 = m1_node.get("source") == "m1"

    results = {
        "workflow": name,
        "display": wf_name,
        "source": "m1" if is_m1 else "definition",
        "started": datetime.now().isoformat(),
        "steps": [],
        "passed": 0,
        "failed": 0,
    }

    # 如果 M1 节点显式声明了 backend，走新路由
    if wf.get("execution", {}).get("backend"):
        return execute_m1_workflow(name, params, dry_run)

    print(f"\n  ═══ Workflow: {wf_name} ═══")
    if wf.get("description"):
        print(f"  {wf['description']}")
    if is_m1:
        print(f"  BOS URI: {wf.get('bos_uri')} | {wf.get('layer')} | {wf.get('domain')}")
    print()

    steps = wf.get("steps", [])
    if not steps:
        return {**results, "error": "工作流无步骤定义"}

    for i, step in enumerate(steps, 1):
        step_name = step.get("name", f"step-{i}")
        action = step.get("action", "")

        # L0 audit: pre-check
        validate_operation("_workflow", "workflow_step",
                           f"bos://_workflow/{name}#{step_name}")
        print(f"  [{i}/{len(steps)}] {step_name}")

        if dry_run:
            print(f"    📋 (dry-run) {action}")
            results["steps"].append({
                "name": step_name, "status": "dry_run", "action": action,
            })
            continue

        try:
            if is_m1:
                step_result = {
                    "passed": True,
                    "summary": f"已路由到 {wf.get('layer')} 层执行",
                }
            else:
                step_result = _execute_step(action, params)
            ok = step_result.get("passed", True)
            results["steps"].append({
                "name": step_name,
                "status": "ok" if ok else "failed",
                "result": step_result,
            })
            if ok:
                results["passed"] += 1
            else:
                results["failed"] += 1
            print(f"    {'✅' if ok else '❌'} {step_result.get('summary', '')}")
        except Exception as e:
            results["steps"].append({
                "name": step_name, "status": "error", "error": str(e),
            })
            results["failed"] += 1
            print(f"    ❌ {e}")
            on_failure = (step.get("on_failure")
                          or (wf.get("execution", {}).get("on_failure") if is_m1 else None)
                          or "continue")
            if on_failure == "abort":
                print("    ⚠️ 中止执行")
                break

    results["finished"] = datetime.now().isoformat()
    total = results["passed"] + results["failed"]
    print(f"\n  {results['passed']}✅  {results['failed']}❌  (共{total}步)\n")

    log_operation({
        "timestamp": datetime.now().isoformat(),
        "domain": "_workflow",
        "operation": f"workflow:{name}",
        "uri": f"bos://_workflow/{name}",
        "passed": results["failed"] == 0,
        "violations": [],
    })

    return results

# =========================================================================
# 硬编码 action 执行器 — 声明式注册 (actions.py)
# =========================================================================


def _execute_step(action: str, params: dict | None = None) -> dict:
    """执行单个步骤（通过 actions.py 注册表路由）

    action 先经过 actions.py 的命名空间剥离和别名映射，
    然后查找注册的 handler。
    未注册 action 返回未知动作错误。
    """
    from ecos.workflow.actions import resolve_action

    params = params or {}
    handler = resolve_action(action)
    if handler is None:
        return {"passed": False, "summary": f"未知动作: {action}"}
    return handler(params)
