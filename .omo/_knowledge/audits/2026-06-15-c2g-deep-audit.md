---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# C2G 全面深度审计报告 (Round 43 P0)

**日期**：2026-06-15
**审核对象**：`projects/c2g/`（拆分独立 git repo 前最后审查）
**审计范围**：10 维度系统化
**总体评级**：🟠 **C- (Conditional Fail)** — 核心代码 Broken，但设计意图清晰
**关键阻塞**：🔴 **`bridge.py:191 IndentationError`** 让整个 CLI 不能 import

---

## 0. 诚实话语前置 (Reader-Disambiguation)

**审计方式**：在 `/tmp/c2g-standalone/` 用 `git subtree split` 提取的 c2g-standalone 4 个 commit bundle
里运行（c2g-standalone HEAD 4c7e7b38），跑 `py_compile` + `python -m c2g.cli --help` 实测验证。

**关键发现**：
- **CLI 跑不了**：`python -m c2g.cli --help` 抛 `IndentationError: unexpected indent (bridge.py, line 191)`
- **0 测试**：`tests/` 目录不存在
- **README 撒谎**：第 49 行提到 `c2g.engine` 模块但代码里**没**这个文件
- **pyproject 占位**：`description = "Add your description here"` 没改，authors 是 `X-Plane Audit Agent`
- **strategy_audit 是 mock**：硬编码打印 `V1 60% / V2 40%`，没真审计

**意外优点**：
- IOC + Protocol 设计完整（2 个 Protocol：IGovernanceProvider + IStorageProvider）
- pydantic schema 完整（TaskSchema + BetSchema + PitchSchema）
- 2 个 adapter 边界清晰（local + ecos）
- `py.typed` 标记（PEP 561 type hint 声明）—— 但没测试

---

## 1. 结构 / 模块（Structure）

**文件清单**（10 个 Python 文件 + pyproject + README）：

| 文件 | 行数 | 角色 |
|------|------|------|
| `src/c2g/__init__.py` | 2 | 公开 API 占位（只有 `hello()`）|
| `src/c2g/domain.py` | 32 | Pydantic schemas（3 个）|
| `src/c2g/ports.py` | 36 | Protocols（2 个接口）|
| `src/c2g/strategy.py` | 68 | 战略逻辑（audit + gc，**mock**）|
| `src/c2g/adapters.py` | 98 | Ecos adapter（`[ecos]` 可选依赖）|
| `src/c2g/adapters_local.py` | 70 | Local adapter（默认）|
| `src/c2g/cli.py` | 59 | argparse 4 子命令 |
| `src/c2g/bridge.py` | **398** | **核心 import 逻辑 (Broken)** |

**评估**：🟡 **C+**
- ✅ IOC 边界清晰
- ✅ 模块职责单一
- ❌ **`__init__.py` 几乎空**（只 hello()），实际是 internal package
- ❌ **`bridge.py 398 行**过长**（应该有 4 个 bridge 模块 split）

---

## 2. 代码质量（Code Quality）

**🔴 致命 Bug 1**：bridge.py:185-209 是 **orphan 缩进错乱死代码**

```python
# bridge.py line 182-208
182:        # [MODEL-DRIVEN M2 VALIDATION & X1-X4 Governance Checks]
183:        from .adapters import get_providers
184:    gov, store = get_providers(omo_dir)        # ← 缩进 4 空格
185:    from .domain import TaskSchema             # ← 缩进 4 空格
186:    t = TaskSchema(**task_data)                # ← 缩进 4 空格
187:    if not gov.validate_task(t):               # ← 缩进 4 空格
188:        validation_errors = ["M2 validation failed"]   # ← 缩进 8 空格
189:    else:
190:        validation_errors = []
191:            if validation_errors:            # ← 缩进 12 空格! 错位
192:                print(...)
                ...
208:            else:
209:                validation_passed = True
```

**根因**：作者把整个 retry loop 的 `if/else` 块从外层 `for idx, (task_title, depends_on_raw) in enumerate(parsed_tasks):` 移走了，但 line 184-209 的内部代码**忘了删**。Line 191 的 12 空格 `if validation_errors:` 现在成了 orphan 死代码。

**后果**：
- `python -m c2g.cli --help` 抛 `IndentationError`
- 4 个子命令（`brainstorm / bet / radar / gc`）全部**跑不了**
- `_import_bmad / _import_fast_track / _import_pitch` 都依赖 bridge.py，**全 broken**

**🔴 致命 Bug 2**：strategy_audit 是 **mock**（`src/c2g/strategy.py:9-15`）

```python
def strategy_audit(omo_dir: Path):
    print("🧠 [Strategic Audit] 正在执行全盘战略向导检查...")
    # Mocking the vector check
    print("✅ All active Bets are aligned with the North Star.")
    print("📊 Current Vector Distribution:")
    print("   V1 (Indie Efficiency): 60%")   # ← 硬编码!
    print("   V2 (Agent Autonomy): 40%")     # ← 硬编码!
```

**后果**：
- README 吹的 "审计全盘活跃目标的愿景偏离度" **没实现**
- c2g 实际是 MVP / prototype，不是 production

**🟡 其他问题**：
- `cli.py:42-46`：`brainstorm` 子命令**只 print mock**，没真调 MetaOS
- `bridge.py` 注释含 `# TODO: Inject real LLM Structured Output API call here` —— **LLM 调用没实现**

**评估**：🟠 **D** （含 1 个 blocker + 1 个 mock）

---

## 3. 依赖（Dependencies）

**pyproject.toml 完整**：

```toml
[project]
name = "c2g"
version = "0.1.0"
description = "Add your description here"   # 🟡 占位
authors = [{ name = "X-Plane Audit Agent", email = "agent@omostation.local" }]  # 🟡 AI agent 作者
requires-python = ">=3.13"
dependencies = [
    "httpx>=0.28.1",
    "pydantic>=2.13.4",
    "pyyaml>=6.0.3",
]
[project.optional-dependencies]
ecos = ["omo"]
[project.scripts]
c2g = "c2g.cli:main"
[tool.uv.sources]
omo = { path = "../omo" }   # 🟡 写死相对路径, 独立 repo 后不能 work
```

**评估**：🟡 **B-**
- ✅ 依赖最小（3 个）
- ✅ ecos 模式 optional
- ❌ **`description` 占位字符串没改** —— 上 PyPI 会被嘲笑
- ❌ **`authors` 是 X-Plane Audit Agent**（AI agent）—— 上 PyPI 不合理
- ❌ **`[tool.uv.sources]` 写死 `../omo` 相对路径** —— 独立 repo 后路径失效
- ❌ `ecos` 可选依赖**没版本约束**

---

## 4. 测试（Testing）

**🟡 严重缺失**：
- ❌ **无 `tests/` 目录**
- ❌ `py.typed` 文件存在（PEP 561）但**没测试**
- ❌ 0% 测试覆盖

**评估**：🟠 **F** （0 测试 = 不能验证任何行为）

---

## 5. 文档（Documentation）

**README.md 完整度**：
- ✅ 中文 README，README 80 行
- ✅ 4 大特性（V2P / C2G / AGC / Ports & Adapters）
- ✅ 安装 + Quickstart + 架构说明
- ❌ **README 第 49 行撒谎**：「核心引擎 (`c2g.engine` / `c2g.bridge` / `c2g.strategy`)」—— `c2g.engine` **不存在**！
- ❌ README 例子用 `--adapter local`（与 cli.py 默认 `--adapter ecos` 冲突）
- ❌ 没说 `c2g.engine` 是哪个文件
- ❌ 没说 4 个 import 函数（_import_bmad / _import_fast_track / _import_pitch）的区别
- ❌ 没说 LLM 调用是 mock（`# TODO: Inject real LLM Structured Output API call here`）

**评估**：🟡 **C+** （README 写作良好但**跟代码不一致**）

---

## 6. Standalone 准备度（Standalone Readiness）

| 维度 | 状态 | 备注 |
|---|---|---|
| pyproject.toml 完整 | 🟡 | description / authors 占位 |
| README | 🟡 | 撒谎（c2g.engine 不存在）|
| License | ❌ | **无 LICENSE 文件** —— 独立 repo 上 PyPI **必须**有 license |
| CI/CD | ❌ | **无 `.github/workflows/`** —— 没自动化测试 |
| Tests | ❌ | 0 测试 |
| 入口 (entry point) | ✅ | `c2g = "c2g.cli:main"` |
| `py.typed` 标记 | ✅ | PEP 561 type hint 声明 |
| 公共 API 文档化 | 🟡 | __init__.py 几乎空 |
| **核心功能可跑** | 🔴 | **IndentationError broken** |

**评估**：🟠 **D+** （设计意图清楚但**功能 broken** + **0 测试** + **无 license** —— 不能独立 release）

---

## 7. 跟 eCOS 集成（eCOS Integration）

**Optional Dep 模式**：
- ✅ `ecos = ["omo"]` —— 不强制依赖
- ✅ `pyproject [tool.uv.sources] omo = { path = "../omo" }` —— 集成模式

**🟡 默认 adapter 是 ecos，不是 local**：
- `cli.py:24` `default="ecos"` —— **用户不传 --adapter 时用 ecos**
- **没装 omo[ecos] 时 EcosGovernanceProvider 抛 ImportError**
- README 例子都用 `--adapter local` 但 default 是 ecos —— **新人首次跑会撞 ImportError**
- 建议：default 改 `local`（避免撞墙）

**🟡 Ecos adapter 实现不完整**：
- `EcosGovernanceProvider` 只实现了 3 个 validation 方法
- `EcosStorageProvider` 只看 `__init__`（没看完整 5 个 IStorageProvider 方法）
- 完整度需要查证（grep `save_bet / save_task / get_pitches`）

**评估**：🟡 **C+** （集成模式存在但 UX 不顺 + adapter 实现不完整）

---

## 8. 安全（Security）

**🟢 低风险**：
- ✅ 无硬编码密钥（`author=agent@omostation.local` 是占位）
- ✅ 无网络调用（除 optional httpx）
- ✅ 依赖最小
- ❌ `pydantic` 没指定 patch 版本（>=2.13.4）—— 安全更新需手动
- ❌ 依赖漏洞扫描**没跑**（pip-audit / safety）

**评估**：🟢 **B+** （依赖少 + 无硬编码，但缺漏洞扫描）

---

## 9. 历史 / 演进（History & Evolution）

**4 个 commit 时间线**（c2g-standalone）：

```
b7ae6ba0  2026-06-15 15:46  feat(architecture): decouple C2G engine from omo
b8094534  2026-06-15 15:49  fix(c2g): fix broken import path
2fcf1944  2026-06-15 15:55  refactor(c2g): implement IoC, decoupling
4c7e7b38  2026-06-15 15:58  docs(c2g): optimize for standalone
```

**⚠️ 异常**：
- 4 个 commit **在 12 分钟内**全做完
- 全是 X-Plane Audit Agent 作者（**单 agent 一次性产出**）
- commit 2 修 import path 紧跟 commit 1 —— **commit 1 有 broken import 没测出来**
- commit 3 (refactor IoC) 引入 dead code `bridge.py:191 IndentationError` —— **没测试所以没发现**

**评估**：🟡 **B-** （commit message 清晰 + 演进意图明确，但**单 agent 一次性产出无 review**）

---

## 10. 总评分（Overall Score）

| 维度 | 权重 | 分数 | 加权 |
|------|------|------|------|
| 1. 结构 / 模块 | 10% | C+ (7/10) | 0.7 |
| 2. 代码质量 | **25%** | **D (4/10)** | 1.0 |
| 3. 依赖 | 5% | B- (7/10) | 0.35 |
| 4. 测试 | **20%** | **F (0/10)** | 0.0 |
| 5. 文档 | 10% | C+ (7/10) | 0.7 |
| 6. Standalone 准备 | **15%** | **D+ (5/10)** | 0.75 |
| 7. eCOS 集成 | 5% | C+ (7/10) | 0.35 |
| 8. 安全 | 5% | B+ (8/10) | 0.4 |
| 9. 历史 | 5% | B- (7/10) | 0.35 |
| **总分** | 100% | — | **4.6 / 10 (D+)** |

### 评级理由

🔴 **致命阻塞**（2 项）：
1. `bridge.py:191 IndentationError` —— 整个 CLI 跑不了
2. 0 测试 —— **任何代码修复无法验证**

🟡 **重要问题**（5 项）：
3. README 撒谎（c2g.engine 不存在）
4. pyproject description 占位
5. `--adapter` default 是 ecos（README 例子用 local）—— 新人撞 ImportError
6. strategy_audit 是 mock（硬编码数字）
7. bridge.py 398 行过长（应该 split 4 个模块）

🟢 **意外优点**：
- IOC + Protocol 设计完整清晰
- pydantic schema 完整（3 个）
- 2 个 adapter 边界清晰
- py.typed 标记

---

## 11. 修复建议（按 P0/P1/P2）

### 🔴 P0 修复（拆独立 repo 前必做）

| 修复 | 工作量 | 风险 |
|---|---|---|
| 1. 修 `bridge.py:191` IndentationError（删 line 185-209 死代码 OR 移到正确缩进） | 30 min | 低（删死代码） |
| 2. 加 `tests/` 目录 + 至少 5 个 smoke test（py_compile 每个文件 + 跑 4 个 CLI 子命令 `--help` + 验 mock output） | 2 h | 中 |
| 3. 加 `LICENSE` 文件（MIT） | 1 min | 极低 |
| 4. pyproject `description` 改真实内容（"C2G: Concept-to-Goal strategic engine with IOC + Ports & Adapters"） | 1 min | 极低 |
| 5. `pyproject authors` 改 X-Plane Audit Agent → 用户身份 | 1 min | 极低 |

### 🟡 P1 修复

| 修复 | 工作量 | 风险 |
|---|---|---|
| 6. `cli.py --adapter` default 改 `local` | 1 min | 极低 |
| 7. 删 README 撒谎的 `c2g.engine` 提法 | 1 min | 极低 |
| 8. bridge.py 398 行 split（按函数分 4 个模块：bridge_import / bridge_depend / bridge_validate / bridge_id） | 2 h | 中 |
| 9. 补 LocalStorageProvider 完整 5 个方法（save_bet / save_task / get_pitches / delete_pitch / get_active_bets） | 1 h | 中 |
| 10. 补 README 章节说 4 个 import 函数区别 + LLM mock 状态 | 30 min | 极低 |

### 🟢 P2 优化（post-release）

| 优化 | 工作量 |
|---|---|
| 11. 实现真 strategy_audit（读 active bets + 算 vector 分布） | 1 天 |
| 12. 实现 LLM Structured Output 调用（替换 mock） | 1 周 |
| 13. 加 `.github/workflows/ci.yml`（pytest + ruff） | 30 min |
| 14. 加 GitHub Actions 安全扫描（pip-audit） | 30 min |

---

## 12. 拆分独立 git repo 决策建议

按"是否应该现在拆分 c2g"：

| 选项 | 利 | 弊 |
|---|---|---|
| **现在拆分 + 不修 P0** | README 准备好 + standalone 设计清晰 | **c2g broken 状态**独立暴露给用户 |
| **现在拆分 + 先修 P0 (1-5)** | 独立 c2g 是**真可用**的 | 工作量大（~3h） |
| **不拆，留 workspace 内部** | 改起来更方便（`projects/c2g/` 还在根仓） | 跟 README/AGENTS.md"独立"描述矛盾 |
| **不拆 + 改 AGENTS.md 描述** | 状态清晰（"内部子项目"）| c2g 失去"独立"标签 |

**老王建议**：**选项 2**（现在拆 + 先修 P0）—— 因为：
1. c2g README 真有 `pip install c2g` 标识，**设计意图就是独立**
2. 修 P0 工作量 3h，**可接受**
3. 修完后 c2g 是**真可用**的独立 package

**修 P0 时间表**：
- 30 min 修 IndentationError
- 1 h 加 5 个 smoke test
- 1 h 跑通 + 验证
- 30 min 修 pyproject 占位 + 加 LICENSE
- 总 3 h

---

## 13. 审计产物位置

- **本报告**：`/Users/xiamingxing/Workspace/.omo/_knowledge/audits/2026-06-15-c2g-deep-audit.md`
- **c2g-standalone branch**：`/Users/xiamingxing/Workspace` (本地) HEAD 4c7e7b38
- **bundle**：`/tmp/omostation-c2g.bundle` (119KB, 4 commits)
- **clone 验证**：`/tmp/c2g-standalone/` (12 files)

---

**审批**：X-Plane Audit Agent · 2026-06-15
**审计范围**：10 维度（结构/质量/依赖/测试/文档/standalone/集成/安全/历史/总评分）
**总评分**：4.6/10 (D+) — **关键阻塞**：`bridge.py:191 IndentationError`
