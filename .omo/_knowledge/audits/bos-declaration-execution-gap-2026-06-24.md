# BOS 声明/执行鸿沟审计 — 2026-06-24

> **审计触发**: P0 红旗 C (端到端 smoke, 打破 BOS=0 自嗨)
> **审计者**: laowang (P60+ smoke 诊断)
> **结论**: BOS 端到端当前 **0 路径能跑通**. 102 URI 声明 alive, 实际 resolve 全失败.

## 1. 现象

- `system.yaml`: BOS 24h invocations = 0
- `list_services()`: 102 BOS URI 全 `alive: True`
- `resolve_bos_uri()`: 全报 `error: No such file or directory (os error 2)`

## 2. 精确根因 (两层)

### 层 1: 11/16 stdio 包无 mcp_server.py (声明假阳性)

16 包声明 stdio BOS, 仅 5 包真有 mcp_server.py:

| 有 mcp_server.py ✅ | 无 mcp_server.py ❌ (11 声明假阳性) |
|---------------------|--------------------------------------|
| eidos, forge, iris, kronos, ontoderive | agent-runtime, codeanalyze, core-models, ecos, health-profile, **kos**, metaos, minerva, omo, protocols-layer, sharedbrain-bridge |

### 层 2: 有 mcp_server.py 的包也跑不通 (路径不匹配)

以 `forge` 为例:
- `pyproject.toml`: `packages = ["src/forge"]`
- 实际文件: `src/mcp_server.py` (顶层, 非 `src/forge/mcp_server.py`)
- resolver 生成 command: `uv run --package forge python -m forge.mcp_server`
- 结果: `ModuleNotFoundError` → "No such file or directory"

**5 个有 mcp_server.py 的包可能都有此路径 bug** (待逐个验证).

## 3. 鸿沟量化

| 层 | 声明 | 执行 | 鸿沟 |
|----|------|------|------|
| BOS URI 总数 | 102 | 0 能跑 | 102 |
| stdio 包 | 16 | 0 能跑 | 16 |
| 有 mcp_server.py 的包 | 5 | 0 能跑 (路径错) | 5 |

声明/执行比 = **102:0** (architecture-optimization 报告估的 21:1 实际更严重).

## 4. 治法建议 (专项, 非本轮)

1. **P0 修包结构**: forge/eidos/iris/kronos/ontoderive 的 mcp_server.py 移到 `src/{pkg}/mcp_server.py` (匹配 pyproject packages)
2. **P0 修 resolver command**: 验证动态 command 生成对 5 包正确
3. **P1 决策 11 假阳性包**: 要么补 mcp_server.py, 要么从 BOS 注册表移除声明 (声明/执行对齐)
4. **P2 加 smoke CI**: 每次变更跑 `resolve_bos_uri` 全 102 URI, 防鸿沟复发

## 5. 关联

- `architecture-optimization-2026-06-24.md` P0 "声明/执行鸿沟 21:1"
- `DEBT-*` (待注册: BOS-DECL-EXEC-GAP)
- `projects/agora/src/agora/l0_registry_loader.py` L205-215 (command 动态派生)
- `projects/agora/src/agora/mcp/bos_resolver.py` (StdioAdapter)

---

*审计者: laowang · 2026-06-24 · 类型: 精确诊断 · 状态: 待专项治理*
