"""cockpit.chain.runner — chain 执行引擎.

执行模型: subprocess 调 cockpit 自身 (优先 shutil.which("cockpit"), 回退 sys.executable -m cockpit).
exec_cmd 可注入 (测试用 fake executor).
状态落盘: <workspace>/data/chain-runs/<run_id>/state.json.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from cockpit.chain.context import ChainConditionError, ChainTemplateError, evaluate_condition, render_template
from cockpit.chain.spec import ChainSpec, ChainStep

ExecCmd = Callable[[list[str], int | None, dict[str, str]], dict[str, Any]]


def _cockpit_base_argv() -> list[str] | None:
    which = shutil.which("cockpit")
    if which:
        return [which]
    return None


def default_exec_cmd(argv: list[str], timeout: int | None, env: dict[str, str]) -> dict[str, Any]:
    base = _cockpit_base_argv()
    full = [*base, *argv] if base else [sys.executable, "-m", "cockpit", *argv]
    try:
        proc = subprocess.run(
            full,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **env},
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": f"timeout after {timeout}s"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_run_id() -> str:
    # run_id 仅用于目录命名, 非安全用途, 伪随机足够
    return f"chain-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{random.randint(1000, 9999)}"  # noqa: S311


def runs_dir() -> Path:
    from cockpit.commands.delegation import workspace_root

    d = workspace_root() / "data" / "chain-runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _build_ctx(spec: ChainSpec, params: dict[str, Any], steps_state: dict[str, Any], prev: dict[str, Any] | None) -> dict[str, Any]:
    resolved_params: dict[str, Any] = {}
    for k, meta in spec.params.items():
        resolved_params[k] = params.get(k, meta.get("default"))
    return {"params": resolved_params, "env": dict(os.environ), "steps": steps_state, "prev": prev or {}}


def _condition_ctx(ctx: dict[str, Any]) -> dict[str, Any]:
    """条件求值 ctx: steps.<n>.stdout 转 json (若可), 其余直传."""
    cond = {"params": ctx["params"], "env": ctx["env"], "prev": ctx["prev"], "steps": {}}
    for name, st in ctx["steps"].items():
        if not isinstance(st, dict) or name.startswith("ref:"):
            continue
        entry: dict[str, Any] = {"exit_code": st.get("exit_code"), "stdout": st.get("stdout", ""), "stderr": st.get("stderr", "")}
        try:
            entry["json"] = json.loads(st.get("stdout", "") or "null")
        except json.JSONDecodeError:
            pass
        cond["steps"][name] = entry
    return cond


def _render_step(step: ChainStep, ctx: dict[str, Any]) -> ChainStep:
    rendered = ChainStep(**asdict(step))
    rendered.command = render_template(step.command, ctx)
    rendered.args = [render_template(a, ctx) for a in step.args]
    return rendered


def _state_path(run_dir: Path) -> Path:
    return run_dir / "state.json"


def _save_state(run_dir: Path, state: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _state_path(run_dir).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state(run_id: str) -> dict[str, Any] | None:
    p = runs_dir() / run_id / "state.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _hitl_prompt(h: dict[str, Any], non_interactive: bool) -> bool:
    prompt = h.get("prompt", f"继续执行 {h.get('at')}?")
    on_timeout = h.get("on_timeout", "abort")
    if non_interactive:
        print(f"[HITL] {prompt} (--non-interactive, 默认继续)")
        return True
    try:
        answer = input(f"[HITL] {prompt} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer in ("y", "yes", ""):
        return True
    print(f"[HITL] 用户拒绝/超时, on_timeout={on_timeout} → {'abort' if on_timeout == 'abort' else 'continue'}")
    return on_timeout != "abort"


def dry_run_chain(spec: ChainSpec, params: dict[str, Any] | None = None) -> int:
    """打印每步计划, 不执行不落盘. 未执行步骤变量显示 <pending>."""
    steps_state: dict[str, Any] = {}
    params = params or {}
    print(f"[dry-run] chain={spec.id} name={spec.name} timeout={spec.timeout}s on_chain_failure={spec.on_chain_failure}")
    for i, step in enumerate(spec.steps):
        ctx = _build_ctx(spec, params, steps_state, steps_state.get("prev"))
        when_display = "always"
        if step.when:
            try:
                ok = evaluate_condition(step.when, _condition_ctx(ctx))
                when_display = f"{step.when} → {'✓执行' if ok else '✗跳过'}"
            except (ChainConditionError, ChainTemplateError) as e:
                when_display = f"{step.when} → <pending> ({e})"
        try:
            rendered = _render_step(step, ctx)
            cmd_display = " ".join(rendered.argv())
        except ChainTemplateError:
            cmd_display = " ".join(step.argv()) + "  (含 <pending> 变量)"
        print(f"  {i + 1}. [{step.name}] {cmd_display}  (when: {when_display}; on_failure: {step.on_failure})")
    print("[dry-run] 未执行任何命令, 未落盘")
    return 0


def run_chain(
    spec: ChainSpec,
    *,
    dry_run: bool = False,
    resume_run_id: str | None = None,
    force_rerun: bool = False,
    non_interactive: bool = False,
    params: dict[str, Any] | None = None,
    exec_cmd: ExecCmd | None = None,
) -> int:
    """执行 chain, 返回最终退出码."""
    if dry_run:
        return dry_run_chain(spec, params)
    exec_cmd = exec_cmd or default_exec_cmd
    params = params or {}

    run_id = resume_run_id or _new_run_id()
    run_dir = runs_dir() / run_id
    if resume_run_id:
        prior = _load_state(resume_run_id)
        if prior is None:
            print(f"[chain] resume 失败: 未找到 run {resume_run_id}")
            return 2
        state = prior
        if force_rerun:
            state["steps_state"] = {}
        steps_state: dict[str, Any] = state.get("steps_state", {})
        state["resumed_at"] = _now()
    else:
        steps_state = {}
        state = {
            "run_id": run_id,
            "chain_id": spec.id,
            "started_at": _now(),
            "params": params,
            "steps_state": steps_state,
            "status": "running",
        }

    hitl_map = {h.get("at"): h for h in spec.hitl}
    chain_failed = False
    final_rc = 0
    chain_deadline = time.monotonic() + spec.timeout

    for step in spec.steps:
        # resume: 跳过已 succeeded
        if not force_rerun and steps_state.get(step.name, {}).get("status") == "succeeded":
            print(f"  [=] {step.name}: succeeded (resume 跳过)")
            continue

        prev = next((steps_state[s.name] for s in spec.steps[: spec.steps.index(step)][::-1] if s.name in steps_state), None)
        ctx = _build_ctx(spec, params, steps_state, prev)

        # HITL: 执行到该步前阻塞
        if step.name in hitl_map:
            ok = _hitl_prompt(hitl_map[step.name], non_interactive)
            if not ok:
                state["status"] = "aborted"
                state["aborted_at"] = step.name
                state["ended_at"] = _now()
                _save_state(run_dir, state)
                print(f"[chain] HITL abort at '{step.name}'")
                return 1

        # when 条件
        if step.when:
            try:
                if not evaluate_condition(step.when, _condition_ctx(ctx)):
                    steps_state[step.name] = {"name": step.name, "status": "skipped", "exit_code": None, "stdout": "", "stderr": "", "started_at": _now(), "ended_at": _now()}
                    _save_state(run_dir, state)
                    print(f"  [-] {step.name}: skipped (when 不满足)")
                    continue
            except (ChainConditionError, ChainTemplateError) as e:
                steps_state[step.name] = {"name": step.name, "status": "error", "exit_code": None, "stdout": "", "stderr": f"when 求值失败: {e}", "started_at": _now(), "ended_at": _now()}
                _save_state(run_dir, state)
                print(f"  [!] {step.name}: when 求值失败 → {e}")
                if spec.on_chain_failure == "abort":
                    state["status"] = "aborted"
                    state["ended_at"] = _now()
                    _save_state(run_dir, state)
                    return 1
                continue

        # 渲染模板
        try:
            rendered = _render_step(step, ctx)
        except ChainTemplateError as e:
            steps_state[step.name] = {"name": step.name, "status": "error", "exit_code": None, "stdout": "", "stderr": f"模板渲染失败: {e}", "started_at": _now(), "ended_at": _now()}
            _save_state(run_dir, state)
            print(f"  [!] {step.name}: 模板渲染失败 → {e}")
            if spec.on_chain_failure == "abort":
                state["status"] = "aborted"
                state["ended_at"] = _now()
                _save_state(run_dir, state)
                return 1
            continue

        # 执行 (含 retry)
        attempts = step.retry_max + 1
        result: dict[str, Any] | None = None
        attempt = 0
        started_at = _now()
        while attempt < attempts:
            if time.monotonic() > chain_deadline:
                steps_state[step.name] = {"name": step.name, "status": "timeout", "exit_code": -1, "stdout": "", "stderr": "chain timeout", "started_at": started_at, "ended_at": _now()}
                _save_state(run_dir, state)
                print(f"  [T] {step.name}: chain 总超时")
                state["status"] = "timeout"
                state["ended_at"] = _now()
                _save_state(run_dir, state)
                return 1
            attempt += 1
            step_timeout = step.timeout or spec.timeout
            result = exec_cmd(rendered.argv(), step_timeout, {})
            if result["exit_code"] == 0:
                break
            if attempt < attempts:
                print(f"  [r] {step.name}: 失败 (rc={result['exit_code']}), {step.retry_backoff}s 后重试 {attempt}/{step.retry_max}")
                time.sleep(step.retry_backoff)

        assert result is not None
        ok = result["exit_code"] == 0
        status = "succeeded" if ok else ("failed" if attempt >= attempts else "failed")
        steps_state[step.name] = {
            "name": step.name,
            "status": status,
            "exit_code": result["exit_code"],
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "attempts": attempt,
            "started_at": started_at,
            "ended_at": _now(),
        }
        if step.capture_output_to:
            steps_state[f"ref:{step.capture_output_to}"] = step.name
        _save_state(run_dir, state)
        marker = "[+]" if ok else "[x]"
        print(f"  {marker} {step.name}: {status} (rc={result['exit_code']}, attempts={attempt})")
        out = (result.get("stdout") or "").strip()
        if out:
            print("      " + out.replace("\n", "\n      ")[:2000])

        if not ok:
            final_rc = result["exit_code"] or 1
            if step.on_failure == "abort" or spec.on_chain_failure == "abort" and step.on_failure != "continue":
                state["status"] = "aborted"
                state["aborted_at"] = step.name
                state["ended_at"] = _now()
                _save_state(run_dir, state)
                print(f"[chain] abort at '{step.name}' (rc={final_rc})")
                return final_rc
            if step.on_failure == "continue":
                chain_failed = True
                print("      on_failure=continue, 继续后续步骤")

    state["status"] = "failed" if chain_failed else "succeeded"
    state["ended_at"] = _now()
    state["final_rc"] = final_rc
    _save_state(run_dir, state)
    print(f"[chain] {state['status']} run_id={run_id} state={_state_path(run_dir)}")
    return final_rc if chain_failed else 0


def parse_params(pairs: list[str]) -> dict[str, str]:
    """--param k=v 列表 → dict."""
    out: dict[str, str] = {}
    for p in pairs or []:
        if "=" not in p:
            raise ValueError(f"--param 须为 k=v 形式: {p}")
        k, v = p.split("=", 1)
        out[k] = v
    return out
