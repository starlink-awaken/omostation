---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: cross-system-integration-20260607.md
deprecated-since: 2026-06-23

---

# 跨系统集成清单 (2026-06-07)

| 子系统 | 集成方式 | 状态 | 备注 |
|--------|---------|------|------|
| agora ↔ ecos | L0 审计 hook + BOS URI 解析 | ✅ | bos:// URI 全链路 |
| agora ↔ kairon | POC_SERVICES stdio 子进程 | ⚠️ | 25 个 POC，待迁移 MCP stdio |
| agora ↔ cockpit | CLI 透传 + MCP HTTP | ✅ | cockpit → agora CLI |
| agora ↔ metaos | ProxyManager 代理 | ✅ | H-M 协议调用 |
| agora ↔ runtime | POC forge 子进程 | ✅ | KEI 沙箱 |
| ecos ↔ gbrain | BOSRoute 声明 | 📋 | 已建模，未实际连通 |
| ecos ↔ omo | domain_manager + constraints | ✅ | L0 治理 |
