---
id: ADR-0425
status: archived
lifecycle: spec
owner: agora
last_updated: '2026-08-25'
---

# ADR-0425: Agent LSP 潜意识护航与 Agora 2.0 内存总线架构

> Date: 2026-08-25
> Status: accepted
> Deciders: Antigravity + 架构师
> Scope: 多智能体运行态 · 内存总线 · 生命周期钩子 · 领域卡带 CI

## Context

随着 OMOStation 迈入多 Agent 高频并发协作深水区，系统面临以下三大物理瓶颈：
1. **CLI 进程并发摩擦**：数百个 Agent 并发拉起 `subprocess.run(["cockpit", ...])` 导致操作系统 I/O 拥堵与句柄饥饿。
2. **事后门禁修复成本高**：结构性漂移（如 Frontmatter 遗失、未登记脚本）在 `git commit` 或 `make ci-local` 时才拦截，导致频繁的打断和返工。
3. **领域沙箱静态陈旧**：Domain Cartridges 依赖人工手动打包，与主干代码和合规红线更新存在时间差。

## Decision

### D1: Agent LSP 实时潜意识护航 (Lifecycle Hook)
在 `.agents/hooks.json` 注册 Antigravity 平台级 `PostToolUse` 钩子，劫持 `write_to_file` 与 `replace_file_content` 工具：
- 文件落盘瞬间由 `bin/gac/agent-lsp-hook.sh` 静默唤醒 `auto-fix-loop.py --apply`。
- 将事后修复前置为毫秒级潜意识纠偏，实现“写盘即合规”。

### D2: Agora 2.0 内存总线架构 (WebSocket/gRPC Daemon)
在 `projects/agora/src/agora/daemon.py` 实现常驻内存守护进程（监听 `:7432`），并由 `cockpit daemon` 统一纳管：
- **Pub/Sub 广播**：基于 WebSocket 提供毫秒级工作区事件与文件锁广播。
- **优雅降级**：当内存总线不可用时，系统自动降级到 FastMCP 工具调用与 CLI 模式。

### D3: Domain Cartridge CI 自动热编译
在 `bin/ssot/cartridge-ci.py` 实现领域沙箱的自动发现与编译流水线，并接入 `bin/gac/knowledge-foundry-cron.py` 的 10:00 定时熔炉槽位，每日全自动完成签名重构。

### D4: FastMCP 与 BOS URI 原生映射
在 Agora MCP 中注册 `governance_auto_fix`、`cartridge_pack` 和 `daemon_bus_publish` 原生工具，并在 `bos://governance/cartridge/*` 与 `bos://bus/daemon/*` 划定路由前缀。

## Consequences

- **正面影响**：
  - 彻底消除了多 Agent 间的 CLI 进程开销，事件传播延迟降至毫秒级。
  - Agent 本地开发漂移自动蒸发，门禁通过率显著提升。
  - 领域沙箱实现 100% 自动化保鲜。
- **限制与成本**：
  - 本地常驻守护进程增加约 30MB 内存开销。
  - 外部非 Antigravity 运行时的 Agent 需显式通过 WebSocket 握手接入。
