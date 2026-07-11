"""Domain app registry and OPC workspace API.

Cockpit owns the human-facing entry surface. L4 domains keep their own SSOT
and, when needed, their own vertical apps. This module exposes the contract
that lets the UI mount those apps without absorbing their data or code.
"""

from __future__ import annotations

import json
import os
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _find_workspace_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            return parent
    return Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))).expanduser()


WORKSPACE_ROOT = _find_workspace_root()


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser()


def _iso_mtime(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    except OSError:
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _path_state(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "updated_at": _iso_mtime(path),
    }


def _probe_url(url: str | None) -> dict[str, Any]:
    if not url:
        return {"status": "not_configured", "url": None, "checked": False}
    if url.startswith("/"):
        return {"status": "internal_route", "url": url, "checked": True}

    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname not in {"localhost", "127.0.0.1", "::1"}:
        return {"status": "external_unchecked", "url": url, "checked": False, "host": hostname}

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((hostname, port), timeout=0.08):
            return {"status": "listening", "url": url, "checked": True, "host": hostname, "port": port}
    except OSError:
        return {"status": "closed", "url": url, "checked": True, "host": hostname, "port": port}


def _runtime_status(contract: DomainAppContract) -> dict[str, Any]:
    launch = _probe_url(contract.launch_url)
    api = _probe_url(contract.api_url)
    statuses = {launch["status"], api["status"]}

    if "listening" in statuses or "internal_route" in statuses:
        status = "running"
    elif contract.launch_url or contract.api_url:
        status = "stopped"
    else:
        status = "not_applicable"

    return {
        "status": status,
        "launch": launch,
        "api": api,
    }


def _contract_actions(contract: DomainAppContract) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if contract.launch_url:
        actions.append(
            {
                "id": "open",
                "label": "打开应用",
                "kind": "open_url",
                "value": contract.launch_url,
                "enabled": True,
                "risk": "low",
                "guard": "opens external app; no workspace write",
            }
        )
    if contract.api_url:
        actions.append(
            {
                "id": "open-api",
                "label": "打开接口",
                "kind": "open_url" if contract.api_url.startswith("http") else "internal_link",
                "value": contract.api_url,
                "enabled": True,
                "risk": "low",
                "guard": "read-only API entry from Cockpit",
            }
        )
    if contract.start_command:
        actions.append(
            {
                "id": "copy-start",
                "label": "复制启动命令",
                "kind": "copy_command",
                "value": contract.start_command,
                "enabled": True,
                "risk": contract.risk_level,
                "guard": "manual execution only; Cockpit does not run this command",
            }
        )
    if contract.verify_commands:
        actions.append(
            {
                "id": "copy-verify",
                "label": "复制验证命令",
                "kind": "copy_command",
                "value": " && ".join(contract.verify_commands),
                "enabled": True,
                "risk": "low",
                "guard": "manual verification; no background execution",
            }
        )
    return actions


def _security_check(
    *,
    check_id: str,
    status: str,
    level: str,
    title: str,
    detail: str,
    evidence: str,
    next_action: str,
    source_path: Path | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "level": level,
        "title": title,
        "detail": detail,
        "evidence": evidence,
        "next_action": next_action,
        "source": _path_state(source_path),
        "blocking": status == "failed",
    }


def _contains_all(text: str, tokens: tuple[str, ...]) -> bool:
    return all(token in text for token in tokens)


def _family_dashboard_security_checks(contract: DomainAppContract) -> list[dict[str, Any]]:
    app_root = contract.app_root or Path()
    proxy_path = app_root / "src" / "proxy.ts"
    save_path = app_root / "src" / "app" / "api" / "file" / "save" / "route.ts"
    rebuild_path = app_root / "src" / "app" / "api" / "rebuild" / "route.ts"
    ai_path = app_root / "src" / "lib" / "ai.ts"
    csrf_path = app_root / "src" / "lib" / "csrf.ts"

    proxy_text = _read_text(proxy_path)
    save_text = _read_text(save_path)
    rebuild_text = _read_text(rebuild_path)
    ai_text = _read_text(ai_path)
    csrf_text = _read_text(csrf_path)

    api_auth_ok = _contains_all(
        proxy_text,
        ('pathname.startsWith("/api")', "isAuthedCookieValue", "status: 401"),
    )
    save_csrf_ok = _contains_all(save_text, ("hasValidCsrfHeader", "status: 403"))
    save_whitelist_ok = _contains_all(save_text, ("canWriteSsotPath", "resolveSsotPath"))
    save_audit_ok = _contains_all(save_text, ("appendAuditLog", "file-writes.jsonl"))
    rebuild_csrf_ok = _contains_all(rebuild_text, ("hasValidCsrfHeader", "execFileSync"))
    ai_env_redaction_ok = _contains_all(
        ai_text, ("process.env.FAMILY_AI_GATEWAY", "redactText", "FAMILY_AI_REDACT_CONTEXT")
    )
    ai_has_default_gateway = bool(re.search(r"https?://\d+\.\d+\.\d+\.\d+", ai_text))
    csrf_env_ok = "process.env.FAMILY_CSRF_TOKEN" in csrf_text
    csrf_static_token = 'FAMILY_CSRF_TOKEN = "family-dashboard-write"' in csrf_text

    return [
        _security_check(
            check_id="api-auth-cookie",
            status="passed" if api_auth_ok else "failed",
            level="high",
            title="API 也校验登录态",
            detail="Next proxy 必须保护 /api，未登录 API 返回 401，而不是只保护页面路由。",
            evidence="proxy.ts 包含 /api 分支、cookie 校验和 401 JSON 响应。"
            if api_auth_ok
            else "未检测到完整 /api cookie 校验链。",
            next_action="保持 proxy.ts 覆盖 /api；新增 API 时不要绕开 middleware。",
            source_path=proxy_path,
        ),
        _security_check(
            check_id="file-save-csrf",
            status="passed" if save_csrf_ok else "failed",
            level="high",
            title="文件写入需要 CSRF",
            detail="file/save 会写 SSOT 文件，POST 必须先校验 CSRF header。",
            evidence="file/save route 调用 hasValidCsrfHeader 并在失败时返回 403。"
            if save_csrf_ok
            else "未检测到 file/save CSRF 403。",
            next_action="在写入前校验 CSRF，并把失败响应保持为 403。",
            source_path=save_path,
        ),
        _security_check(
            check_id="file-save-path-whitelist",
            status="passed" if save_whitelist_ok else "failed",
            level="high",
            title="文件写入路径白名单",
            detail="写回只能落在家庭 SSOT 允许范围，不能任意路径写文件。",
            evidence="file/save route 使用 canWriteSsotPath 与 resolveSsotPath。"
            if save_whitelist_ok
            else "未检测到写路径白名单和解析保护。",
            next_action="保留 canWriteSsotPath/resolveSsotPath，新增写接口复用同一边界。",
            source_path=save_path,
        ),
        _security_check(
            check_id="file-save-audit-log",
            status="passed" if save_audit_ok else "failed",
            level="medium",
            title="文件写入审计日志",
            detail="真实资料写入需要最小审计，至少记录时间、动作、路径和字节数。",
            evidence="file/save route 写入 .local-audit/file-writes.jsonl。"
            if save_audit_ok
            else "未检测到 file/save 审计日志。",
            next_action="写入成功后追加本地审计日志，后续可接 Cockpit 统一审计。",
            source_path=save_path,
        ),
        _security_check(
            check_id="rebuild-csrf",
            status="passed" if rebuild_csrf_ok else "failed",
            level="high",
            title="重建接口需要 CSRF",
            detail="rebuild 会执行 bun run build:data，必须在执行前校验 CSRF。",
            evidence="rebuild route 调用 hasValidCsrfHeader，并通过 execFileSync 受控执行 build:data。"
            if rebuild_csrf_ok
            else "未检测到 rebuild CSRF 或受控执行。",
            next_action="保持 rebuild POST 的 CSRF 检查在命令执行之前。",
            source_path=rebuild_path,
        ),
        _security_check(
            check_id="ai-env-redaction",
            status="warn"
            if ai_env_redaction_ok and ai_has_default_gateway
            else "passed"
            if ai_env_redaction_ok
            else "failed",
            level="medium",
            title="AI 网关环境化与脱敏",
            detail="家庭隐私内容进入 AI 前需要环境化网关、默认脱敏和本地模式策略。",
            evidence=(
                "已检测到 FAMILY_AI_GATEWAY 与 redactText，但仍保留默认网关 fallback。"
                if ai_env_redaction_ok and ai_has_default_gateway
                else "已检测到 FAMILY_AI_GATEWAY 与 redactText。"
                if ai_env_redaction_ok
                else "未检测到 AI 网关环境变量和脱敏链路。"
            ),
            next_action="去掉硬编码默认网关，或把它降为本机开发显式配置。",
            source_path=ai_path,
        ),
        _security_check(
            check_id="csrf-secret-env",
            status="warn" if csrf_static_token else "passed" if csrf_env_ok else "failed",
            level="medium",
            title="CSRF token 不应静态硬编码",
            detail="CSRF token 应来自环境变量或会话绑定，静态常量只适合作为临时本机原型。",
            evidence=(
                "检测到静态 FAMILY_CSRF_TOKEN。"
                if csrf_static_token
                else "检测到 process.env.FAMILY_CSRF_TOKEN。"
                if csrf_env_ok
                else "未检测到 CSRF token 来源。"
            ),
            next_action="把 FAMILY_CSRF_TOKEN 切到环境变量，并在客户端从受控入口取 token。",
            source_path=csrf_path,
        ),
    ]


def _family_hub_security_checks(contract: DomainAppContract) -> list[dict[str, Any]]:
    app_root = contract.app_root or Path()
    server_path = app_root / "api" / "server.ts"
    server_text = _read_text(server_path)

    write_auth_ok = (
        "FAMILY_HUB_API_TOKEN" in server_text
        and ("requireWriteAuth" in server_text or "requireApiAuth" in server_text)
        and "authorization" in server_text
        and "status(401)" in server_text
    )
    audit_ok = _contains_all(server_text, ("appendAuditLog", "api-writes.jsonl", "quest.complete", "quest.create"))
    validation_ok = _contains_all(
        server_text, ("Quest title is required", "Invalid quest type", "Invalid quest assignee")
    )
    gbrain_safe_ok = (
        _contains_all(server_text, ("execFile", "syncQuestCompletionToGbrain")) and "gbrainCmd" not in server_text
    )

    return [
        _security_check(
            check_id="family-hub-write-auth",
            status="passed" if write_auth_ok else "failed",
            level="medium",
            title="写接口 Bearer token",
            detail="family-hub 的 quest 创建/完成接口需要受控写 token，避免外部页面直接写 SQLite。",
            evidence="api/server.ts 包含 FAMILY_HUB_API_TOKEN、requireApiAuth、Authorization 校验和 401 响应。"
            if write_auth_ok
            else "未检测到 family-hub 写 token 校验。",
            next_action="生产环境配置 FAMILY_HUB_API_TOKEN，前端用 VITE_FAMILY_HUB_API_TOKEN 发送 Bearer token。",
            source_path=server_path,
        ),
        _security_check(
            check_id="family-hub-write-audit",
            status="passed" if audit_ok else "failed",
            level="medium",
            title="写接口审计日志",
            detail="创建/完成任务会改变家庭任务状态，必须留下本地审计证据。",
            evidence="api/server.ts 写入 .local-audit/api-writes.jsonl，记录 quest.create 和 quest.complete。"
            if audit_ok
            else "未检测到 family-hub 写审计。",
            next_action="每个写接口成功后追加审计日志，后续可接 Cockpit 统一审计。",
            source_path=server_path,
        ),
        _security_check(
            check_id="family-hub-input-validation",
            status="passed" if validation_ok else "failed",
            level="medium",
            title="任务写入输入校验",
            detail="创建任务必须校验标题、类型和分配对象，避免脏数据进入 SQLite。",
            evidence="api/server.ts 校验 title/type/assignee 并返回 400。"
            if validation_ok
            else "未检测到任务创建输入校验。",
            next_action="继续把 reward 范围和角色集合收敛到共享 schema。",
            source_path=server_path,
        ),
        _security_check(
            check_id="family-hub-gbrain-execfile",
            status="passed" if gbrain_safe_ok else "failed",
            level="medium",
            title="GBrain 同步不拼 shell",
            detail="任务标题会进入同步内容，不能拼成 shell 字符串执行。",
            evidence="api/server.ts 使用 execFile 参数调用 syncQuestCompletionToGbrain，未检测到 gbrainCmd shell 拼接。"
            if gbrain_safe_ok
            else "仍可能存在 shell 字符串拼接。",
            next_action="保持外部命令走 execFile 参数数组，用户内容只作为参数传入。",
            source_path=server_path,
        ),
    ]


def _security_checks(contract: DomainAppContract) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if contract.id == "family-dashboard-app":
        checks.extend(_family_dashboard_security_checks(contract))
    elif contract.id == "family-hub":
        checks.extend(_family_hub_security_checks(contract))
    elif contract.write_capabilities:
        checks.append(
            _security_check(
                check_id="write-surface-registered",
                status="warn",
                level=contract.risk_level,
                title="写入接口安全证据待登记",
                detail="该领域服务声明了写入能力，但 Cockpit 还没有读到认证、CSRF、白名单和审计证据。",
                evidence=", ".join(contract.write_capabilities),
                next_action="把服务写入接口的认证、审计和验证命令登记到 domain app contract。",
                source_path=contract.app_root,
            )
        )
    else:
        checks.append(
            _security_check(
                check_id="read-only-contract",
                status="passed",
                level="low",
                title="只读领域挂载",
                detail="该领域入口未声明写入能力，Cockpit 只做读取、聚合和导航。",
                evidence="write_capabilities 为空。",
                next_action="新增写能力前先补安全门 contract。",
                source_path=contract.ssot_root or contract.app_root,
            )
        )

    if contract.integration_mode != "native_cockpit_view":
        checks.append(
            _security_check(
                check_id="external-boundary",
                status="passed",
                level="medium",
                title="外部挂载边界",
                detail="Cockpit 只做入口、状态和导航，不吸收领域 app 代码或真实 SSOT 数据。",
                evidence=contract.integration_mode,
                next_action="继续保持 L4 SSOT 和 app 代码在领域边界内。",
                source_path=contract.app_root or contract.ssot_root,
            )
        )
    return checks


def _security_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failed = sum(1 for check in checks if check["status"] == "failed")
    warn = sum(1 for check in checks if check["status"] == "warn")
    passed = sum(1 for check in checks if check["status"] == "passed")
    posture = "blocked" if failed else "attention" if warn else "passed"
    return {
        "posture": posture,
        "total": len(checks),
        "passed": passed,
        "warn": warn,
        "failed": failed,
        "blocking": failed,
        "attention": warn + failed,
        "high_risk_open": sum(1 for check in checks if check["level"] == "high" and check["status"] != "passed"),
    }


def _security_gates(contract: DomainAppContract) -> list[dict[str, str]]:
    gates: list[dict[str, str]] = []
    if contract.write_capabilities:
        gates.append(
            {
                "id": "write-gate",
                "level": contract.risk_level,
                "title": "写入能力需安全门",
                "detail": "写入、重建、AI 网关等能力必须由领域 app 自己完成认证、CSRF、白名单和审计。",
            }
        )
    if contract.integration_mode != "native_cockpit_view":
        gates.append(
            {
                "id": "external-boundary",
                "level": "medium",
                "title": "外部挂载边界",
                "detail": "Cockpit 只做入口、状态和导航，不吸收领域 app 代码或真实 SSOT 数据。",
            }
        )
    return gates


@dataclass(frozen=True)
class DomainAppContract:
    id: str
    name: str
    domain_id: str
    domain_name: str
    kind: str
    integration_mode: str
    layer: str
    risk_level: str
    ssot_root: Path | None
    app_root: Path | None
    launch_url: str | None
    api_url: str | None
    start_command: str | None
    verify_commands: tuple[str, ...]
    read_capabilities: tuple[str, ...]
    write_capabilities: tuple[str, ...]
    auth: dict[str, str]
    notes: tuple[str, ...]


def _contracts() -> list[DomainAppContract]:
    family_root = _env_path("FAMILY_SSOT_ROOT", Path.home() / "Documents" / "@家庭生活")
    family_app_root = _env_path("FAMILY_DASHBOARD_APP_ROOT", family_root / "family-dashboard-app")
    opc_root = _env_path("OPC_SSOT_ROOT", Path.home() / "Documents" / "@OPC")
    family_hub_root = _env_path("FAMILY_HUB_ROOT", WORKSPACE_ROOT / "projects" / "family-hub")

    return [
        DomainAppContract(
            id="family-dashboard-app",
            name="家庭驾驶舱",
            domain_id="family",
            domain_name="@家庭生活",
            kind="external_next_app",
            integration_mode="external_mount",
            layer="L4 app mounted through L3 Cockpit",
            risk_level="high",
            ssot_root=family_root,
            app_root=family_app_root,
            launch_url=os.environ.get("FAMILY_DASHBOARD_URL", "http://localhost:3000"),
            api_url=os.environ.get("FAMILY_DASHBOARD_API_URL", "http://localhost:3000/api"),
            start_command=f'cd "{family_app_root}" && bun run dev',
            verify_commands=(
                "bun run verify:paths",
                "bun run verify:domain-data",
                "bun run test",
                "bun run build",
            ),
            read_capabilities=("knowledge.read", "knowledge.search", "app-data.read", "ai.ask"),
            write_capabilities=("knowledge.update:limited", "app-data.rebuild"),
            auth={
                "type": "single_password_cookie",
                "env": "FAMILY_DASHBOARD_PASSWORD",
                "boundary": "external app auth; Cockpit links only",
            },
            notes=(
                "Do not migrate family SSOT into Workspace.",
                "Expose through links/status until the app passes API auth and write gates.",
            ),
        ),
        DomainAppContract(
            id="opc-workspace",
            name="OPC 作战台",
            domain_id="opc",
            domain_name="@OPC",
            kind="cockpit_module",
            integration_mode="native_cockpit_view",
            layer="L3 Cockpit module over L4 SSOT",
            risk_level="medium",
            ssot_root=opc_root,
            app_root=None,
            launch_url=None,
            api_url="/api/opc/workspace",
            start_command=None,
            verify_commands=("uv run pytest src/cockpit/tests/test_domain_apps_api.py -q",),
            read_capabilities=("strategy.read", "content_calendar.read", "metrics.read", "portfolio.read"),
            write_capabilities=(),
            auth={"type": "cockpit_api_auth", "boundary": "inherits Cockpit dashboard auth"},
            notes=(
                "OPC stays a Cockpit module until publishing and product metrics become stable.",
                "The SSOT remains ~/Documents/@OPC.",
            ),
        ),
        DomainAppContract(
            id="family-hub",
            name="Family Hub",
            domain_id="family",
            domain_name="@家庭生活",
            kind="service_app",
            integration_mode="external_service",
            layer="X/L2 service linked from L3 Cockpit",
            risk_level="medium",
            ssot_root=None,
            app_root=family_hub_root,
            launch_url=os.environ.get("FAMILY_HUB_URL"),
            api_url=os.environ.get("FAMILY_HUB_API_URL", "http://localhost:3001/api/health"),
            start_command=f'cd "{family_hub_root}" && bun run api',
            verify_commands=("bun run build", "uv run python -m unittest discover -s tests -q"),
            read_capabilities=("profiles.read", "quests.read", "rewards.read"),
            write_capabilities=("quests.create", "quests.complete", "rewards.update"),
            auth={"type": "service_local", "boundary": "separate service; no SSOT ownership"},
            notes=(
                "This is the gamified task service, not the family knowledge dashboard.",
                "It may feed the family dashboard later through API/MCP contracts.",
            ),
        ),
    ]


def _contract_status(contract: DomainAppContract) -> dict[str, Any]:
    app_state = _path_state(contract.app_root)
    ssot_state = _path_state(contract.ssot_root)
    runtime = _runtime_status(contract)
    security_checks = _security_checks(contract)
    security_summary = _security_summary(security_checks)
    health = "ready"
    warnings: list[str] = []
    freshness: dict[str, Any] = {}

    if contract.app_root is not None and not contract.app_root.exists():
        health = "missing"
        warnings.append("app_root_missing")
    if contract.ssot_root is not None and not contract.ssot_root.exists():
        health = "missing"
        warnings.append("ssot_root_missing")

    if contract.id == "family-dashboard-app" and contract.app_root is not None:
        summary_path = contract.app_root / "app-data" / "summary.json"
        summary = _read_json(summary_path)
        if summary:
            freshness = {
                "status": "built",
                "summary_path": str(summary_path),
                "generated_at": summary.get("meta", {}).get("generatedAt") or summary.get("updatedAt"),
                "updated_at": _iso_mtime(summary_path),
            }
        else:
            if health == "ready":
                health = "needs_build"
            warnings.append("app_data_missing")
            freshness = {"status": "needs_build", "summary_path": str(summary_path)}

    if contract.id == "family-hub" and contract.app_root is not None:
        db_path = contract.app_root / "family_hub.db"
        freshness = {
            "status": "runtime_db_present" if db_path.exists() else "runtime_db_missing",
            "db_path": str(db_path),
            "updated_at": _iso_mtime(db_path),
        }

    if contract.id == "opc-workspace":
        strategy_path = (contract.ssot_root or Path()) / "STRATEGY.md"
        freshness = {
            "status": "ssot_present" if strategy_path.exists() else "strategy_missing",
            "strategy_path": str(strategy_path),
            "updated_at": _iso_mtime(strategy_path),
        }
        if not strategy_path.exists():
            health = "needs_attention" if health == "ready" else health
            warnings.append("strategy_missing")

    return {
        "id": contract.id,
        "name": contract.name,
        "domain": {"id": contract.domain_id, "name": contract.domain_name},
        "kind": contract.kind,
        "integration_mode": contract.integration_mode,
        "layer": contract.layer,
        "risk_level": contract.risk_level,
        "health": health,
        "runtime": runtime,
        "warnings": warnings,
        "paths": {"ssot_root": ssot_state, "app_root": app_state},
        "links": {"launch_url": contract.launch_url, "api_url": contract.api_url},
        "actions": _contract_actions(contract),
        "security_gates": _security_gates(contract),
        "security_checks": security_checks,
        "security_summary": security_summary,
        "commands": {
            "start": contract.start_command,
            "verify": list(contract.verify_commands),
        },
        "capabilities": {
            "read": list(contract.read_capabilities),
            "write": list(contract.write_capabilities),
        },
        "auth": contract.auth,
        "freshness": freshness,
        "notes": list(contract.notes),
    }


def build_domain_apps() -> dict[str, Any]:
    items = [_contract_status(contract) for contract in _contracts()]
    return {
        "schema_version": "v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "strategy": "Cockpit is the L3 entry; L4 domains keep SSOT and vertical app ownership.",
        "items": items,
        "summary": {
            "total": len(items),
            "ready": sum(1 for item in items if item["health"] == "ready"),
            "needs_attention": sum(1 for item in items if item["health"] != "ready"),
            "running": sum(1 for item in items if item["runtime"]["status"] == "running"),
            "stopped": sum(1 for item in items if item["runtime"]["status"] == "stopped"),
            "high_risk": sum(1 for item in items if item["risk_level"] == "high"),
            "external_mounts": sum(1 for item in items if item["integration_mode"] != "native_cockpit_view"),
            "security_passed": sum(item["security_summary"]["passed"] for item in items),
            "security_warn": sum(item["security_summary"]["warn"] for item in items),
            "security_failed": sum(item["security_summary"]["failed"] for item in items),
            "security_blocking": sum(item["security_summary"]["blocking"] for item in items),
            "security_attention_apps": sum(1 for item in items if item["security_summary"]["posture"] != "passed"),
        },
    }


def _markdown_table_after_heading(text: str, heading_keyword: str, limit: int = 8) -> list[dict[str, str]]:
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if heading_keyword in line), -1)
    if start < 0:
        return []

    table_lines: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if table_lines and (not stripped or stripped.startswith("## ")):
            break
        if stripped.startswith("|"):
            table_lines.append(stripped)

    rows = []
    header: list[str] | None = None
    for line in table_lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells:
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if header is None:
            header = cells
            continue
        if header and len(cells) == len(header):
            row = dict(zip(header, cells, strict=False))
            if any(value and value != "—" for value in row.values()):
                rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def _weekly_priorities(strategy_md: str) -> list[dict[str, str]]:
    priorities: list[dict[str, str]] = []
    in_section = False
    for line in strategy_md.splitlines():
        if "本周三件事" in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = re.match(r"\s*\d+\.\s+\*\*(.+?)\*\*\s*[—-]\s*(.+)", line)
        if match:
            priorities.append({"title": match.group(1).strip(), "detail": match.group(2).strip()})
    return priorities


def _metric_sections(metrics_md: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current_heading = ""
    current_lines: list[str] = []

    def flush() -> None:
        if not current_heading:
            return
        rows = _markdown_table_after_heading("\n".join(current_lines), current_heading, limit=12)
        sections.append({"name": current_heading, "items": rows})

    for line in metrics_md.splitlines():
        if line.startswith("## "):
            flush()
            current_heading = line.removeprefix("## ").strip()
            current_lines = [line]
        elif current_heading:
            current_lines.append(line)
    flush()
    return sections


def build_opc_workspace() -> dict[str, Any]:
    opc_root = _env_path("OPC_SSOT_ROOT", Path.home() / "Documents" / "@OPC")
    if not opc_root.exists():
        return {
            "schema_version": "v1",
            "exists": False,
            "ssot_root": str(opc_root),
            "weekly_priorities": [],
            "content_calendar": {"week": [], "ideas": []},
            "metrics": [],
            "product_portfolio": {"matrix": [], "pipeline": [], "revenue": []},
        }

    strategy_md = _read_text(opc_root / "STRATEGY.md")
    calendar_md = _read_text(opc_root / "CONTENT_CALENDAR.md")
    metrics_md = _read_text(opc_root / "METRICS.md")
    portfolio_md = _read_text(opc_root / "PRODUCT_PORTFOLIO.md")

    return {
        "schema_version": "v1",
        "exists": True,
        "ssot_root": str(opc_root),
        "updated_at": max(
            filter(
                None,
                (
                    _iso_mtime(opc_root / "STRATEGY.md"),
                    _iso_mtime(opc_root / "CONTENT_CALENDAR.md"),
                    _iso_mtime(opc_root / "METRICS.md"),
                    _iso_mtime(opc_root / "PRODUCT_PORTFOLIO.md"),
                ),
            ),
            default=None,
        ),
        "positioning": {
            "title": "OPC 作战台",
            "summary": "围绕公开输出、方法论验证和产品化信号，把 @OPC SSOT 聚合到 Cockpit。",
        },
        "weekly_priorities": _weekly_priorities(strategy_md),
        "content_calendar": {
            "week": _markdown_table_after_heading(calendar_md, "本周"),
            "ideas": _markdown_table_after_heading(calendar_md, "选题池"),
        },
        "metrics": _metric_sections(metrics_md),
        "product_portfolio": {
            "matrix": _markdown_table_after_heading(portfolio_md, "产品矩阵"),
            "pipeline": _markdown_table_after_heading(portfolio_md, "产品管线"),
            "revenue": _markdown_table_after_heading(portfolio_md, "收入总览"),
        },
        "source_paths": {
            "strategy": str(opc_root / "STRATEGY.md"),
            "content_calendar": str(opc_root / "CONTENT_CALENDAR.md"),
            "metrics": str(opc_root / "METRICS.md"),
            "product_portfolio": str(opc_root / "PRODUCT_PORTFOLIO.md"),
        },
    }


@router.get("/api/domain-apps")
async def get_domain_apps() -> dict[str, Any]:
    return build_domain_apps()


@router.get("/api/domain-apps/{app_id}")
async def get_domain_app(app_id: str) -> dict[str, Any]:
    for item in build_domain_apps()["items"]:
        if item["id"] == app_id:
            return item
    raise HTTPException(status_code=404, detail="domain app not found")


@router.get("/api/opc/workspace")
async def get_opc_workspace() -> dict[str, Any]:
    return build_opc_workspace()
