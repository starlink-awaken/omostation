import json

from fastapi.testclient import TestClient

from cockpit.dashboard_server import app
from cockpit.web.api_domain_apps import build_domain_apps, build_opc_workspace


def test_domain_apps_contract_uses_configured_paths(monkeypatch, tmp_path):
    family_root = tmp_path / "family"
    family_app = family_root / "family-dashboard-app"
    opc_root = tmp_path / "opc"
    family_hub = tmp_path / "family-hub"

    (family_app / "app-data").mkdir(parents=True)
    (family_app / "src" / "app" / "api" / "file" / "save").mkdir(parents=True)
    (family_app / "src" / "app" / "api" / "rebuild").mkdir(parents=True)
    (family_app / "src" / "lib").mkdir(parents=True)
    (family_hub / "api").mkdir(parents=True)
    opc_root.mkdir()
    family_hub.mkdir(exist_ok=True)
    (family_app / "app-data" / "summary.json").write_text(
        json.dumps({"meta": {"generatedAt": "2026-07-04T00:00:00Z"}}),
        encoding="utf-8",
    )
    (family_app / "src" / "proxy.ts").write_text(
        'const isApiPath = pathname.startsWith("/api");\n'
        "isAuthedCookieValue(v);\n"
        'return NextResponse.json({ error: "未登录" }, { status: 401 });\n',
        encoding="utf-8",
    )
    (family_app / "src" / "app" / "api" / "file" / "save" / "route.ts").write_text(
        "hasValidCsrfHeader(request.headers);\n"
        "return NextResponse.json({}, { status: 403 });\n"
        "canWriteSsotPath(relPath);\n"
        "resolveSsotPath(relPath);\n"
        "appendAuditLog(relPath, content);\n"
        '"file-writes.jsonl";\n',
        encoding="utf-8",
    )
    (family_app / "src" / "app" / "api" / "rebuild" / "route.ts").write_text(
        "hasValidCsrfHeader(request.headers);\nexecFileSync('bun', ['run', 'build:data']);\n",
        encoding="utf-8",
    )
    (family_app / "src" / "lib" / "ai.ts").write_text(
        "process.env.FAMILY_AI_GATEWAY;\nredactText(message.content, 12000);\nprocess.env.FAMILY_AI_REDACT_CONTEXT;\n",
        encoding="utf-8",
    )
    (family_app / "src" / "lib" / "csrf.ts").write_text(
        "export const FAMILY_CSRF_TOKEN = process.env.FAMILY_CSRF_TOKEN;\n",
        encoding="utf-8",
    )
    (opc_root / "STRATEGY.md").write_text("# strategy", encoding="utf-8")
    (family_hub / "api" / "server.ts").write_text(
        "process.env.FAMILY_HUB_API_TOKEN;\n"
        "function requireWriteAuth() { authorization; status(401); }\n"
        "function appendAuditLog() { 'api-writes.jsonl'; 'quest.complete'; 'quest.create'; }\n"
        "if (!title) throw new Error('Quest title is required');\n"
        "throw new Error('Invalid quest type');\n"
        "throw new Error('Invalid quest assignee');\n"
        "function syncQuestCompletionToGbrain() { execFile('bun', []); }\n",
        encoding="utf-8",
    )
    (family_hub / "family_hub.db").write_text("", encoding="utf-8")

    monkeypatch.setenv("FAMILY_SSOT_ROOT", str(family_root))
    monkeypatch.setenv("FAMILY_DASHBOARD_APP_ROOT", str(family_app))
    monkeypatch.setenv("OPC_SSOT_ROOT", str(opc_root))
    monkeypatch.setenv("FAMILY_HUB_ROOT", str(family_hub))

    payload = build_domain_apps()

    assert payload["schema_version"] == "v1"
    assert {item["id"] for item in payload["items"]} == {
        "family-dashboard-app",
        "opc-workspace",
        "family-hub",
    }
    family = next(item for item in payload["items"] if item["id"] == "family-dashboard-app")
    assert family["integration_mode"] == "external_mount"
    assert family["health"] == "ready"
    assert family["freshness"]["status"] == "built"
    assert family["runtime"]["launch"]["checked"] is True
    assert any(action["id"] == "copy-start" for action in family["actions"])
    assert any(action["kind"] == "copy_command" for action in family["actions"])
    assert any(gate["id"] == "write-gate" for gate in family["security_gates"])
    assert family["security_summary"]["posture"] == "passed"
    assert family["security_summary"]["failed"] == 0
    assert any(check["id"] == "api-auth-cookie" for check in family["security_checks"])
    opc = next(item for item in payload["items"] if item["id"] == "opc-workspace")
    assert opc["runtime"]["status"] == "running"
    assert opc["runtime"]["api"]["status"] == "internal_route"
    family_hub_item = next(item for item in payload["items"] if item["id"] == "family-hub")
    assert family_hub_item["links"]["launch_url"] is None
    assert family_hub_item["commands"]["start"].endswith("bun run api")
    assert family_hub_item["security_summary"]["posture"] == "passed"
    assert payload["summary"]["high_risk"] == 1
    assert "running" in payload["summary"]
    assert payload["summary"]["security_failed"] == 0
    assert payload["summary"]["security_warn"] == 0


def test_opc_workspace_parses_operational_ssot(monkeypatch, tmp_path):
    opc_root = tmp_path / "opc"
    opc_root.mkdir()
    (opc_root / "STRATEGY.md").write_text(
        """
## 七、本周三件事

1. **确定公共身份** — 选一个主力平台
2. **发第一篇文章** — 跑通发布链路
""".strip(),
        encoding="utf-8",
    )
    (opc_root / "CONTENT_CALENDAR.md").write_text(
        """
## 本周

| 日期 | 平台 | 选题 | 状态 |
|------|------|------|:--:|
| 周一 | 公众号 | 第一篇 | ⬜ |
""".strip(),
        encoding="utf-8",
    )
    (opc_root / "METRICS.md").write_text(
        """
## 内容

| 指标 | 目标 | 当前 | 趋势 |
|------|------|------|:--:|
| 周发布量 | ≥3 | 1 | 🟡 |
""".strip(),
        encoding="utf-8",
    )
    (opc_root / "PRODUCT_PORTFOLIO.md").write_text(
        """
## 产品管线

| 产品 | 阶段 | 预计上线 | 备注 |
|------|:--:|------|------|
| 模板包 | 构思 | — | 验证中 |
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPC_SSOT_ROOT", str(opc_root))

    payload = build_opc_workspace()

    assert payload["exists"] is True
    assert payload["weekly_priorities"][0]["title"] == "确定公共身份"
    assert payload["content_calendar"]["week"][0]["选题"] == "第一篇"
    assert payload["metrics"][0]["items"][0]["指标"] == "周发布量"
    assert payload["product_portfolio"]["pipeline"][0]["产品"] == "模板包"


def test_domain_apps_routes_are_mounted():
    client = TestClient(app)

    resp = client.get("/api/domain-apps")
    assert resp.status_code == 200
    assert "items" in resp.json()

    opc_resp = client.get("/api/opc/workspace")
    assert opc_resp.status_code == 200
    assert opc_resp.json()["schema_version"] == "v1"
