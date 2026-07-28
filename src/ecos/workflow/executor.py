"""Workflow Executor — 执行工作流定义

核心函数:
- execute_workflow(): 旧接口，向后兼容的完整执行器
- execute_m1_workflow(): 新接口，通过 BackendRegistry 路由
- execute_step(): 原始硬编码 action 执行器 (委派 actions.py)
"""

from __future__ import annotations

import logging
from datetime import datetime

from ecos.workflow.backend_registry import resolve
from ecos.workflow.cache import get as cache_get
from ecos.workflow.cache import set as cache_set
from ecos.workflow.loader import load_workflow
from ecos.workflow.preflight import inject_preflight
from ecos.workflow.validator import (
    X2BudgetDeducer,
    X3CostRecorder,
    check_execution_result,
    generate_m0_snapshot,
    validate_workflow,
)

logger = logging.getLogger("ecos.workflow.executor")


# L0 audit (可选；不通过 sys.path 注入 ops — ADR-0181 Phase 3)
try:
    from l0_audit import (  # type: ignore[import-not-found]
        log_operation,
        validate_operation,
    )
except ImportError:
    def validate_operation(*a, **kw):
        return None

    def log_operation(*a, **kw):
        return None


# =========================================================================
# 新接口: execute_m1_workflow — 通过 BackendRegistry 路由
# =========================================================================


def execute_m1_workflow(
    name: str, params: dict | None = None, dry_run: bool = False
) -> dict:
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

    logger.info(
        "Executing workflow: %s (backend=%s, mode=%s)",
        wf_name,
        m1_node.get("execution", {}).get("backend", "default"),
        m1_node.get("execution", {}).get("mode", "workflow"),
    )

    if wf.get("description"):
        logger.info("  %s", wf["description"])

    # 读取工作流级缓存配置
    cache_ttl = m1_node.get("execution", {}).get("cache_ttl", 0)

    steps = wf.get("steps", [])
    if not steps:
        return {**results, "error": "工作流无步骤定义"}

    # L0 audit: pre-check
    validate_operation("_workflow", "workflow_execute", f"bos://_workflow/{name}")

    if dry_run:
        for i, step in enumerate(steps, 1):
            step_name = step.get("name", f"step-{i}")
            results["steps"].append(
                {
                    "name": step_name,
                    "status": "dry_run",
                    "action": step.get("action", ""),
                }
            )
        results["finished"] = datetime.now().isoformat()
        return results

    # 通过 BackendRegistry 解析后端并执行
    try:
        # ── 治理管线: pre-flight checks ──
        violations = validate_workflow(m1_node)
        if violations:
            results["violations"] = violations
            if any(v.get("severity") == "error" for v in violations):
                logger.warning(
                    "Workflow blocked by %d validation violations", len(violations)
                )
                results["error"] = f"治理约束未通过: {len(violations)} 个违规"
                results["finished"] = datetime.now().isoformat()
                return results
            logger.info(
                "Workflow validation: %d warnings (non-blocking)", len(violations)
            )

        # ── 缓存检查：如果工作流配置了 cache_ttl，优先返回缓存 ──
        if cache_ttl > 0 and not dry_run:
            cached = cache_get(name, 0, params)
            if cached is not None:
                logger.info("Cache HIT for workflow: %s (skip budget check)", name)
                return dict(cached)

        budget_status = X2BudgetDeducer.check_budget(m1_node)
        if not budget_status.get("ok") and budget_status.get("budget"):
            logger.warning("Budget warnings: %s", budget_status.get("warnings"))
            if budget_status.get("warnings") and any(
                "余额不足" in w for w in budget_status.get("warnings", [])
            ):
                results["error"] = (
                    f"X2 熔断: Token 余额不足 ({budget_status.get('balance', 0)})"
                )
                results["finished"] = datetime.now().isoformat()
                logger.info("X2 circuit break triggered for workflow: %s", name)
                return results

        # ── 执行（注入 preflight：backend 可验证治理管线已通过）──
        backend_fn = resolve(wf)
        params_with_pf = inject_preflight(
            params,
            name,
            backend=m1_node.get("execution", {}).get("backend", "default"),
            source=m1_node.get("source", "definition"),
        )
        backend_result = backend_fn(wf, params_with_pf)

        if "steps" in backend_result:
            results["steps"] = backend_result["steps"]
            results["passed"] = backend_result.get("passed", 0)
            results["failed"] = backend_result.get("failed", 0)
        else:
            # 后端的简略返回模式
            ok = backend_result.get("passed", True)
            results["steps"].append(
                {
                    "name": wf_name,
                    "status": "ok" if ok else "failed",
                    "result": backend_result,
                }
            )
            if ok:
                results["passed"] += 1
            else:
                results["failed"] += 1
    except Exception as e:  # defensive fallback
        logger.error("Workflow execution failed: %s", e)
        results["failed"] += 1
        results["steps"].append(
            {
                "name": "execute",
                "status": "error",
                "error": str(e),
            }
        )

    # ── 缓存写入：如果工作流配置了 cache_ttl，将结果写入缓存 ──
    if cache_ttl > 0 and "error" not in results:
        cache_set(name, 0, results, ttl=cache_ttl, params=params)

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
    log_operation(
        {
            "timestamp": datetime.now().isoformat(),
            "domain": "_workflow",
            "operation": f"workflow:{name}",
            "uri": f"bos://_workflow/{name}",
            "passed": results["failed"] == 0,
            "violations": [],
        }
    )

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


def execute_workflow(
    name: str, params: dict | None = None, dry_run: bool = False
) -> dict:
    """执行工作流 — 向后兼容接口（全部委派 execute_m1_workflow）

    保持签名和返回值兼容，但所有执行逻辑通过 execute_m1_workflow 统一路由。
    确保 X2/X3/X4/M0 治理管线在所有路径下都执行。
    """
    return execute_m1_workflow(name, params=params, dry_run=dry_run)


# =========================================================================
# 硬编码 action 执行器 — 声明式注册 (actions.py)
# =========================================================================


def _execute_step(
    action: str, params: dict | None = None, step: dict | None = None
) -> dict:
    """执行单个步骤（通过 actions.py 注册表路由）

    支持自定义命令:
      当 step 中定义了 command 字段且 action 在 actions.py 中未注册时,
      将 command 作为 subprocess 命令执行。

    示例 YAML:
      steps:
        - name: 自定义检查
          action: my_custom_check
          command: python3 /path/to/script.py --flag
          timeout: 60
    """
    from ecos.workflow.actions import resolve_action

    params = params or {}
    handler = resolve_action(action)
    if handler is not None:
        # 将 step 级字段（如 workflow、command）合并到 params 以供 handler 使用
        step_params = dict(params)
        if step:
            for key in ("workflow", "command", "timeout", "args", "params"):
                if key in step:
                    val = step[key]
                    if (
                        isinstance(val, dict)
                        and key in step_params
                        and isinstance(step_params[key], dict)
                    ):
                        step_params[key].update(val)
                    else:
                        step_params[key] = val
        return handler(step_params)

    # 自定义命令回退 (step.command)
    if step and step.get("command"):
        return _execute_command(step)

    return {"passed": False, "summary": f"未知动作: {action}"}


def _execute_command(step: dict) -> dict:
    """执行自定义命令 (step.command + step.args)"""
    import shlex
    import subprocess

    command = step.get("command", "")
    if not command:
        return {"passed": False, "summary": "无 command 定义"}

    # 拆分为 shell 命令
    if isinstance(command, str):
        cmd = shlex.split(command)
    else:
        cmd = list(command)

    timeout = step.get("timeout", 60)
    step_name = step.get("name", "?")

    try:
        logger.info("Executing custom command: %s", " ".join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        ok = r.returncode == 0
        summary = (
            r.stdout.strip()[:200] or r.stderr.strip()[:200] or ("✅" if ok else "❌")
        )
        return {
            "passed": ok,
            "summary": summary,
            "stdout": r.stdout[:1000],
            "stderr": r.stderr[:500],
        }
    except subprocess.TimeoutExpired:
        logger.warning("Custom command timed out (%ss): %s", timeout, step_name)
        return {"passed": False, "summary": f"命令超时 ({timeout}s)"}
    except FileNotFoundError:
        return {"passed": False, "summary": f"命令未找到: {cmd[0] if cmd else ''}"}
    except Exception as e:  # defensive fallback
        logger.error("Custom command failed: %s", e)
        return {"passed": False, "summary": str(e)}


# =========================================================================
# 测试模式 — mock action 执行，验证编排逻辑
# =========================================================================


def test_workflow(name: str) -> dict:
    """测试工作流编排逻辑（mock 所有 action，验证步骤链路）

    与 --dry-run 的区别:
      --dry-run: 跳过执行，只打印步骤名
      test:     完整验证编排管线（加载→校验→步骤解析→后端解析→mock执行）

    验证项目:
      - 工作流定义加载正确
      - 所有步骤的 action 名可解析
      - 步骤顺序正确
      - 后端可解析
      - X1-X4 治理管线完整
      - 全部 mock 通过（0 failed = 编排正确）
    """
    from ecos.workflow.backend_registry import resolve as resolve_backend
    from ecos.workflow.loader import load_workflow
    from ecos.workflow.validator import validate_workflow

    wf = load_workflow(name)
    if not wf:
        return {"error": f"工作流不存在: {name}", "passed": 0, "failed": 0}

    wf_name = wf.get("name", name)
    is_m1 = wf.get("type") == "Workflow"

    results: dict = {
        "workflow": name,
        "display": wf_name,
        "source": "m1" if is_m1 else "definition",
        "steps": [],
        "passed": 0,
        "failed": 0,
        "warnings": [],
        "started": datetime.now().isoformat(),
    }

    print(f"🧪 测试工作流: {wf_name}")
    if wf.get("description"):
        print(f"   描述: {wf['description']}")
    print(f"   步骤数: {len(wf.get('steps', []))}")
    print()

    # ── 1. 治理校验 (X1-X4) ──
    m1_node = dict(wf)
    if "execution" not in m1_node:
        m1_node["execution"] = {}
    m1_node["source"] = "m1" if is_m1 else "definition"

    violations = validate_workflow(m1_node)
    errors = [v for v in violations if v.get("severity") == "error"]
    warnings = [v for v in violations if v.get("severity") != "error"]

    if errors:
        print(f"  ❌  治理违规 ({len(errors)}):")
        for v in errors:
            print(f"      [{v.get('id', '?')}] {v['message']}")
            results["warnings"].append(v["message"])
        results["failed"] = len(errors)
        results["finished"] = datetime.now().isoformat()
        return results

    for v in warnings:
        print(f"  ⚠️  [{v.get('id', '?')}] {v['message']}")
        results["warnings"].append(v["message"])

    # ── 2. 后端解析验证 ──
    backend_name = (
        wf.get("execution", {}).get("backend")
        or wf.get("execution", {}).get("mode")
        or "default"
    )
    try:
        backend_fn = resolve_backend(m1_node)
        assert callable(backend_fn), "后端不可调用"
        print(f"  ✅  backend 解析: {backend_name}")
    except Exception as e:  # defensive fallback
        print(f"  ❌  backend 解析失败 ({backend_name}): {e}")
        results["failed"] += 1
        results["finished"] = datetime.now().isoformat()
        return results

    # ── 3. Mock 执行所有步骤 ──
    steps = wf.get("steps", [])
    from ecos.workflow.actions import resolve_action

    for i, step in enumerate(steps, 1):
        step_name = step.get("name", f"step-{i}")
        action = step.get("action", "")
        deps = step.get("depends_on", [])

        # 验证 action 名可解析
        handler = resolve_action(action)
        if handler is None:
            print(
                f"  ❌  [{i}/{len(steps)}] {step_name:25s}  action 不可解析: {action}"
            )
            results["steps"].append(
                {
                    "name": step_name,
                    "status": "failed",
                    "action": action,
                    "error": f"未知动作: {action}",
                }
            )
            results["failed"] += 1
            continue

        dep_info = f"  (依赖: {', '.join(deps)})" if deps else ""
        print(f"  ✅  [{i}/{len(steps)}] {step_name:25s}  {action}{dep_info}")

        results["steps"].append(
            {
                "name": step_name,
                "status": "ok",
                "action": action,
                "result": {"passed": True, "summary": "✅ (mock)"},
                "depends_on": deps,
            }
        )
        results["passed"] += 1

    # ── 4. 依赖链验证 ──
    step_names = {s["name"] for s in steps if s.get("name")}
    unresolved_deps = []
    for step in steps:
        for dep in step.get("depends_on", []):
            if dep not in step_names:
                unresolved_deps.append(dep)
                print(f"  ⚠️  未解析依赖: {dep} (步骤 {step.get('name', '?')})")

    if unresolved_deps:
        results["warnings"].append(f"未解析依赖: {', '.join(unresolved_deps)}")
        print(f"  ⚠️  共 {len(unresolved_deps)} 个未解析依赖")

    # ── 完成 ──
    results["finished"] = datetime.now().isoformat()

    print()
    print(f"{'=' * 50}")
    print("  测试结果:")
    print(
        f"    步骤:        {len(steps)} 总 / {results['passed']} ✅ / {results['failed']} ❌"
    )
    print(f"    违规:        {len(errors)} error / {len(warnings)} warning")
    print(f"    后端:        {backend_name}")
    print(f"    未解析依赖:   {len(unresolved_deps)}")
    print(f"{'=' * 50}")

    if results["failed"] == 0:
        print("  ✅  编排验证通过，所有 mock 步骤执行成功。")
    else:
        print(f"  ❌  编排验证失败: {results['failed']} 个问题。")

    return results
