---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-08-18
type: ssot
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
| **`PITFALL-004`** | `MEDIUM` | doc-governance `last-reviewed` UTC 时区陷阱 | 本地日期写 `last-reviewed` 但校验器按 UTC 判 future → 预算超限 gac-gate FAIL | `last-reviewed` 一律用 UTC 当天或更早（保守写昨天）；该陷阱同时把文件从 frontmatter 桶移入 enums 桶 |
| **`PITFALL-005`** | `HIGH` | CI 失败误判为自己的改动引入 | PR CI 红了就改自己代码, 但 fail 是 pre-existing（main 上本来就有的问题）| 三步法: 1) 看 PR diff 文件清单排除 gitlink; 2) git stash 跑基线对比; 3) 查近 5-10 个 PR 同检查状态 |
| **`PITFALL-SUB-004`** | `HIGH` | `.git/config` 子模块 URL 覆盖错误导致 init 404 (kairon) | 本地 config 的 `submodule.<path>.url` 覆盖了 `.gitmodules` 正确值 | `git submodule sync <path>` 对齐 config 与 `.gitmodules`; 修复须落盘 `.gitmodules` 而非只改本地 config |
| **`PITFALL-SUB-005`** | `MEDIUM` | 空壳子模块 (.git 存在但内容为空) | claim/init 中途失败留半初始化状态, `update --init` 不重填 | `git submodule update --force --init <sub>` 重填 + `--checkout` 归位到 gitlink (消幽灵 M) |
| **`PITFALL-GAT-006`** | `HIGH` | 交付内容已被 main 等价合并/自愈 | 在过期 base 上重复造轮子, 未先 fetch 最新 main 做内容等价检查 | 动手前 `git fetch origin main` + 内容 diff 判等价; 已合入则放弃分支不开 PR |
| **`PITFALL-COO-004`** | `MEDIUM` | PR CI lint fail 不一定是本 PR 引入 — 子模块 pre-existing violation 触发 | 看到 lint fail 第一反应是改自己代码, 但 fail 文件都在 gitlink 子模块里 (projects/cockpit 等) | 1) 看 PR diff 文件清单排除 gitlink 后是否触发; 2) 查近 5-10 个 PR 同 lint 状态, 都在 fail = pre-existing; 3) 改 rebase 到含子模块 bump 的 main |
| **`PITFALL-COO-005`** | `HIGH` | cherry-pick commit 跨 base 重放带 parent 的 reverse 到 target | cherry-pick 一个 commit 到新 base, PR diff 含 200+ 行反向删除 (parent 引入但 main 已合入的内容) | 跨 base 重放改动: `git show <old>:<path>` 拿文件内容 + 在新 base 重做改动, 不用 cherry-pick 当 commit |
| **`PITFALL-COO-006`** | `MEDIUM` | 本地工作树 ≠ origin/main 状态 | fetch 后没 reset, 工作树停留在 fetch 前的快照, 误以为 PR 没合 | 任何 "main 是不是这样" 判断, 先 `git fetch origin main` + `git reset --hard origin/main`; 不信本地工作树, 用 `git show origin/main:<path>` |

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
