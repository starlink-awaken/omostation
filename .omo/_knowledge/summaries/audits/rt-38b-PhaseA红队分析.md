---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Phase A 红队分析报告

> 审计日期: 2026-05-26
> 审计范围: Phase A 6个变更 (P0层定义 / workspace profile / product-health / MCP research_reader / storage.py MCP调用 / 工作台修改)
> 环境: macOS 单人开发环境
> 威胁模型: 数据完整性 > 机密性 > 可用性

---

## 高危 (P0)

| # | 攻击向量 | 影响 | 修复 |
|---|---------|------|------|
| 1 | MCP子进程fork开销 | 每次读操作额外100-300ms，10次调用增加1-3s延迟。两条代码路径维护成本翻倍 | 移除 `_mcp_call`，统一SQLite |
| 2 | `~/.workspace/` 文件权限开放 | persona.yaml (含真实姓名) 和 data.db (含研究内容) 默认644，同机任何进程可读 | `chmod 600` |

## 中危 (P1)

| # | 攻击向量 | 影响 | 修复 |
|---|---------|------|------|
| 3 | product-health PATH劫持 | `subprocess.run(["workspace",...])` 通过PATH解析，恶意venv可完全控制脚本 | 用绝对路径 |
| 4 | MCP直接调用模式无错误处理 | `sys.argv[2]` 无越界检查，错误调用直接崩溃 | 加 try/except |
| 5 | SQLite符号链接劫持 | data.db被符号链接替换可导致数据污染 | `os.path.realpath()` 验证 |
| 6 | 健康度公式可调参 | 分数可以脚本作者随意调参到任意值，43.7%无意义 | 基于真实行为数据 |
| 7 | SELECT * 泄露full_text | research_get 返回所有列，MCP模式下同机进程可读取全部研究 | 显式列清单 |

## 低危 (P2)

| # | 攻击向量 | 修复 |
|---|---------|------|
| 8 | product-health子进程无timeout | 添加 timeout=10 |
| 9 | MCP server错误路径泄露 | 包装异常为通用消息 |
| 10 | 文档 vs 实现同步 | P0层阈值抽离为常量 |

---

## 真实环境下最应该修的3件事

1. **移除 `_mcp_call` 机制** — 子进程fork + 双重代码路径 + 无实际收益，Phase A 不需要
2. **文件权限加固** — `chmod 600 ~/.workspace/persona.yaml ~/.workspace/data.db`，立即生效
3. **product-health 用绝对路径** — 避免 PATH 注入
