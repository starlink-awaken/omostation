"""Policy-table RBAC for Memory OS (Phase 6).

Loads `.omo/_truth/registry/memory-rbac.yaml` when available; falls back to
embedded defaults. Enforcement is deny-by-default for unknown roles.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_EMBEDDED: dict[str, Any] = {
    "default_role": "agent",
    "roles": {
        "admin": {"allow": ["write", "recall", "forget", "consolidate", "knowledge_ref", "status", "admin"]},
        "agent": {"allow": ["write", "recall", "forget", "knowledge_ref", "status"]},
        "readonly": {"allow": ["recall", "knowledge_ref", "status"]},
        "guest": {"allow": ["status"]},
        "governance-agent": {"allow": ["write", "recall", "forget", "knowledge_ref", "status", "consolidate"]},
    },
    "profile_role_map": {
        "governance-agent": "governance-agent",
        "claude": "agent",
        "codex": "agent",
        "external-readonly": "readonly",
    },
}


class RbacDeniedError(PermissionError):
    """Raised when an action is not allowed for the resolved role."""


# Backward-compat alias: test_phase6_neo4j_rbac.py 等历史引用用短名 (T6-01 断测修复)
RbacDenied = RbacDeniedError


def _policy_path() -> Path | None:
    env = os.environ.get("MOS_RBAC_PATH")
    if env:
        p = Path(env)
        return p if p.is_file() else None
    for root_key in ("ECOS_WORKSPACE", "WORKSPACE_ROOT"):
        root = os.environ.get(root_key)
        if root:
            cand = Path(root) / ".omo" / "_truth" / "registry" / "memory-rbac.yaml"
            if cand.is_file():
                return cand
    # walk up from package
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / ".omo" / "_truth" / "registry" / "memory-rbac.yaml"
        if cand.is_file():
            return cand
    return None


def _parse_simple_policy_yaml(text: str) -> dict[str, Any]:
    """Minimal YAML subset parser for memory-rbac.yaml (no PyYAML hard dep).

    Supports: default_role scalar, roles.<name>.allow: [a, b], profile_role_map.
    Falls back to embedded defaults on parse failure.
    """
    try:
        import yaml  # type: ignore[import-not-found]

        docs = list(yaml.safe_load_all(text))
        body = docs[-1] if docs else {}
        if isinstance(body, dict) and body.get("roles"):
            return body
    except Exception:
        pass

    out: dict[str, Any] = {"roles": {}, "profile_role_map": {}, "default_role": "agent"}
    # default_role: agent
    m = re.search(r"^default_role:\s*(\S+)\s*$", text, re.M)
    if m:
        out["default_role"] = m.group(1).strip().strip("\"'")
    # roles block: capture name + allow list
    for m in re.finditer(
        r"^  ([a-zA-Z0-9_-]+):\n(?:    .*\n)*?    allow:\s*\[([^\]]*)\]",
        text,
        re.M,
    ):
        role = m.group(1)
        allows = [a.strip().strip("\"'") for a in m.group(2).split(",") if a.strip()]
        out["roles"][role] = {"allow": allows}
    # profile_role_map
    in_map = False
    for line in text.splitlines():
        if re.match(r"^profile_role_map:\s*$", line):
            in_map = True
            continue
        if in_map:
            if re.match(r"^[a-zA-Z_]", line) and not line.startswith(" "):
                break
            mm = re.match(r"^\s+([a-zA-Z0-9_-]+):\s*(\S+)\s*$", line)
            if mm:
                out["profile_role_map"][mm.group(1)] = mm.group(2).strip().strip("\"'")
    if out["roles"]:
        return out
    return dict(_EMBEDDED)


@lru_cache(maxsize=4)
def load_policy(path: str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _policy_path()
    if p and p.is_file():
        body = _parse_simple_policy_yaml(p.read_text(encoding="utf-8"))
        if isinstance(body, dict) and body.get("roles"):
            return body
    return dict(_EMBEDDED)


def resolve_role(
    *,
    role: str | None = None,
    agent_profile: str | None = None,
    policy: dict[str, Any] | None = None,
) -> str:
    pol = policy or load_policy()
    if role:
        return role
    mapping = pol.get("profile_role_map") or {}
    if agent_profile and agent_profile in mapping:
        return str(mapping[agent_profile])
    return str(pol.get("default_role") or "agent")


def allowed_actions(role: str, policy: dict[str, Any] | None = None) -> set[str]:
    pol = policy or load_policy()
    roles = pol.get("roles") or {}
    entry = roles.get(role) or {}
    return set(entry.get("allow") or [])


def check_action(
    action: str,
    *,
    role: str | None = None,
    agent_profile: str | None = None,
    policy: dict[str, Any] | None = None,
    raise_on_deny: bool = True,
) -> bool:
    pol = policy or load_policy()
    resolved = resolve_role(role=role, agent_profile=agent_profile, policy=pol)
    ok = action in allowed_actions(resolved, pol)
    if not ok and raise_on_deny:
        raise RbacDeniedError(f"role={resolved} denied action={action}")
    return ok
