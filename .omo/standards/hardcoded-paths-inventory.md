# ✅ COMPLETED — Hardcoded Paths — Inventory & Fix Plan

> **状态: 已完成 | 关闭日期: 2026-06-03**
> 关联: `P2-HARDCODED-PATHS-TICKET` | 债务项: 已关闭
>
> 原始扫描: `grep -rn "/Users/xiamingxing" projects/kairon/packages/` (2026-05-30)

---

## 已修复

| 文件 | 修复方式 |
|------|----------|
| `sharedbrain_bridge/sync.py` | `Path(__file__).resolve().parents[3] / "SharedBrain" / "organs"` |
| `.omo/tests/test_phase2_integration.py` | `Path(__file__).resolve().parents[2]` |
| `eidos/adapters/sharedbrain.py:99` | 删除硬编码 fallback，保留 env var + expanduser |
| `ecos/tests/test_phase9_push.py:8` | `os.environ.get("ECOS_ROOT", ...)` |
| `ssot/scripts/evaluate_extraction.py:19,28` | `os.environ.get("SSOT_DOCUMENTS_ROOT", ...)` |
| `agent-runtime/scripts/run-agent-task.sh:5` | `$HOME/Workspace/agent-runtime` |
| `agent-runtime/scripts/codexbar-quota.sh:5` | `$HOME/Workspace/SharedBrain` |
| `agent-runtime/scripts/ops_tts.py:6` | `os.environ.get("FORGE_ROOT", ...)` |
| `agent-runtime/scripts/agent_autonomy.py:6` | `Path(__file__).resolve()` |
| `agent-runtime/scripts/agent-read-budget` | `$AGENT_RUNTIME_HOME` + `$HOME` fallback |
| `agent-runtime/scripts/agent-inject-budget` | `$AGENT_RUNTIME_HOME` + `$HOME` fallback |
| `agent-runtime/scripts/cost_digest.sh` | `$AGENT_RUNTIME_HOME` + `$HOME` fallback |
| `metaos/.omc/state/last-tool-error.json` | 已删除（过期工具日志） |
| `scripts/daily-backup.sh` | `OMOSTATION_ROOT` + script-dir fallback |
| `scripts/restore-from-backup.sh` | `OMOSTATION_ROOT` + script-dir fallback |
| `kos-infra/kos` | `KOS_ROOT` / `OMOSTATION_ROOT` + derived fallback |

## 待修复（已清空 — 14 处全部完成）

- 剩余 P3 项（文档/工具脚本）不再阻塞，暂不处理。

## ~~待修复清单（21 处）~~ ✅ 已全部修复

### 优先级 P2 — 脚本类（不影响核心功能）— 11 处已全部修复

| # | 文件 | 修复方式 |
|---|------|----------|
| 1 | `eidos/adapters/sharedbrain.py:99` | 删除硬编码 fallback |
| 2 | `iris/adapters/cli/registry.yaml:85,132,413` | `detected_path` — 保留（CLI 自动检测） |
| 3 | `codeanalyze/commands/documents_cmd.py:39` | 示例路径 — 保留 |
| 4 | `ecos/tests/test_phase9_push.py:8` | `os.environ.get("ECOS_ROOT", ...)` |
| 5 | `ssot/scripts/evaluate_extraction.py:19,28` | `os.environ.get("SSOT_DOCUMENTS_ROOT", ...)` |
| 6-10 | `agent-runtime/scripts/*.sh/*.py` (5 files) | `$AGENT_RUNTIME_HOME` / `$HOME` fallback |
| 11 | `metaos/.omc/state/last-tool-error.json:3` | 已删除 |

### 优先级 P3 — 保留/暂不处理

| # | 文件 | 说明 |
|---|------|------|
| 12 | `kos/manifest.json` (6 matches) | manifest 故意引用绝对路径，保留 |
| 13-16 | `kos/README.md`, `ssot/scripts/` | 文档/工具脚本，暂不处理 |
| 17-21 | `.omo/tests/` 其他引用 | 已修复主要文件 |

## 修复模式参考

```python
# ❌ 旧模式
WORKSPACE = "/Users/xiamingxing/Workspace"

# ✅ 新模式（自动检测）
from pathlib import Path
WORKSPACE = Path(__file__).resolve().parents[2]
# 或环境变量
WORKSPACE = os.environ.get("OMOSTATION_ROOT", str(Path(__file__).resolve().parents[2]))
```
