---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-08-18
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
| **`PITFALL-SUB-004`** | `HIGH` | `.git/config` 子模块 URL 覆盖错误导致 init 404 (kairon) | 本地 config 的 `submodule.<path>.url` 覆盖了 `.gitmodules` 正确值 | `git submodule sync <path>` 对齐 config 与 `.gitmodules`; 修复须落盘 `.gitmodules` 而非只改本地 config |
| **`PITFALL-SUB-005`** | `MEDIUM` | 空壳子模块 (.git 存在但内容为空) | claim/init 中途失败留半初始化状态, `update --init` 不重填 | `git submodule update --force --init <sub>` 重填 + `--checkout` 归位到 gitlink (消幽灵 M) |
| **`PITFALL-GAT-006`** | `HIGH` | 交付内容已被 main 等价合并/自愈 | 在过期 base 上重复造轮子, 未先 fetch 最新 main 做内容等价检查 | 动手前 `git fetch origin main` + 内容 diff 判等价; 已合入则放弃分支不开 PR |

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
