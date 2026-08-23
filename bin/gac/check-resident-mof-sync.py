#!/usr/bin/env python3
"""CR-RESIDENT-MOF-SYNC-01: resident 角色双份对齐 CI 校验.

resident 五类角色 (sediment/decision/execute/monitor/heartbeat) 必须同时注册在:
- 代码 SSOT: projects/omo/src/omo/resident/roles.py (ROLES dict 顶层 keys)
- MOF m1:  projects/ecos/src/ecos/ssot/mof/m1/agent/AGENT-RESIDENT-ROLES.yaml
            (每个 DigitalAgent 的 properties.resident_role)

drift = 对称差 (roles.py 有但 MOF 无 | MOF 有但 roles.py 无).
rule: resident.roles_code_count == resident.roles_mof_count and resident.roles_drift == 0
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROLES_PY = REPO / "projects" / "omo" / "src" / "omo" / "resident" / "roles.py"
MOF_ROLES_YAML = (
    REPO / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "agent"
    / "AGENT-RESIDENT-ROLES.yaml"
)


def _roles_from_code(path: Path) -> set[str]:
    """AST 提取 ROLES dict 顶层 string keys, 零依赖解析 (无需 omo 包).

    兼容两种形式: `ROLES = {...}` (Assign) 与 `ROLES: dict[...] = {...}` (AnnAssign).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
        if (
            any(isinstance(t, ast.Name) and t.id == "ROLES" for t in targets)
            and isinstance(node.value, ast.Dict)
        ):
            keys: set[str] = set()
            for k in node.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
            return keys
    return set()


def _roles_from_mof(path: Path) -> set[str]:
    """从 AGENT-RESIDENT-ROLES.yaml 提取 resident_role 值 (multi-doc YAML)."""
    try:
        import yaml

        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001 - 上报解析错误
        raise SystemExit(f"MOF roles yaml parse error: {exc}") from exc
    roles: set[str] = set()
    for doc in docs:
        if not isinstance(doc, list):
            continue
        for agent in doc:
            if not isinstance(agent, dict):
                continue
            props = agent.get("properties") or {}
            role = props.get("resident_role")
            if role:
                roles.add(str(role))
    return roles


def check_roles_sync() -> tuple[bool, str]:
    """CR-RESIDENT-MOF-SYNC-01: roles.py 与 MOF 双份角色零漂移."""
    if not ROLES_PY.is_file():
        return False, f"roles.py not found: {ROLES_PY}"
    if not MOF_ROLES_YAML.is_file():
        return False, f"AGENT-RESIDENT-ROLES.yaml not found: {MOF_ROLES_YAML}"
    code_roles = _roles_from_code(ROLES_PY)
    mof_roles = _roles_from_mof(MOF_ROLES_YAML)
    drift = sorted(code_roles ^ mof_roles)
    code_only = sorted(code_roles - mof_roles)
    mof_only = sorted(mof_roles - code_roles)
    if drift:
        detail = (
            f"roles drift: code={len(code_roles)} mof={len(mof_roles)} "
            f"drift={len(drift)} (code_only={code_only} mof_only={mof_only})"
        )
        return False, detail
    return True, f"roles aligned: code={len(code_roles)} mof={len(mof_roles)} drift=0"


def main() -> int:
    print("── CR-RESIDENT-MOF-SYNC-01: resident 角色双份对齐 ──")
    passed, detail = check_roles_sync()
    icon = "OK" if passed else "FAIL"
    print(f"  [{icon}] {detail}")
    print()
    if passed:
        print("CR-RESIDENT-MOF-SYNC-01 PASS")
        return 0
    print("CR-RESIDENT-MOF-SYNC-01 FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
