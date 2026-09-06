---
schema_version: specification/v1
spec_version: 1.0.0
title: "Documents 多客户端配置自愈守护与 BOS 统一事实服务网关"
bet_id: BET-Y1Q4-T6-21
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
type: ssot
last_updated: 2026-09-06
---

# Documents 多客户端配置自愈守护与 BOS 统一事实服务网关 (T6-21)

## Intent

修复 Documents 多客户端 (Claude Desktop, Codex, Zed, ZCode) 配置漂移报错，
在 Agora/BOS 中构建统一只读事实穿透网关 (`bos://documents/{domain}/{resource}`)。

## Architecture

```
bin/gac/documents-client-sync.py (新)
├─ check: 扫描 4 个 IDE 配置文件, 报告 drift
├─ apply: 原子写入修复 + 备份旧配置
└─ 输出: JSON status envelope

projects/agora/src/agora/tools_bos/documents.py (新)
├─ bos://documents/{domain}/registry  → L4-DOMAIN-REGISTRY.yaml 只读
├─ bos://documents/{domain}/jobs      → documents-domain-projects.yaml 只读
├─ bos://documents/{domain}/state     → runtime state 只读
└─ Schema 校验 + cache

tests/test_documents_client_sync.py (根目录)
tests/test_bos_documents_facade.py (agora)
```

## Done Criteria

1. `bin/gac/documents-client-sync.py` check 模式: 检测 4 个 IDE 配置漂移, 返回 exit 0 + ok=true
2. `bin/gac/documents-client-sync.py` apply 模式: 原子修复 + 备份
3. `projects/agora/src/agora/tools_bos/documents.py`: bos://documents/* 只读路由注册
4. `projects/agora/tests/test_bos_documents_facade.py`: 单元测试全通过
5. `tests/test_documents_client_sync.py`: 根目录测试全通过
6. `make gac-local-gate`: 全绿

## Non-Goals

- 不修改第三方 IDE 二进制文件或其非 Cockpit 配置
- 不开放公网未经认证的端口服务
- 不在 Documents 物理目录启动常驻进程

## Risks

- L2: 配置修改必须原子写入并备份旧配置
- BOS 网关未认证请求时执行只读受控拒绝
