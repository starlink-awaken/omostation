#!/usr/bin/env python3
"""Capability token generator — scoped, time-limited execution tokens for scene dispatch.

Implements the capability-based security pattern (ACM 2026: Securing Agents With
Tracked Capabilities). Tokens are generated per-dispatch from the scene card's
permission_scope, valid for a limited time, and never persisted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

TOKEN_SCHEMA = "capability-token/v1"
DEFAULT_TTL_MINUTES = 30
VALID_SCOPES = {"ci-read", "workflow-read", "evidence-write", "config-read", "state-read"}


def _load_scene_card(path: Path) -> dict[str, Any]:
    import yaml

    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    body = docs[-1] if docs else {}
    if not isinstance(body, dict):
        raise ValueError(f"scene card must be an object: {path}")
    return body


def generate_token(
    scene_card_path: Path,
    *,
    actor: str = "agent",
    ttl_minutes: int = DEFAULT_TTL_MINUTES,
    extra_scopes: list[str] | None = None,
) -> dict[str, Any]:
    """Generate a scoped, time-limited capability token for a scene."""
    card = _load_scene_card(scene_card_path)
    scene_id = card.get("scene_id", "unknown")
    scopes = card.get("permission_scope", [])
    if not isinstance(scopes, list):
        scopes = []

    # Validate scopes against controlled vocabulary (if available)
    invalid = [s for s in scopes if s not in VALID_SCOPES]
    if invalid:
        return {
            "schema": TOKEN_SCHEMA,
            "status": "rejected",
            "detail": f"invalid scope(s): {invalid}",
            "valid_scopes": sorted(VALID_SCOPES),
        }

    if extra_scopes:
        for s in extra_scopes:
            if s not in scopes and s in VALID_SCOPES:
                scopes.append(s)

    now = datetime.now(UTC)
    expires = now + timedelta(minutes=ttl_minutes)
    token_id = secrets.token_urlsafe(16)
    token_hash = hashlib.sha256(f"{scene_id}:{token_id}:{now.isoformat()}".encode()).hexdigest()[:24]

    return {
        "schema": TOKEN_SCHEMA,
        "status": "issued",
        "token_id": f"cap:{token_hash}",
        "scene_id": scene_id,
        "scopes": sorted(set(scopes)),
        "issued_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "ttl_minutes": ttl_minutes,
        "issued_by": actor,
        "resource_limits": {
            "max_files": 100,
            "max_api_calls": 50,
            "max_execution_seconds": ttl_minutes * 60,
        },
        "side_note": "token is in-memory only — do not persist, log, or commit",
    }


def verify_token(token: dict[str, Any]) -> dict[str, Any]:
    """Verify a capability token is valid and not expired."""
    if token.get("schema") != TOKEN_SCHEMA:
        return {"valid": False, "reason": "wrong schema"}
    expires_str = token.get("expires_at", "")
    if not expires_str:
        return {"valid": False, "reason": "missing expires_at"}
    try:
        expires = datetime.fromisoformat(expires_str)
    except ValueError:
        return {"valid": False, "reason": "invalid expires_at format"}
    if datetime.now(UTC) > expires:
        return {"valid": False, "reason": "expired", "expired_at": expires_str}
    return {"valid": True, "scene_id": token.get("scene_id"), "scopes": token.get("scopes", [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])

    sub = parser.add_subparsers(dest="command")

    gen_parser = sub.add_parser("generate", help="generate a capability token")
    gen_parser.add_argument("--scene-card", type=Path, required=True)
    gen_parser.add_argument("--actor", default="agent")
    gen_parser.add_argument("--ttl", type=int, default=DEFAULT_TTL_MINUTES, help="TTL in minutes")

    verify_parser = sub.add_parser("verify", help="verify a token from stdin or --token-file")
    verify_parser.add_argument("--token-file", type=Path)

    args = parser.parse_args(argv)
    command = args.command or "help"

    if command == "generate":
        token = generate_token(args.scene_card, actor=args.actor, ttl_minutes=args.ttl)
        print(json.dumps(token, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if token.get("status") == "issued" else 1

    if command == "verify":
        import sys

        if args.token_file:
            token = json.loads(args.token_file.read_text(encoding="utf-8"))
        else:
            token = json.loads(sys.stdin.read())
        result = verify_token(token)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["valid"] else 1

    print("Commands: generate, verify")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
