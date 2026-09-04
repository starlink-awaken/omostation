---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
title: ChatGPT Secure MCP Routing Implementation Plan
type: doc
---
# ChatGPT Secure MCP Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Documents 域项目注册表如实声明 ChatGPT 的官方 MCP 接入方式，并由治理检查器拒绝把本地 stdio 配置伪装成 ChatGPT 直连。

**Architecture:** 域身份继续只由 L4 DomainRegistry/DomainManifest 提供；Workspace 的 `documents-domain-projects.yaml` 继续只保存客户端和能力绑定。ChatGPT 连接只声明官方支持的公共 HTTPS MCP 或 Secure MCP Tunnel，不在仓库创建 tunnel、保存密钥或复制 Cockpit 命令矩阵。

**Tech Stack:** YAML、Python 3.13、pytest、PyYAML、Ruff。

## Global Constraints

- `@公共/_control/L4-DOMAIN-REGISTRY.yaml` 与各域 `DOMAIN.yaml` 仍是域身份唯一机器真源。
- `.omo/_truth/registry/documents-domain-projects.yaml` 是 Workspace 客户端/能力绑定 SSOT；客户端文件仅为投影。
- ChatGPT 不得声明读取 Claude/Codex 的本地 `mcpServers` 或 stdio 配置。
- ChatGPT 官方连接范围固定为 `public_https_or_secure_tunnel`。
- `clients.chatgpt_web.instruction_file` 必须为 YAML `null`。
- `clients.chatgpt_web.requires_developer_mode` 必须为 `true`。
- `clients.chatgpt_web.setup_ref` 固定为 `https://developers.openai.com/plugins/deploy/connect-chatgpt`。
- `clients.chatgpt_web.tunnel_ref` 固定为 `https://developers.openai.com/api/docs/guides/secure-mcp-tunnels`。
- 本任务不得创建 tunnel、写入 `tunnel_id`、API key、token 或修改本机 ChatGPT 设置。

---

### Task 1: 固化 ChatGPT 官方接入契约与 fail-closed 治理门

**Files:**

- Modify: `.omo/_truth/registry/documents-domain-projects.yaml`
- Modify: `bin/gac/documents-domain-project-check.py`
- Modify: `tests/test_documents_domain_project_check.py`
- Modify: `docs/reports/2026-08-12-documents-domain-project-mvp-retrospective.md`

**Interfaces:**

- Consumes: `check_domain_projects(domain_registry_path: Path, project_registry_path: Path) -> dict[str, object]`
- Produces: stable checker errors for missing/malformed/false-local ChatGPT connection metadata; the existing report envelope and exit-code contract remain unchanged.

- [ ] **Step 1: Write failing tests for the ChatGPT connection contract**

Update `_project_registry()` so its valid fixture contains:

```python
"chatgpt_web": {
    "instruction_file": None,
    "mcp_scope": "public_https_or_secure_tunnel",
    "requires_developer_mode": True,
    "setup_ref": "https://developers.openai.com/plugins/deploy/connect-chatgpt",
    "tunnel_ref": "https://developers.openai.com/api/docs/guides/secure-mcp-tunnels",
}
```

Add parameterized negative cases for: missing `clients`, missing `chatgpt_web`, `instruction_file="AGENTS.md"`, `mcp_scope="user_or_project"`, `requires_developer_mode=False`, and either official reference replaced by a non-official URL. Assert the exact stable error returned by the checker.

- [ ] **Step 2: Run RED and record the failures**

Run:

```bash
uv run --with pytest --with pyyaml python -m pytest tests/test_documents_domain_project_check.py -q
```

Expected: the new negative cases fail because the current checker does not validate ChatGPT client metadata.

- [ ] **Step 3: Implement the minimum checker validation**

In `check_domain_projects()`:

1. Require `clients` to be a mapping.
2. Require `clients.chatgpt_web` to be a mapping.
3. Compare the five binding fields against the exact values in Global Constraints.
4. Append deterministic field-specific errors without changing the existing report schema or raising raw exceptions.

Do not add tunnel provisioning, network calls, application discovery, or another registry.

- [ ] **Step 4: Update the live binding registry**

Keep the existing `chatgpt_web` key for compatibility and replace its obsolete `remote_plugin_required` claim with the exact contract from Global Constraints. The note must state that developer mode connects a public HTTPS MCP endpoint or Secure MCP Tunnel and that local Claude/Codex JSON is not consumed.

- [ ] **Step 5: Update the MVP retrospective**

Append a short dated correction recording:

- official evidence changed the prior “remote plugin only” assumption;
- Secure MCP Tunnel can forward to private stdio/HTTP MCP without public ingress;
- no tunnel was provisioned in this task because credentials and external Platform state are a separate owner-confirmed operation.

- [ ] **Step 6: Run focused and live verification**

Run:

```bash
uv run --with pytest --with pyyaml python -m pytest tests/test_documents_domain_project_check.py -q
uv run --with pyyaml python bin/gac/documents-domain-project-check.py \
  --domain-registry "/Users/xiamingxing/Documents/@公共/_control/L4-DOMAIN-REGISTRY.yaml" \
  --project-registry ".omo/_truth/registry/documents-domain-projects.yaml" \
  --json
uv run --with ruff ruff check bin/gac/documents-domain-project-check.py tests/test_documents_domain_project_check.py
uv run --with ruff ruff format --check bin/gac/documents-domain-project-check.py tests/test_documents_domain_project_check.py
git diff --check
```

Expected: focused tests pass; live checker returns `ok=true` and 12 domains; Ruff and diff checks pass.

- [ ] **Step 7: Commit**

```bash
git add .omo/_truth/registry/documents-domain-projects.yaml \
  bin/gac/documents-domain-project-check.py \
  tests/test_documents_domain_project_check.py \
  docs/reports/2026-08-12-documents-domain-project-mvp-retrospective.md \
  docs/superpowers/plans/2026-08-12-chatgpt-secure-mcp-routing.md
git commit -m "fix(documents): govern ChatGPT MCP routing"
```
