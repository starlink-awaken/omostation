"""Compute Governance Summary API endpoints.

提供 AetherForge 算力大盘并网自愈与网络唤醒接口。

Routes:
    GET  /api/governance/compute/status  → 算力网格与网关状态概览
    POST /api/governance/compute/wakeup  → 网络唤醒物理从机节点 (WoL)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class WakeupRequest(BaseModel):
    node_id: str


def get_workspace_root() -> Path | None:
    """动态定位 workspace 根目录"""
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            return parent
    return None


def get_aetherforge_env(workspace_root: Path) -> dict[str, str]:
    """生成包含 aetherforge 路径的 PYTHONPATH 环境变量"""
    env = os.environ.copy()
    aether_src = workspace_root / "projects" / "aetherforge" / "src"
    gateway_src = workspace_root / "projects" / "aetherforge" / "packages" / "gateway" / "src"
    mesh_src = workspace_root / "projects" / "aetherforge" / "packages" / "mesh" / "src"

    paths = []
    if aether_src.is_dir():
        paths.append(str(aether_src))
    if gateway_src.is_dir():
        paths.append(str(gateway_src))
    if mesh_src.is_dir():
        paths.append(str(mesh_src))

    if paths:
        existing = env.get("PYTHONPATH", "")
        if existing:
            env["PYTHONPATH"] = os.pathsep.join(paths) + os.pathsep + existing
        else:
            env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


@router.get("/api/governance/compute/status")
async def get_compute_status():
    """获取算力网格、LiteLLM 路由与凭据额度并网状态。"""
    root = get_workspace_root()
    if not root:
        raise HTTPException(status_code=500, detail="Cannot locate workspace root.")

    onboard_script = root / "bin" / "gac-compute-onboard.py"
    if not onboard_script.is_file():
        raise HTTPException(status_code=500, detail="Compute onboarding script not found.")

    # 运行 bin/gac-compute-onboard.py --json
    cmd = [sys.executable, str(onboard_script), "--json"]
    env = get_aetherforge_env(root)

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            # 即使脚本出错，我们也返回错误信息做防线
            raise HTTPException(
                status_code=500, detail=f"Onboard script failed with code {result.returncode}: {result.stderr.strip()}"
            )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Compute status check timed out.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check compute status: {str(e)}")


@router.post("/api/governance/compute/wakeup")
async def wakeup_compute_node(req: WakeupRequest):
    """通过 Wake-on-LAN 发送 Magic Packet 唤醒离线从机节点。"""
    root = get_workspace_root()
    if not root:
        raise HTTPException(status_code=500, detail="Cannot locate workspace root.")

    # 优先将 node_id 映射到项目注册表 compute_nodes
    # 比如如果是 'ENG-OLLAMA-MACMINI'，底层 wakeup_node 会自动解析包含 'MACMINI' 的硬件并发出 WoL
    # 我们可以直接调用 cockpit compute mesh wakeup <node_id>

    # 构造执行命令: python3 -m aetherforge.cli mesh wakeup <node_id>
    cmd = [sys.executable, "-m", "aetherforge.cli", "mesh", "wakeup", req.node_id]
    env = get_aetherforge_env(root)

    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"Wakeup packet successfully sent to node '{req.node_id}'.",
                "stdout": result.stdout.strip(),
            }
        else:
            return {
                "success": False,
                "message": f"Wakeup script failed for node '{req.node_id}'.",
                "stderr": result.stderr.strip(),
                "stdout": result.stdout.strip(),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute wakeup: {str(e)}")


class ComputeGenerateRequest(BaseModel):
    prompt: str
    model: str = "coder"


@router.post("/api/governance/compute/generate")
async def compute_generate(req: ComputeGenerateRequest):
    """经本地算力集群生成文本 — bos://capability/compute/generate → AetherForge → omlx。

    model 为网关模型名 (裸名如 coder / mini-9b 优先本地 omlx; 或 ENG-*/model 全名)。
    """
    root = get_workspace_root()
    if not root:
        raise HTTPException(status_code=500, detail="Cannot locate workspace root.")

    # 用 uv run 跑 aetherforge 自己的 venv (依赖齐全), 调 gateway.rpc.run_generate = BOS compute/generate 同一入口
    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    code = (
        "import json,sys;"
        "from aetherforge.gateway.rpc import run_generate;"
        "print(json.dumps(run_generate(sys.argv[1], model=sys.argv[2]), ensure_ascii=False))"
    )
    cmd = [
        "uv",
        "run",
        "--directory",
        str(root / "projects" / "aetherforge"),
        "python",
        "-c",
        code,
        req.prompt,
        req.model,
    ]

    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip().splitlines()[-1])
        raise HTTPException(
            status_code=500,
            detail=f"Compute generate failed: {result.stderr.strip()[-300:] or 'no output'}",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Compute generate timed out.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compute generate error: {str(e)}")
