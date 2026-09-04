---
type: ssot
last-reviewed: 2026-08-26
owner: governance-team
---

# Documents 域项目状态入口设计

**日期：** 2026-08-12
**状态：** 已确认设计，待实现
**范围：** Cockpit 只读 CLI/MCP 投影；不改变 Documents 内容、第三方客户端配置、定时任务或运行时执行面。

## 1. 目标

为个人 Documents 库的每一个 L4 域提供一个可信、轻量的项目入口：一次展示该域的权威身份、Workspace 绑定以及该绑定声明的域内引导文件是否存在且可读。

这不是内容健康检查、KEMS 健康度、迁移切换或客户端安装检测。它只回答“这个域是否已经具备可进入、可被 Cowork 客户端识别的项目骨架”。

## 2. 权威边界

| 信息 | 唯一权威来源 | Cockpit 的职责 |
| --- | --- | --- |
| 域 ID、名称、路径、DOMAIN 契约、owner | L4 `ManifestRegistry` 与 `DOMAIN.yaml` | 复用现有 loader 的只读投影 |
| 域到 Workspace profile 的绑定、各客户端声明 | Workspace `.omo/_truth/registry/documents-domain-projects.yaml` | 通过现有 `_binding_context()` 读取，不复制注册表 |
| 域内客户端引导文件 | 已注册域根目录下的文件 | 只检查声明文件的存在性、常规文件类型和可读性 |
| `_entities/facts.md` | Documents 内容域 | 仅作为信息性存在/可读性信号；不影响整体状态 |

Cockpit 不写上述任一来源，也不推断或修改 Claude Desktop、Codex、Zed/ZCode、ChatGPT 的客户端配置。`chatgpt_web` 当前没有 `instruction_file` 声明，因此它不会被当作缺失的域内网关。

## 3. 对外契约

### 3.1 适配器

新增纯只读适配器函数：

```python
domain_project_status(
    domain_id: str = "",
    *,
    workspace_root: str | Path | None = None,
    registry_path: str | Path | None = None,
    documents_root: str | Path | None = None,
) -> dict[str, Any]
```

它复用 `domains_list()` / `domain_context()` 的 L4 authority path 和 `_binding_context()` 的 Workspace binding path；不得另建 manifest 或 binding parser。

响应固定为 `cockpit.domain-project-status.v1`：

```json
{
  "schema": "cockpit.domain-project-status.v1",
  "status": "ok | degraded | unavailable",
  "available": true,
  "requested_domain_id": "vault",
  "total": 1,
  "summary": {"ok": 1, "degraded": 0, "unavailable": 0},
  "domains": [
    {
      "id": "vault",
      "name": "@学习进化",
      "status": "ok",
      "identity": {"path": "…", "lifecycle": "active", "authority_policy": "canonical_write"},
      "binding": {"status": "ok", "profile_id": "content-domain", "source": "…"},
      "gateways": [
        {"client": "claude", "instruction_file": "CLAUDE.md", "status": "present", "path": "…"},
        {"client": "codex", "instruction_file": "AGENTS.md", "status": "present", "path": "…"}
      ],
      "facts": {"status": "present", "path": "…/_entities/facts.md"}
    }
  ],
  "sources": {"domain_registry": "…", "binding_registry": "…"}
}
```

`domain_id` 为空时列出所有已注册域；非空时只返回该域。未知域、无法读取/校验 L4 注册表或无法解析已声明 manifest 时，返回单一 `unavailable` envelope，不伪造部分成功。

### 3.2 状态语义

| 状态 | 含义 |
| --- | --- |
| `ok` | L4 身份有效、Workspace binding 有效，且该 binding 的每个非空 `clients.*.instruction_file` 都是域根内可读的常规文件。 |
| `degraded` | L4 身份仍可解析，但域目录不可用、binding 不存在/无效，或任一声明网关缺失、不可读、类型非法。 |
| `unavailable` | L4 registry/manifest 无法作为 authority 使用，或请求了未知域。 |

全量查询汇总规则：全部域 `ok` 才为 `ok`；至少一个域 `degraded` 时为 `degraded`；L4 authority 不可用或全量投影无法建立时为 `unavailable`。

`facts.status` 只能为 `present`、`missing`、`unreadable` 或 `invalid`，永远不改变上面的域状态。

### 3.3 文件安全与最小读取

网关和 facts 仅接受预期域根下的常规文件；静态 symlink、目录、FIFO 等非普通文件报告 `invalid`，不跟随读取。对普通文件仅做有界可读性探测，不返回文件正文。

此处防止静态路径越界；不把同机恶意精确时序替换作为 MVP 的并发隔离承诺。

### 3.4 CLI 与 MCP

- CLI：`cockpit domain-status [DOMAIN_ID] --json`
  - `--json` 输出上面的完整 JSON envelope；默认文本仅渲染同一 envelope。
  - 退出码：`0=ok`、`1=degraded`、`2=unavailable`。
- MCP：`domain_project_status(domain_id: str = "") -> str`
  - 始终返回同一 envelope 的 JSON 字符串，不写状态、不执行 job、不调用 Runtime。
- 现有 `domains`、`domain_context`、`kems status/scan` 语义保持不变，避免把项目入口误包装为内容审计。

## 4. 明确非目标

- 不迁移或替换 `@公共/_runtime` / `@驾驶舱/_runtime` 的既有脚本、cron 或 symlink。
- 不写 `DOMAIN.yaml`、binding registry、CLAUDE/AGENTS、facts 或任何 Documents 文件。
- 不验证 Claude Desktop / Codex / Zed / ChatGPT 是否已 reload、是否实际安装 MCP，亦不变更它们的配置入口。
- 不把 facts 缺失、KEMS audit 失败或 runtime health 失败映射为项目网关缺失。

## 5. 验收与测试

1. 适配器：有效 identity/binding/gateway 为 `ok`；绑定缺失、域根或声明文件缺失为 `degraded`；facts 缺失仍 `ok`；未知域和坏 registry 为 `unavailable`。
2. 文件边界：声明 gateway 的静态 symlink、目录和 FIFO 均不被跟随，且返回 `invalid`/`degraded`。
3. MCP：工具注册、空/指定 `domain_id` 参数透传，以及 JSON envelope 可解析。
4. CLI：`ok/degraded/unavailable` 分别返回 0/1/2；`--json` 与 MCP/adapter 载荷一致。
5. 真实只读 smoke：针对当前 12 个注册 Documents 域运行一次全量投影；将观察结果如实记录，不把当前缺失项伪装成已完成客户端安装。

实现结束后仅运行 Cockpit 针对性测试、Ruff 与该只读 smoke；Cockpit 合并后，才以独立 root PR 更新 `projects/cockpit` gitlink。任何 legacy runtime 的 parity、cutover、retirement 都保留给后续独立确认。
