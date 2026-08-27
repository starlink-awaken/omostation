---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# Wave 13.1 复盘报告

> 日期: 2026-05-27 | 复盘类型: 逐 Wave 复盘+红队
> 基于 `~/Documents/学习进化/基建架构/38-Workspace全面重构与治理对齐路线图.md`

---

## 1. 完成情况

| 任务 | 状态 | 实际耗时 | 偏差 |
|------|------|---------|------|
| W001 创建 scripts/ 迁入6个外部脚本 | ✅ | 5min | 无 |
| W002 软链保持 cron 兼容 | ✅ | 5min | 无 |
| W003 更新 cli.py 引用路径 | ✅ | 5min | 无 |
| W004 验证 cron 路径一致性 | ✅ | 5min | 无 |
| W005 pyproject.toml 代替 setup.py | ✅ | 5min | 无 |

**实际总耗时**: ~25min（计划65min，提前62%）

**门禁验证**:
- ✅ 64 tests passed
- ✅ 6个软链全部指向 wksp/scripts/
- ✅ cli.py 无 `.hermes/scripts/` 直接引用（除 governance 委派 — 合理的外部依赖）
- ✅ pyproject.toml 语法有效
- ✅ workspace --help 正常

---

## 2. 红队分析

### 2.1 攻击向量扫描

| 向量 | 严重度 | 描述 | 当前状态 |
|------|--------|------|---------|
| 软链断裂 | 🟡 P2 | 如果 wksp/scripts/ 被删除或移动，软链变成断链，cron 无声失败 | 脚本在 git 管理中，概率低 |
| 备份残留 | 🟢 P3 | `.bak` 文件留在 ~/.hermes/scripts/，占空间但无实际风险 | 6个.bak文件，共~12KB |
| 路径穿透 | 🟡 P2 | `_SCRIPT_DIR = Path(__file__).resolve().parent / "scripts"` — 如果 pip 安装，`__file__` 在 site-packages，scripts/ 找不到 | 当前非 pip 安装 |
| governance 路径 | 🟡 P2 | 第34行 `Path.home() / ".hermes" / "scripts"` 仍是硬编码 | 属于外部委派，计划中标注为可接受 |

### 2.2 关键发现

**发现1: pyproject.toml 的 entry point 与当前 `~/.local/bin/workspace` 不一致**
- `setup.py` 使用 `workspace=workspace.cli:main`（包名 workspace）
- `pyproject.toml` 使用 `workspace = "wksp.cli:main"`（包名 wksp）
- 实际模块目录是 `wksp/`，所以 pyproject.toml 的路径是正确的
- **影响**: 如果以后 pip install，旧的 `~/.local/bin/workspace` wrapper 会覆盖。需在安装后更新 wrapper。

**发现2: 遗留 `.bak` 文件未清理**
- 6个 `.bak` 文件共 ~12KB
- 建议在确认软链稳定后删除（保留一个过渡期）

**发现3: 脚本路径只在运行时验证，无静态检查**
- `_SCRIPT_DIR / "product-health"` 在运行时才检查文件存在
- 如果重命名/删除脚本，只有在执行 product-health 时才会报错
- 建议 W005 后补充：启动时验证 `_SCRIPT_DIR` 下所有引用脚本存在

---

## 3. 纠偏措施

| 问题 | 措施 | 执行时机 |
|------|------|---------|
| 遗留 .bak 文件 | 确认 Wave 13.2 正常后删除 | Wave 13.2 门禁后 |
| 无脚本存在性校验 | W006 (README) 中标注脚本清单 | Wave 13.2 |
| pyproject.toml entry point 与 wrapper 潜在冲突 | 记录在 docs/ARCHITECTURE.md 中 | Wave 13.2 |

---

## 4. Wave 13.1 状态

```
Wave 13.1: [██████████] 100% — 解耦完成 ✅
Wave 13.2: [░░░░░░░░░░] 0% — 文档基建（待开始）
```

**TASK_POOL 更新**:
- W001-W005: **done**
- Wave 13.1 复盘：完成

---

## 5. 下一步

进入 Wave 13.2 (文档基建)：
- W006: README.md
- W007: docs/ARCHITECTURE.md
- W008: docs/COMMANDS.md
- W009: docs/CONTRIBUTING.md
- W010: 清理空目录
