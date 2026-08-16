"""CircuitEngine — 回路状态机执行：YAML 解析、拓扑排序编排、SLA 超时、即发即忘、重试。"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import yaml

from core_models.protocols.circuit import CircuitDefinition, CircuitRun, CircuitStep, FailureAction


@dataclass
class _StepState:
    """每个步骤的运行时状态。"""

    step: CircuitStep
    status: str = "pending"  # pending|running|completed|failed|skipped
    attempt: int = 0
    started_at: float = 0.0
    completed_at: float = 0.0
    error: str = ""


class CircuitEngine:
    """回路执行引擎。用法: engine = CircuitEngine(); defn = engine.load_circuit("a.circuit"); run = await engine.execute_circuit(defn, ctx={})"""

    def __init__(self) -> None:
        self._runs: dict[str, CircuitRun] = {}
        self._step_states: dict[str, dict[str, _StepState]] = {}  # run_id -> {step_id -> _StepState}
        self._cancel_signals: dict[str, asyncio.Event] = {}

    # ── YAML Loader ──────────────────────────────────────────────

    def load_circuit(self, path: str | Path) -> CircuitDefinition:
        """从 .circuit YAML 文件加载回路定义。"""
        raw = Path(path).read_text(encoding="utf-8")
        return self.parse_circuit(raw)

    def parse_circuit(self, yaml_text: str) -> CircuitDefinition:
        """从 YAML 文本解析回路定义。"""
        data = yaml.safe_load(yaml_text) or {}
        steps_data: list[dict] = data.get("steps", [])
        sla: dict = data.get("sla", {})

        steps: list[CircuitStep] = []
        for sd in steps_data:
            retry: dict = sd.get("retry", {}) or {}
            steps.append(
                CircuitStep(
                    id=sd["id"],
                    neuron=sd.get("neuron", ""),
                    action=sd.get("action", ""),
                    depends_on=sd.get("depends_on", []) or [],
                    condition=sd.get("condition", ""),
                    on_failure=FailureAction(sd.get("on_failure", "reject")),
                    fire_and_forget=sd.get("fire_and_forget", False),
                    retry_max_attempts=retry.get("max_attempts", 0),
                    retry_backoff_ms=retry.get("backoff_ms", 100),
                    params=sd.get("params", {}) or {},
                )
            )

        return CircuitDefinition(
            name=data.get("name", "unnamed"),
            version=str(data.get("version", "1.0")),
            description=data.get("description", ""),
            trigger=data.get("trigger", ""),
            sla_p99_ms=sla.get("p99_ms", 100),
            sla_timeout_ms=sla.get("timeout_ms", 1000),
            steps=steps,
        )

    # ── State Machine Executor ───────────────────────────────────

    async def execute_circuit(self, circuit: CircuitDefinition, context: dict | None = None) -> CircuitRun:
        """执行回路，按依赖顺序执行步骤。"""
        ctx = context or {}
        run = CircuitRun(
            run_id=str(uuid.uuid4()),
            circuit_name=circuit.name,
            status="running",
            started_at=time.monotonic(),
        )
        self._runs[run.run_id] = run
        cancel_evt = asyncio.Event()
        self._cancel_signals[run.run_id] = cancel_evt

        step_states: dict[str, _StepState] = {}
        for s in circuit.steps:
            step_states[s.id] = _StepState(step=s)
        self._step_states[run.run_id] = step_states

        try:
            # 总的 SLA 超时
            total_timeout = circuit.sla_timeout_ms / 1000.0 if circuit.sla_timeout_ms > 0 else None
            await asyncio.wait_for(
                self._execute_steps(circuit, ctx, run, step_states, cancel_evt),
                timeout=total_timeout,
            )
        except TimeoutError:
            if run.status not in ("completed", "failed"):
                run.status = "failed"
                run.error = f"SLA timeout exceeded ({circuit.sla_timeout_ms}ms)"
        except asyncio.CancelledError:
            run.status = "failed"
            run.error = "Circuit cancelled"
        except Exception as exc:
            run.status = "failed"
            run.error = f"Circuit error: {exc}"
        finally:
            if run.status == "running":
                run.status = "completed"
            run.completed_at = time.monotonic()
            self._cancel_signals.pop(run.run_id, None)

        return run

    async def _execute_steps(
        self,
        circuit: CircuitDefinition,
        ctx: dict,
        run: CircuitRun,
        step_states: dict[str, _StepState],
        cancel_evt: asyncio.Event,
    ) -> None:
        """按拓扑序执行所有步骤。"""
        # 构建依赖图
        step_map: dict[str, CircuitStep] = {s.id: s for s in circuit.steps}
        indegree: dict[str, int] = {s.id: len(s.depends_on) for s in circuit.steps}
        dependents: dict[str, list[str]] = {s.id: [] for s in circuit.steps}
        ready_queue: deque[str] = deque()

        for s in circuit.steps:
            for dep in s.depends_on:
                if dep in dependents:
                    dependents[dep].append(s.id)

        for sid, deg in indegree.items():
            if deg == 0:
                ready_queue.append(sid)

        # 用于跟踪哪些步骤已解析（成功/跳过）
        resolved: set[str] = set()
        # 即发即忘任务
        fire_tasks: set[asyncio.Task] = set()

        while ready_queue or fire_tasks:
            if cancel_evt.is_set():
                run.status = "failed"
                run.error = "Cancelled by user"
                return

            # 等待已完成的即发即忘任务，也允许取消
            if fire_tasks:
                done, fire_tasks = await self._wait_any_fire_task(fire_tasks, cancel_evt)
                if cancel_evt.is_set():
                    return
                # done 中的任务即使失败也已处理（在 _execute_one_step 中已记录）
                continue

            # 所有就绪步骤都已调度，等待即发即忘任务
            if not ready_queue:
                if fire_tasks:
                    await asyncio.sleep(0.01)
                    continue
                break

            sid = ready_queue.popleft()

            # 检查 condition
            step = step_map[sid]
            if step.condition:
                if not self._eval_condition(step.condition, ctx):
                    st = step_states[sid]
                    st.status = "skipped"
                    st.completed_at = time.monotonic()
                    resolved.add(sid)
                    self._release_dependents(sid, dependents, indegree, ready_queue, resolved)
                    continue

            st = step_states[sid]
            if step.fire_and_forget:
                # 即发即忘：不阻塞，立即释放依赖它的步骤
                resolved.add(sid)
                self._release_dependents(sid, dependents, indegree, ready_queue, resolved)
                task = asyncio.create_task(self._execute_one_step(step, st, ctx, cancel_evt))
                fire_tasks.add(task)
            else:
                run.current_step = sid
                success = await self._execute_one_step(step, st, ctx, cancel_evt)
                if not success and step.on_failure == FailureAction.REJECT:
                    run.status = "failed"
                    run.error = f"Step '{sid}' failed and on_failure=reject"
                    return
                resolved.add(sid)
                self._release_dependents(sid, dependents, indegree, ready_queue, resolved)

        # 等待所有即发即忘任务完成
        if fire_tasks:
            remaining = asyncio.gather(*fire_tasks, return_exceptions=True)
            await remaining

        # 检查是否所有步骤都已处理
        pending = [sid for sid, st in step_states.items() if st.status == "pending"]
        if pending:
            run.status = "failed"
            run.error = f"Circuit incomplete: steps {pending} could not be resolved (circular dependency?)"
            return

    async def _wait_any_fire_task(
        self, tasks: set[asyncio.Task], cancel_evt: asyncio.Event
    ) -> tuple[set[asyncio.Task], set[asyncio.Task]]:
        """等待任意一个即发即忘任务完成，同时监听取消信号。"""
        if not tasks:
            return set(), tasks
        wait_tasks = set(tasks) | {asyncio.create_task(cancel_evt.wait())}
        done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
        # 移除取消信号任务
        cancel_task = None
        for t in done:
            if t not in tasks:
                cancel_task = t
                break
        if cancel_task:
            done.discard(cancel_task)
            # 取消取消信号等待任务
            for t in pending:
                if t not in tasks:
                    t.cancel()
                    break
            return done, pending & tasks
        return done, pending & tasks

    async def _execute_one_step(
        self,
        step: CircuitStep,
        st: _StepState,
        ctx: dict,
        cancel_evt: asyncio.Event,
    ) -> bool:
        """执行单个步骤，含重试逻辑。返回 True 表示成功或可容忍失败。"""
        max_attempts = max(1, step.retry_max_attempts + 1)
        for attempt in range(1, max_attempts + 1):
            if cancel_evt.is_set():
                st.status = "failed"
                st.error = "Cancelled"
                return False
            st.attempt = attempt
            st.status = "running"
            st.started_at = time.monotonic()
            try:
                await self._invoke_step(step, ctx)
                st.status = "completed"
                st.completed_at = time.monotonic()
                return True
            except Exception as exc:
                st.error = str(exc)
                if attempt < max_attempts:
                    backoff = step.retry_backoff_ms / 1000.0
                    await asyncio.sleep(backoff)
                else:
                    st.status = "failed"
                    st.completed_at = time.monotonic()
                    if step.on_failure == FailureAction.SKIP:
                        st.status = "skipped"
                        return True
                    return False
        return False

    async def _invoke_step(self, step: CircuitStep, ctx: dict) -> None:
        """调用步骤实现。子类可覆写以接入神经元调用。默认是空操作桩。"""
        await asyncio.sleep(0)

    # ── Condition Evaluator ──────────────────────────────────────

    def _eval_condition(self, condition: str, ctx: dict) -> bool:
        """评估条件。支持 ``"${var}"``、``"${var} == val"``、``"${var} != val"``。"""
        cond = condition.strip()
        if not cond.startswith("${"):
            return bool(cond)
        # 提取变量引用
        end = cond.find("}")
        if end < 0:
            return bool(ctx.get(cond, False))
        ref = cond[2:end]
        remainder = cond[end + 1 :].strip()
        if not remainder:
            return bool(ctx.get(ref, False))
        # 二元比较
        if "==" in remainder:
            _, _, rhs = remainder.partition("==")
            return str(ctx.get(ref)) == rhs.strip().strip("'\"")
        if "!=" in remainder:
            _, _, rhs = remainder.partition("!=")
            return str(ctx.get(ref)) != rhs.strip().strip("'\"")
        return bool(ctx.get(ref, False))

    # ── Dependency resolution helpers ────────────────────────────

    @staticmethod
    def _release_dependents(
        sid: str,
        dependents: dict[str, list[str]],
        indegree: dict[str, int],
        ready_queue: deque[str],
        resolved: set[str],
    ) -> None:
        """递减依赖计数，将入度归零的步骤加入就绪队列。"""
        for dep_id in dependents.get(sid, []):
            indegree[dep_id] = indegree.get(dep_id, 0) - 1
            if indegree[dep_id] <= 0 and dep_id not in resolved:
                ready_queue.append(dep_id)

    # ── Run status & cancel ──────────────────────────────────────

    async def get_run_status(self, run_id: str) -> CircuitRun:
        """查询回路执行状态。"""
        if run_id not in self._runs:
            raise KeyError(f"Run '{run_id}' not found")
        return self._runs[run_id]

    async def cancel_run(self, run_id: str) -> bool:
        """取消回路执行。"""
        if run_id not in self._runs:
            return False
        evt = self._cancel_signals.get(run_id)
        if evt:
            evt.set()
            return True
        return False

    def get_step_states(self, run_id: str) -> dict[str, _StepState]:
        """获取指定执行的步骤状态（调试用）。"""
        return self._step_states.get(run_id, {})
