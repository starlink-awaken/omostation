---
schema_version: evidence-report/v1
status: archived
owner: governance-team
observed_at: 2026-08-27
bet_id: BET-Y1Q3-T10-21
lifecycle: history
last-reviewed: 2026-08-27
---

# L4 实例与 Documents 边界盘点

## 1. 盘点范围

本报告只记录 Workspace checkout、Agora nested submodule、L4 interface/source 和 Documents registry 的静态事实；不修改 Documents 内容、不启动生产服务、不切换路由。

## 2. 两个 L4 实例

| 实例 | 路径 | 观察 commit | 来源/状态 |
|---|---|---|---|
| canonical | `projects/l4-kernel` | `f3d697999cd1f0075338f79308f1de2c9ebbf31f` | Workspace root submodule，ManifestRegistry/Content Plane/Harness |
| nested | `projects/agora/projects/l4-kernel` | `cdab5c6c40efb39e61719aac67c55174e18d9bb2` | Agora nested submodule，legacy DomainRegistry/KEMS |

两者属于同一远程仓库；nested commit 是 canonical commit 的祖先，但不是同一个运行实现。

## 3. 接口差异

- canonical `INTERFACE.yaml` 将正式 Phase 0 MCP 面限定为 contract validation 与 Harness；架构定位为只读契约编译器和内容面 Harness。
- nested `INTERFACE.yaml` 仍将 L4 定义为 27 域统一注册与 KEMS 六面管理面。
- canonical source 的 MCP `TOOLS` 表实际包含 47 个工具；nested source 的 `TOOLS` 表实际包含 45 个工具，包含历史管理/执行面。
- Agora `mcp_bootstrap.py`、BOS fallback 和 auth gateway 均按 `projects/l4-kernel` 路径声明/启动 L4；在 Agora checkout 中该路径落到 nested submodule。

## 4. Documents 绑定事实

- `@公共/_control/L4-DOMAIN-REGISTRY.yaml` 是 12 个 Documents 域的 identity registry。
- `.omo/_truth/registry/documents-domain-projects.yaml` 将域身份 owner 指向 L4，将 Workspace MCP owner 指向 Cockpit，将任务/审批指向 OMO，将知识 runtime 指向 Kairon/KOS，将运行状态指向 Runtime。
- Runtime state 的声明根为 Workspace 下 `.local/state/omostation/runtime`；与 Documents root 重叠时 owner-job runner 会 fail closed。

## 5. 现状判定

| 轴 | 判定 | 证据 |
|---|---|---|
| canonical L4 可加载/可测试 | PASS | L4 lint 与全量测试 exit 0 |
| nested L4 可独立复现 | PARTIAL | nested uv 环境缺少 Agora 内部 `projects/bus-foundation` |
| L4 身份唯一 | FAIL | root 与 Agora 各有一个 L4 submodule |
| BOS route 唯一 | FAIL | 相同 L4 service route 使用相对路径 |
| Documents binding 声明 | PASS | domain project checker 12/12，无 error |
| Documents 物理纯内容化 | FAIL | 实际 T8 仍发现 runtime/cache/projection/invalid archive |
| 本波次切换/删除 | UNPROVABLE | 本报告不执行生产切换和删除 |

## 6. 复核命令

```bash
git ls-tree HEAD projects/l4-kernel
git -C projects/agora ls-tree HEAD projects/l4-kernel
git -C projects/l4-kernel rev-parse HEAD
git -C projects/agora/projects/l4-kernel rev-parse HEAD
python3 bin/ssot/journey-validator.py
python3 bin/gac/documents-domain-project-check.py --domain-registry <path> --project-registry <path> --json
python3 bin/gac/documents-content-plane-migration-check.py --json
```
