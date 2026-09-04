---
lifecycle: pattern
owner: governance-team
last_updated: 2026-08-18
---
# Agent 架构避坑知识库 (Architecture Pitfalls SSOT)

> **核心原则**：所有经历过的架构隐患、AST 拦截踩坑与误区，必须固化在此知识库中，并通过 `ecos-constraint pitfall scan` 纳入 CI 静态门禁，确保“踩过的坑绝不踩第二遍”。

---

## 避坑条目清单

| 编号 | 严重度 | 踩坑场景 | 核心反模式 | 安全规避配方 |
|:---|:---|:---|:---|:---|
| **`PITFALL-001`** | `CRITICAL` | Gatekeeper/Compiler 写磁盘触发静态拦截 | 在治理代码中直接使用 `Path.write_text` / `Path.mkdir` | 采用 `os.makedirs` + `with open(..., "w", encoding="utf-8") as f:` |
| **`PITFALL-002`** | `CRITICAL` | 双平面纯净度破坏 (Documents 脚本污染) | 在 `~/Documents` 下存放 `.py`, `.sh`, `.venv` 或 `node_modules` | 严格代码进 `~/workspace`，文档进 `~/Documents` |
| **`PITFALL-003`** | `HIGH` | 多客户端 MCP 同步参数缺失 | 客户端配置缺少 `--mode install` 或 `--dry-run` 导致静默失败 | 同步脚本必须严格声明 CLI 所需参数并提供 defaults |

---

## 常用治理命令

```bash
# 扫描代码库中是否存在已知踩坑特征
ecos-constraint pitfall scan [path] [--strict]

# 查看避坑知识库列表
ecos-constraint pitfall list

# 详细解释指定踩坑教训与配方
ecos-constraint pitfall explain PITFALL-001
```
