"""Agent Runtime HTTP 服务 — 带 Bearer token 认证。"""

import json
import time
from pathlib import Path

from runtime.executor.config import AUTH_TOKEN, EXEC_LOG_FILE, log
from runtime.executor.engine import AgentRuntime, _build_alert_message, _log_execution

# ── FastAPI 应用 ──────────────────────────────────────────────────────────────


def _verify_auth(request):
    """验证 Bearer token 认证。AUTH_TOKEN 为空时不验证。"""
    if not AUTH_TOKEN:
        return
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {AUTH_TOKEN}"
    if auth_header != expected:
        from fastapi import HTTPException

        log.warning(f"⛔ Auth failed: got header={auth_header[:30]}...")
        raise HTTPException(status_code=401, detail="Unauthorized")


def create_app():
    """创建 FastAPI 应用（带可选的 Bearer Token 认证）。"""
    from fastapi import FastAPI, HTTPException, Request
    from pydantic import BaseModel

    app = FastAPI(title="Agent Runtime", version="1.0.0")
    runtime = AgentRuntime()

    # ── 中间件：认证 ──────────────────────────────────────────────────────
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # 健康检查公开放行
        if request.url.path == "/health":
            return await call_next(request)
        # AUTH_TOKEN 为空时不验证
        if not AUTH_TOKEN:
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {AUTH_TOKEN}"
        if auth != expected:
            from fastapi.responses import JSONResponse

            log.warning(f"⛔ Auth blocked: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized. Set AGENT_RUNTIME_AUTH_TOKEN env var."},
            )
        response = await call_next(request)
        return response

    # ── 请求模型 ──────────────────────────────────────────────────────────

    class TaskRequest(BaseModel):
        prompt: str = ""
        task: str = ""
        tools: list = None  # type: ignore
        context: dict = None  # type: ignore

    class ChatRequest(BaseModel):
        message: str
        history: list = None  # type: ignore
        session_id: str = ""
        context: dict = None  # type: ignore

    # ── 端点 ──────────────────────────────────────────────────────────────

    @app.get("/health")
    def health():
        return {"status": "ok", "model": runtime.model, "auth": bool(AUTH_TOKEN)}

    @app.post("/chat")
    def chat(req: ChatRequest):
        """对话模式。"""
        t0 = time.time()
        system_prompt = (
            "你是 Agent Runtime，一个 AI 助手。你可以使用工具来完成任务。\n"
            "请用中文回复。\n"
            "如果你需要执行命令、读取文件或查询系统，使用相应的工具。\n"
            "如果只是聊天，直接回复即可。"
        )

        messages = [{"role": "system", "content": system_prompt}]
        if req.history:
            for h in req.history[-20:]:
                if isinstance(h, dict) and "role" in h and "content" in h:
                    messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": req.message})

        schemas = runtime.tools.build_tool_schemas()
        max_turns = 30

        for turn in range(max_turns):
            response = runtime._call_llm(messages, tools=schemas)
            finish = response.get("finish_reason", "stop")
            if response.get("error"):
                return {
                    "response": f"抱歉，我遇到了错误: {response['error']}",
                    "turns": turn + 1,
                    "duration_sec": round(time.time() - t0, 2),
                }

            assistant_msg = dict(response)
            assistant_msg.pop("finish_reason", None)
            assistant_msg.pop("usage", None)
            assistant_msg.pop("error", None)
            messages.append(assistant_msg)
            tcs = response.get("tool_calls", [])

            if finish == "stop" or not tcs:
                return {
                    "response": response.get("content", ""),
                    "turns": turn + 1,
                    "usage": response.get("usage", {}),
                    "duration_sec": round(time.time() - t0, 2),
                }

            for tc in tcs:
                messages.append(runtime._execute_tool(tc))

        return {
            "response": messages[-1].get("content", ""),
            "turns": max_turns,
            "truncated": True,
            "duration_sec": round(time.time() - t0, 2),
        }

    @app.post("/run-task")
    def run_task(req: TaskRequest):
        """执行任务。"""
        t0 = time.time()
        prompt = req.prompt
        task_id = req.task or "custom"

        if not prompt and req.task:
            task_file = Path(__file__).parent / "task_definitions" / f"{req.task}.json"
            if task_file.exists():
                task_def = json.loads(task_file.read_text())
                prompt = task_def.get("prompt", "")
                task_id = req.task

        if not prompt:
            raise HTTPException(status_code=400, detail="prompt or task is required")

        result = runtime.run_task(prompt, tools_enabled=req.tools, context=req.context)
        elapsed = time.time() - t0

        status = "error" if "error" in result else "ok"
        summary = result.get("result", "")[:200]
        _log_execution(task_id, status, summary, result, elapsed)

        if "error" in result:
            alert = _build_alert_message(task_id, result)
            try:
                runtime.tools.send_message(text=alert)
            except Exception:
                pass
            raise HTTPException(status_code=500, detail=result["error"])

        result["duration_sec"] = round(elapsed, 2)
        return result

    @app.get("/logs")
    def get_logs(limit: int = 50):
        """返回最近的执行日志。"""
        if not EXEC_LOG_FILE.exists():
            return {"logs": []}
        lines = EXEC_LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines[-limit:]:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        entries.reverse()
        return {"logs": entries, "total": len(lines)}

    @app.get("/task-history/{task_id}")
    def get_task_history(task_id: str, limit: int = 20):
        """返回指定任务的执行历史。"""
        if not EXEC_LOG_FILE.exists():
            return {"logs": []}
        lines = EXEC_LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines[-500:]:
            try:
                entry = json.loads(line)
                if entry.get("task_id") == task_id:
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
        entries.reverse()
        return {"logs": entries[:limit], "total": len(entries)}

    return app
