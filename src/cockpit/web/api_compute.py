"""Compute Governance Summary API endpoints.

提供 AetherForge 算力大盘并网自愈与网络唤醒接口。

Routes:
    GET  /api/governance/compute/status  → 算力网格与网关状态概览
    POST /api/governance/compute/wakeup  → 网络唤醒物理从机节点 (WoL)
"""

from __future__ import annotations

import json
import os
import re
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
        raise HTTPException(status_code=503, detail="Compute workspace is unavailable.")

    onboard_script = root / "bin" / "gac-compute-onboard.py"
    if not onboard_script.is_file():
        raise HTTPException(status_code=503, detail="Compute onboarding capability is not mounted.")

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
            raise HTTPException(status_code=503, detail=f"Compute onboarding is unavailable: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Compute status check timed out.")
    except HTTPException:
        raise
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Compute onboarding returned invalid JSON: {exc}") from exc
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Compute status is unavailable: {str(e)}") from e


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


OMLX_BIN = "/Volumes/Model/omlx/bin/omlx"


class ModelActionRequest(BaseModel):
    model: str
    action: str = "load"  # load | unload


def _omlx_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    return env


@router.get("/api/governance/compute/models")
async def list_compute_models():
    """三机本地算力模型清单 —— 来自 SSOT(能力/位置/成本)+ omlx 实时 loaded 态。"""
    root = get_workspace_root()
    if not root:
        raise HTTPException(status_code=500, detail="Cannot locate workspace root.")

    # 1) SSOT: 能力 / runs_on / 成本(omlxc ssot-sync 生成)
    ssot_models: list[dict[str, Any]] = []
    ssot_path = root / "projects/ecos/src/ecos/ssot/mof/m1/model" / "MODEL-BREW-OMLX-LOCAL.yaml"
    if ssot_path.is_file():
        try:
            import yaml

            data = yaml.safe_load(ssot_path.read_text(encoding="utf-8")) or {}
            ssot_models = data.get("models", []) or []
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读 SSOT 失败: {e}")

    # 2) omlx: 各节点实时加载态
    loaded: dict[str, list[str]] = {}
    try:
        r = subprocess.run([OMLX_BIN, "node", "ps"], env=_omlx_env(), capture_output=True, text=True, timeout=30)
        cur = None
        for line in (r.stdout or "").splitlines():
            raw = re.sub(r"\x1b\[[0-9;]*m", "", line)
            s = raw.strip()
            if not s:
                continue
            if not raw.startswith(" "):  # 节点行
                cur = s.split("—")[0].strip()
                loaded.setdefault(cur, [])
            elif cur:
                # "● key :port (engine)" 或 "lmstudio :1234 — a, b"
                if "—" in s:
                    tail = s.split("—", 1)[1].strip()
                    if tail and "空闲" not in tail and "down" not in tail:
                        loaded[cur].extend(x.strip() for x in tail.split(","))
                elif s.startswith("●"):
                    parts = s.replace("●", "").strip().split()
                    if parts:
                        loaded[cur].append(parts[0])
    except Exception:
        pass  # 实时态拿不到不影响清单

    return {
        "status": "success",
        "total": len(ssot_models),
        "models": ssot_models,
        "loaded_by_node": loaded,
    }


@router.post("/api/governance/compute/model-action")
async def compute_model_action(req: ModelActionRequest):
    """加载/卸载模型 —— 自动判断本地或远程节点(经 omlxc load/unload)。"""
    if req.action not in ("load", "unload"):
        raise HTTPException(status_code=400, detail="action 必须是 load 或 unload")
    try:
        r = subprocess.run(
            [OMLX_BIN, req.action, req.model], env=_omlx_env(), capture_output=True, text=True, timeout=300
        )
        out = re.sub(r"\x1b\[[0-9;]*m", "", (r.stdout or "") + (r.stderr or ""))
        return {
            "status": "success" if r.returncode == 0 else "failed",
            "action": req.action,
            "model": req.model,
            "output": out.strip()[-400:],
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"{req.action} 超时(大模型加载较慢)")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{req.action} 失败: {e}")


class FabricTriageRequest(BaseModel):
    prompt: str


class FabricVRAMRequest(BaseModel):
    model_id: str = "coding"
    context_tokens: int = 32768


class FabricWarmRequest(BaseModel):
    model_id: str = "coding"


@router.get("/api/governance/compute/fabric")
async def get_compute_fabric():
    """获取 omlxc 算力织网实时全景（温控、分诊分级、显存预算与两级缓存）。"""
    root = get_workspace_root()
    if not root:
        raise HTTPException(status_code=500, detail="Cannot locate workspace root.")
    omlxc_root = root / "projects" / "omlxc"
    try:
        r = subprocess.run(
            ["uv", "run", "omlxc", "fabric", "inspect", "--json"],
            cwd=str(omlxc_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
        raise HTTPException(status_code=500, detail=f"Fabric inspect failed: {r.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fabric error: {e}")


@router.post("/api/governance/compute/fabric/warm")
async def compute_fabric_warm(req: FabricWarmRequest):
    """预热系统 Prompt 前缀缓存以实现 0ms TTFT。"""
    root = get_workspace_root()
    if not root:
        raise HTTPException(status_code=500, detail="Cannot locate workspace root.")
    omlxc_root = root / "projects" / "omlxc"
    try:
        r = subprocess.run(
            ["uv", "run", "omlxc", "fabric", "warm", "--model", req.model_id, "--json"],
            cwd=str(omlxc_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
        raise HTTPException(status_code=500, detail=f"Fabric warm failed: {r.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fabric warm error: {e}")


@router.post("/api/governance/compute/fabric/triage")
async def compute_fabric_triage(req: FabricTriageRequest):
    """意图复杂度分诊分析。"""
    root = get_workspace_root()
    if not root:
        raise HTTPException(status_code=500, detail="Cannot locate workspace root.")
    omlxc_root = root / "projects" / "omlxc"
    try:
        r = subprocess.run(
            ["uv", "run", "omlxc", "fabric", "triage", req.prompt, "--json"],
            cwd=str(omlxc_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
        raise HTTPException(status_code=500, detail=f"Fabric triage failed: {r.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fabric triage error: {e}")


@router.post("/api/governance/compute/fabric/vram")
async def compute_fabric_vram(req: FabricVRAMRequest):
    """动态 KV Cache 显存预算评估与准入判定。"""
    root = get_workspace_root()
    if not root:
        raise HTTPException(status_code=500, detail="Cannot locate workspace root.")
    omlxc_root = root / "projects" / "omlxc"
    try:
        r = subprocess.run(
            ["uv", "run", "omlxc", "fabric", "vram", req.model_id, str(req.context_tokens), "--json"],
            cwd=str(omlxc_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
        raise HTTPException(status_code=500, detail=f"Fabric vram failed: {r.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fabric vram error: {e}")
