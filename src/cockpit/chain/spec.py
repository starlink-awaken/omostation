"""cockpit.chain.spec — chain 声明式链路 spec 加载/校验.

搜索路径 (先命中先用):
  1. <cockpit 仓>/config/chains/*.yaml   (内置 demo)
  2. <workspace>/config/chains/*.yaml    (workspace 覆盖)
  3. ~/.workspace/chains/                (用户级)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# cockpit 仓根 (src/cockpit/chain/spec.py → 上跳 3 级)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

SPEC_SCHEMA_VERSION = 1
VALID_ON_FAILURE = {"abort", "continue", "retry"}
VALID_ON_CHAIN_FAILURE = {"abort", "continue"}


class ChainSpecError(Exception):
    """chain spec 加载/校验失败."""


@dataclass
class ChainStep:
    name: str
    command: str
    title: str = ""
    args: list[str] = field(default_factory=list)
    when: str = ""
    on_failure: str = "abort"
    retry_max: int = 0
    retry_backoff: float = 1.0
    capture_output_to: str = ""
    timeout: int | None = None

    def argv(self) -> list[str]:
        """command (可含多 token, 如 "cockpit gac") + args → argv, 去掉前导 cockpit token."""
        import shlex

        try:
            tokens = shlex.split(self.command)
        except ValueError:
            tokens = self.command.split()
        if tokens and tokens[0] == "cockpit":
            tokens = tokens[1:]
        return [*tokens, *self.args]


@dataclass
class ChainSpec:
    id: str
    version: int
    name: str
    description: str = ""
    owner: str = "cockpit"
    tags: list[str] = field(default_factory=list)
    params: dict[str, dict[str, Any]] = field(default_factory=dict)
    timeout: int = 600
    on_chain_failure: str = "abort"
    steps: list[ChainStep] = field(default_factory=list)
    hitl: list[dict[str, Any]] = field(default_factory=list)
    source_path: str = ""

    def step_names(self) -> set[str]:
        return {s.name for s in self.steps}


def search_paths() -> list[Path]:
    from cockpit.commands.delegation import workspace_root

    return [
        REPO_ROOT / "config" / "chains",
        workspace_root() / "config" / "chains",
        Path.home() / ".workspace" / "chains",
    ]


def _iter_chain_files() -> list[tuple[Path, Path]]:
    """返回 (chain_id, 路径) 列表, 按搜索路径优先级先命中先用."""
    seen: set[str] = set()
    out: list[tuple[Path, Path]] = []
    for base in search_paths():
        if not base.is_dir():
            continue
        for f in sorted(base.glob("*.yaml")):
            cid = f.stem
            if cid not in seen:
                seen.add(cid)
                out.append((cid, f))
    return out


def list_chains() -> list[str]:
    return [cid for cid, _ in _iter_chain_files()]


def chain_source(chain_id: str) -> Path | None:
    for cid, path in _iter_chain_files():
        if cid == chain_id:
            return path
    return None


def _load_raw(chain_id: str) -> tuple[dict[str, Any], Path]:
    path = chain_source(chain_id)
    if path is None:
        raise ChainSpecError(f"chain '{chain_id}' 未找到 (搜索路径: {[str(p) for p in search_paths()]})")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ChainSpecError(f"chain spec 必须是 mapping: {path}")
    return raw, path


def parse_spec(raw: dict[str, Any], source_path: str = "") -> ChainSpec:
    """dict → ChainSpec (不做完整校验, 校验走 validate_spec)."""
    steps = []
    for s in raw.get("steps", []):
        retry = s.get("retry") or {}
        steps.append(
            ChainStep(
                name=str(s.get("name", "")),
                command=str(s.get("command", "")),
                title=str(s.get("title", "")),
                args=[str(a) for a in s.get("args", [])],
                when=str(s.get("when", "")),
                on_failure=str(s.get("on_failure", "abort")),
                retry_max=int(retry.get("max", 0)),
                retry_backoff=float(retry.get("backoff", 1.0)),
                capture_output_to=str(s.get("capture_output_to", "")),
                timeout=s.get("timeout"),
            )
        )
    return ChainSpec(
        id=str(raw.get("id", "")),
        version=int(raw.get("version", SPEC_SCHEMA_VERSION)),
        name=str(raw.get("name", raw.get("id", ""))),
        description=str(raw.get("description", "")),
        owner=str(raw.get("owner", "cockpit")),
        tags=[str(t) for t in raw.get("tags", [])],
        params=dict(raw.get("params", {})),
        timeout=int(raw.get("timeout", 600)),
        on_chain_failure=str(raw.get("on_chain_failure", "abort")),
        steps=steps,
        hitl=list(raw.get("hitl", [])),
        source_path=source_path,
    )


def load_chain(chain_id: str) -> ChainSpec:
    raw, path = _load_raw(chain_id)
    return parse_spec(raw, source_path=str(path))


def validate_spec(spec: ChainSpec | dict[str, Any]) -> list[str]:
    """结构校验, 返回错误列表 (空 = 通过). 接受 ChainSpec 或 raw dict."""
    errors: list[str] = []
    if isinstance(spec, ChainSpec):
        s: ChainSpec = spec
    else:
        s = parse_spec(spec)
    if not s.id:
        errors.append("id: 必填")
    if not s.name:
        errors.append("name: 必填")
    if s.on_chain_failure not in VALID_ON_CHAIN_FAILURE:
        errors.append(f"on_chain_failure: 非法值 '{s.on_chain_failure}' (合法: {sorted(VALID_ON_CHAIN_FAILURE)})")
    if not s.steps:
        errors.append("steps: 至少一步")
    seen: set[str] = set()
    for i, step in enumerate(s.steps):
        tag = f"steps[{i}]"
        if not step.name:
            errors.append(f"{tag}.name: 必填")
        elif step.name in seen:
            errors.append(f"{tag}.name: 重复 '{step.name}'")
        seen.add(step.name)
        if not step.command:
            errors.append(f"{tag}.command: 必填")
        if step.on_failure not in VALID_ON_FAILURE:
            errors.append(f"{tag}.on_failure: 非法值 '{step.on_failure}' (合法: {sorted(VALID_ON_FAILURE)})")
        if step.retry_max < 0:
            errors.append(f"{tag}.retry.max: 不能为负")
        if step.capture_output_to and not step.capture_output_to.replace("_", "").replace("-", "").isalnum():
            errors.append(f"{tag}.capture_output_to: 引用名须为标识符 '{step.capture_output_to}'")
    for h in s.hitl:
        if not h.get("at"):
            errors.append("hitl[].at: 必填 (须为 step name)")
        elif h.get("at") not in seen:
            errors.append(f"hitl[].at: '{h.get('at')}' 不在 steps 中")
    return errors


def validate_command_catalog(spec: ChainSpec) -> list[str]:
    """每步命令第一 token (去 cockpit 前缀) 须 ∈ COMMAND_CATALOG 且 chain_enabled."""
    from cockpit.commands.delegation import ensure_delegated_catalog
    from cockpit.commands.registry import COMMAND_CATALOG

    ensure_delegated_catalog()
    errors: list[str] = []
    for i, step in enumerate(spec.steps):
        tokens = step.command.strip().split()
        if tokens and tokens[0] == "cockpit":
            tokens = tokens[1:]
        cmd = tokens[0] if tokens else ""
        meta = COMMAND_CATALOG.get(cmd)
        if meta is None:
            errors.append(f"steps[{i}].command: '{cmd}' 不在 COMMAND_CATALOG")
        elif not meta.chain_enabled:
            errors.append(f"steps[{i}].command: '{cmd}' chain_enabled=False (risk={meta.risk})")
    return errors


def spec_to_raw(spec: ChainSpec) -> dict[str, Any]:
    """ChainSpec → 可序列化 dict (chain show 用)."""
    return {
        "id": spec.id,
        "version": spec.version,
        "name": spec.name,
        "description": spec.description,
        "owner": spec.owner,
        "tags": spec.tags,
        "params": spec.params,
        "timeout": spec.timeout,
        "on_chain_failure": spec.on_chain_failure,
        "steps": [
            {
                "name": s.name,
                "title": s.title,
                "command": s.command,
                "args": s.args,
                **({"when": s.when} if s.when else {}),
                "on_failure": s.on_failure,
                **({"retry": {"max": s.retry_max, "backoff": s.retry_backoff}} if s.retry_max else {}),
                **({"capture_output_to": s.capture_output_to} if s.capture_output_to else {}),
            }
            for s in spec.steps
        ],
        "hitl": spec.hitl,
        "source_path": spec.source_path,
    }


SKELETON_TEMPLATE = """\
id: {chain_id}
version: 1
name: {chain_id}
description: TODO: 链路用途
owner: cockpit
tags: []
params: {{}}
timeout: 600
on_chain_failure: abort
steps:
  - name: step-1
    title: 第一步
    command: cockpit status
    args: ["--json"]
    on_failure: abort
hitl: []
"""


def init_chain(chain_id: str, force: bool = False) -> Path:
    """生成骨架 YAML 到 <cockpit 仓>/config/chains/<chain_id>.yaml."""
    import re

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", chain_id):
        raise ChainSpecError(f"非法 chain id: '{chain_id}' (须为小写字母/数字/连字符)")
    target_dir = REPO_ROOT / "config" / "chains"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{chain_id}.yaml"
    if target.exists() and not force:
        raise ChainSpecError(f"已存在: {target} (用 --force 覆盖)")
    target.write_text(SKELETON_TEMPLATE.format(chain_id=chain_id), encoding="utf-8")
    return target
