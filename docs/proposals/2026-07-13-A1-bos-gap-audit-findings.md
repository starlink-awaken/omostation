# A1 · BOS 声明/执行鸿沟重新审计 — 发现报告

> 日期: 2026-07-13 · 方法: 静态可解析性审计 (纯文件系统, 不 spawn 子进程)
> 审计源: `projects/agora/src/agora/mcp/resolver/services.py` 的 fallback 声明 (65 条, 与 resolver 一致的可执行 registry)
> 脚本: `bos_resolve_audit.py` · 明细: `bos_resolve_audit.csv`

## 核心结论：6/24 的 "102:0" 已严重失真，真实鸿沟只剩 5 条

| 类别 | 数量 | 占比 | 说明 |
|------|------|------|------|
| **OK（可解析）** | 43 | 66% | 目标模块在项目 venv/src 中存在 |
| **UNIMPLEMENTED（声明即标注）** | 17 | 26% | `[UNIMPLEMENTED]` POC stdio，设计上就未实现，非断层 |
| **FAIL（真实断层）** | **5** | 8% | 声明了但模块/子模块缺失 |

**去掉设计性未实现后，48 条"应可用"服务里 43 条可解析 = 90%。** 这与 6/24 审计报告的"102 声明 alive / 0 resolve 成功"是天壤之别——期间广泛补齐的 `mcp_server.py` 和 CLI 模块把绝大多数鸿沟填上了。**旧快照不能再作为决策依据。**

## 5 条真实断层（已逐一验证，非误报）

| URI | 根因 | 验证 |
|-----|------|------|
| `bos://governance/protocols-layer/trigger` | **top-module 缺失** | kairon 下无任何 `protocols_layer` 包/py 文件，URI 悬空 |
| `bos://persona/core-models/schema` | **子模块缺失** | `core_models` 包在，但声明用 `-m core_models.cli`，实际只有 `__main__.py`，无 `cli.py` |
| `bos://persona/core-models/validate` | 同上 | 同上 |
| `bos://persona/health-profile/query` | **子模块缺失** | `health_profile` 包在（`__init__/__main__/io/models`），无 `cli.py` |
| `bos://persona/health-profile/update` | 同上 | 同上 |

## A2 的具体修复方向（已备好，可直接派单）

**低成本（2 处声明改写，各 ~10 分钟）**——`core-models` 和 `health-profile` 都有 `__main__.py`：
- 方案 a：把声明从 `python -m core_models.cli <action>` 改成 `python -m core_models <action>`（走已有 `__main__` 入口）；`health_profile` 同理。需确认 `__main__.py` 接受该 action 参数。
- 方案 b：在两个包补 `cli.py` 薄封装。

**真实缺口（1 个能力，需决策）**——`protocols-layer/trigger`：
- kairon 里根本没有 `protocols_layer` 包。要么**实现**该触发器能力，要么把 URI **标注 UNIMPLEMENTED / deprecate**，别让它继续在 registry 里假装 alive。建议先 deprecate 止血，能力实现单独立项。

## 两条重要 caveat（交给 A2 收口）

1. **静态 ≠ 活体**：文件存在不等于 `uv run ... -m` 一定导入成功（可能有依赖/import 错误）。A2 应对这 43 条 OK 抽样跑一次真实 `uv run` 确认，把"静态可解析"升级为"活体 resolve 通过"。
2. **registry 双源**：运行时优先读 `projects/agora/etc/bos-services.yaml`（YAML 驱动），本审计用的是 services.py 的 fallback 硬编码。A2 应核对 YAML 与 fallback 是否一致——若 YAML 声明了额外 URI，需一并纳入。

## 对健康分的启示（喂给 A4）

真实 resolve 率约 90%（去掉设计性未实现），而非健康分里隐含的"运行时黄"所暗示的崩溃级。这说明 **BOS 层其实比健康分体现的更健康**——运行时 18/30 的低分更可能来自 A3 的 daemon 在线率（60%），而非 BOS 鸿沟。A3 的优先级应高于对 BOS 的进一步投入。
