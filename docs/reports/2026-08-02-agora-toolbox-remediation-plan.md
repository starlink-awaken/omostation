---
type: ephemeral
created: 2026-09-03
---

# agora × toolbox 修复清单（P0/P1）

> **创建时间**：2026-08-02
> **来源**：[`docs/reports/2026-08-02-agora-toolbox-deep-audit.md`](2026-08-02-agora-toolbox-deep-audit.md) 第 6 节
> **状态**：✅ **F-01~F-14 全部完成**（PR #782 `10e60a08` + PR #790 `4ca5a0f8`，agora `ad92fcd` 已入 main，1476 tests 全绿）
> **执行顺序**：F-01 → F-02 → F-03 → F-05 → F-04 → F-06 → F-07 → F-08 → F-09 → F-10（全部落地）

---

## P0 — 必须修复（安全 + 路由正确性）

### F-01 agora 认证 fail-closed

- **面**：agora
- **问题**：`AGORA_API_KEY` 未配置即 `return True` 且 role=admin；无 `Authorization` 头完全跳过认证
- **证据**：`server/tools_auth.py:26-28` · `mcp/mcp_transport.py:187-202`
- **验收标准**：未配 key 启动失败；无头请求返回 401
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

### F-02 移除硬编码回退 token

- **面**：agora
- **问题**：env 缺失时用明文 `"eCOS-v5-Trust-Token"`，可伪造任意 agent 身份
- **证据**：`middleware/middleware.py:155`
- **验收标准**：无 env 时认证失败
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

### F-03 admission fail-closed

- **面**：agora
- **问题**：`AGORA_ADMISSION_MODE` 默认 degraded→required；`bos_router.register()` 不调用 admission（含 seed_from_poc/reload_from_m1 旁路）
- **证据**：`admission/port.py:170-178` · `bos_router.py:134`
- **验收标准**：provider 缺失即拒绝注册；旁路路径同走准入
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

### F-04 resolver 与 YAML transport 对齐

- **面**：agora
- **问题**：resolver 只实现 internal/stdio/mcp_stdio，YAML 中 50 条（27%）inline/mcp_proxy/mcp/http 条目落入 `_call_stdio` → `Popen([])` 报错
- **证据**：`resolver/api.py:349` · `mcp.py:522`
- **验收标准**：4 种 transport 均有执行路径或显式降级
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

### F-05 修复 BOS 注册表 schema 漂移

- **面**：agora
- **问题**：5 条 `bos://memory/inbox/*` 声明 `transport: mcp` 缺 `command`；`bos://omo/tasks/active` 缺 description → 2 测试失败
- **证据**：`etc/bos-services.yaml`
- **验收标准**：恢复 2 个失败测试全绿（`test_bos_registry.py` / `test_bos_yaml_lint.py`）
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

---

## P1 — 应修复（toolbox 可执行性 + SSOT 刷新）

### F-06 wps-skills command 悬空

- **面**：toolbox
- **问题**：command 指向 `ToolBox/skills/wps-skills/dist/index.js`，但 dist 不存在（未 build）
- **证据**：`bos-services.yaml:2008-2010`
- **验收标准**：`bos://capability/wps-skills/load` 可执行
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

### F-07 3 个 inline 占位降级

- **面**：toolbox
- **问题**：claude-skills/skills-for-fabric/knowledge-work-plugins 无 command，status=active 但调用必失败
- **证据**：B 面 `bos-services.yaml:2072-2083/2135-2146/2179-2190`
- **验收标准**：无 active-but-uninvokable 服务（补 command 或标 deprecated）
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

### F-08 统一 ToolBox 执行环境

- **面**：toolbox
- **问题**：headroom/code-review-graph/deer-flow/datafoundry 用 `python3 -m` 但系统 python3 无对应模块、无 .venv
- **证据**：`bos-services.yaml` 4 个 capability/* 条目
- **验收标准**：各实例可经 `uv run --directory $TOOLBOX_ROOT/...` 执行
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

### F-09 mcp_proxy 迁移纳入 toolbox

- **面**：agora + toolbox
- **问题**：13 服务 transport 全为 stdio/inline，未纳入 mcp_proxy；7 实例 i0_route=pending
- **证据**：`feature_gate.py:34` · B 面 i0_route
- **验收标准**：capability 域经 proxy 管理；i0_route 脱离 pending
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

### F-10 SSOT 快照刷新

- **面**：toolbox
- **问题**：M1 1340→实测 1422；BOS 114→184；port 18→46；ruflo 游离未注册；_staging 名存实亡
- **证据**：`SSOT-SNAPSHOT.md` · `registry/tools.json`
- **验收标准**：快照数字与实测一致；ruflo 注册或归档；无游离实例
- **状态**：✅ 已完成 (PR #782 + #790, agora ad92fcd)

---

## 治理面修复（可选）

| # | 项 | 证据 | 验收 | 状态 |
|---|---|---|---|---|
| F-11 | 凭据泄漏：Authorization 头不进日志 | `server/tools_auth.py:52` | 日志无凭据 | ✅ 已修复 |
| F-12 | RBAC 收紧：非 collab 工具默认 require grant | `auth/authorizer.py:14` | 无 grant 拒绝 | ✅ 已修复（`AGORA_ENFORCE_ALL_TOOLS=1` 可选收紧） |
| F-13 | SSRF 白名单：market/multi_instance_middleware 对外 URL 白名单 | `plugins/market/market.py:302` | 越界 URL 拒绝 | ✅ 已修复 |
| F-14 | 盲区测试：tools_auth fail-open 断言、oauth2/identity 单测、凭据泄漏回归 | tests/ | 新增测试通过 | ✅ 已修复（新增 30+ 测试） |

---

## 执行建议

1. **每项独立 run**：F-01~F-05 在 `projects/agora` 内改代码，F-06~F-10 涉及 `~/ToolBox` + agora 注册清单。
2. **验证**：agora 侧 `uv run pytest tests/ -q`；toolbox 侧 `bin/check-toolbox-ssot.py` + 各实例冒烟。
3. **P0 依赖**：F-04 依赖 F-05（注册表修正后再对齐 resolver 分支判定）。
4. **风险提示**：F-01~F-03 收紧默认配置可能影响现有 agent 调用链，改动前需确认 `AGORA_API_KEY`/admission provider 已配置（或加 feature flag 过渡）。
