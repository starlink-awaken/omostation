---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# 治理宪章执行机制: 强制约束与长期保鲜

> 补充 governance-charter-v1.md · 2026-06-06

---

## 一、防御层级 (Defense in Depth)

```
Layer 0: 文档声明 (CLAUDE.md §0)
  ↓ Agent 启动即读, 不可跳过
  
Layer 1: CI 验证 (GitHub Actions)
  ↓ push 时跑, 阻断违规合并
  
Layer 2: Runtime 检查 (MCP tools)
  ↓ Agent 每次操作前调用 cards_check
  
Layer 3: 周常自动化 (ecos-health-check)
  ↓ 定时扫描, 输出保鲜报告
```

## 二、每层具体实现

### 2.0 文档层: CLAUDE.md §0

```markdown
## §0 启动强制指令 (MANDATORY · 不可跳过)

**Agent 首次响应前必须通过 cockpit MCP 调用 workspace_context。**
禁止: 未获取上下文直接修改代码。
治理宪章: .omo/_knowledge/management/governance-charter-v1.md
```

**强制执行**: CLAUDE.md 是 Agent 启动时第一个读的文件。只要人在、文档在、Agent 就会遵守。这是最轻量但最有效的约束层——不需要代码，只需要 SSOT 存在。

### 2.1 CI 层: 四个自动化检查

```
.github/workflows/
  ┌─ interface-check.yml    → 接口注册表保鲜
  ├─ port-conflict.yml       → 端口冲突检测
  ├─ dependency-check.yml    → 跨层 import 违规
  └─ doc-freshness.yml       → CLAUDE.md 保鲜
```

每个 CI script 是独立的 Python 脚本，放在 `scripts/` 下:

```python
# scripts/check-interfaces.py
# 读取 protocols/interface-registry.yaml
# 扫描各项目 pyproject.toml [project.scripts]
# 检查: 1. 未注册的 CLI → 报错
#       2. 端口冲突 → 报错
#       3. module_path 不存在 → 报错
# exit 0 = pass, exit 1 = fail

# scripts/check-port-conflicts.py
# 扫描所有端口引用 → 去重 → 冲突即 fail

# scripts/check-cross-deps.py
# 检查跨层 import: cockpit 不能 import kairon.xxx
# 检查反向依赖: kairon 不能 import cockpit

# scripts/check-doc-freshness.py
# 扫描 CLAUDE.md/AGENTS.md 的 last_updated 日期
# >30 天 → CI 黄色警告
# >90 天 → CI 红色阻断
```

### 2.2 Runtime 层: MCP 工具

```python
# cockpit MCP: cards_check() — 操作前验证
# Agent 在执行任何修改前调用

@mcp.tool()
def cards_check(operation: str = "") -> str:
    """操作前约束验证。检查: 代码冻结/端口冲突/跨层import"""
    violations = []
    
    # 检查 1: OMO 是否 code_freeze
    omo = yaml.safe_load(open(".omo/_truth/goals/current.yaml"))
    if omo.get("code_freeze"):
        violations.append("代码冻结中")
    
    # 检查 2: 是否涉及端口变更
    if "port" in operation.lower():
        registry = yaml.safe_load(open("protocols/interface-registry.yaml"))
        # 检查新端口是否已注册
    
    # 检查 3: 是否修改核心架构文件
    restricted = [".omo/_truth/", "protocols/", "LAYER-INDEX.md"]
    for path in restricted:
        if path in operation:
            violations.append(f"修改受限路径 {path}: 需 OMO 提案")
    
    return json.dumps({"compliant": len(violations)==0, "violations": violations})
```

### 2.3 周常自动化: 保鲜扫描

```python
# scripts/ecos-health-check.py
# 一键扫描:
#   1. 9 项目 CI 最后运行时间
#   2. CLAUDE.md §0 是否存在
#   3. INTERFACE.yaml 是否存在 (每个项目)
#   4. P0 债务数量
#   5. 端口冲突
# 输出: 控制台彩色报告 + JSON (可选)
```

---

## 三、收敛机制

### 3.1 接口注册表自收敛

```
每次 CI 运行:
  1. 扫描所有 pyproject.toml → 取出 [project.scripts]
  2. 对比 protocols/interface-registry.yaml
  3. 缺失 → 报错 (CLI 未注册)
  4. 多余 → 警告 (registry 有僵尸条目)
```

这样: 任何人加 CLI/MCP/端口，如果不更新 registry，CI 就红。注册表永远与代码同步。

### 3.2 端口自收敛

```
每次 CI 运行:
  1. 扫描所有 *.py 中的 port= 数字
  2. 去重 → 冲突 → CI red
  3. 未在 registry 注册 → CI red
```

### 3.3 依赖自收敛

```
每次 CI 运行:
  1. 扫描所有跨项目 import
  2. 对照 §2 依赖矩阵
  3. 违规 → CI red
```

---

## 四、长期记忆

### 4.1 CodeBuddy Memory (会话级)

```markdown
# ~/.codebuddy/projects/.../memory/governance-charter-v1.md
---
name: 治理宪章 v1
type: reference
---
每次会话启动自动加载。
包含: 10 条不可变原则 + 分层矩阵引用
```

### 4.2 OMO 债务 (持久化)

```
每周生成保鲜报告 → 发现问题 → omo debt register
  → 标注 X2 (保鲜维度)
  → 分配 owner
  → 追踪直到修复
```

### 4.3 周常驱动

```bash
# 每周一早上 (或 CI cron):
workspace health           # 一键健康检查
omo debt list --stale      # 列出过期债务
check-interfaces.py         # 接口一致性
check-doc-freshness.py      # 文档保鲜
# → 输出保鲜报告 → 如果异常 → omo debt register
```

### 4.4 Phase 门禁

```
Phase 切换时必须:
  □ 全量测试通过
  □ 所有 P0 债务关闭
  □ 接口注册表一致
  □ 端口无冲突
  □ 文档保鲜 (<30d)
  □ governance-charter 审查通过
```

---

## 五、如果有人绕过呢？

### 5.1 你绕不过 CI

```
git push → CI 运行 → interface-check → 失败 → 不能合并
```

### 5.2 你绕不过 Code Review

```
每次 git commit → pre-commit hook → ruff + interface check
```

### 5.3 你绕不过周报

```
每周 health check → 发现端口冲突/债务/文档过期
→ omo debt register → 进入追踪
→ 责任人必须响应
```

### 5.4 你绕不过 Phase 门禁

```
Phase 结束 → 门禁检查 → 发现违规
→ Phase 不能标记 done
→ OMO goals 停留在 current
→ 所有人都能看到
```

---

## 六、总结: 五层防线

| 防线 | 触发时机 | 阻断力 | 覆盖 |
|------|---------|--------|------|
| CLAUDE.md §0 | Agent 启动 | 引导 (软) | Agent 行为 |
| CI scripts | git push | 阻断 (硬) | 接口/端口/依赖 |
| MCP cards_check | Agent 操作前 | 警告 (中) | 运行时约束 |
| ecos-health-check | 每周 cron | 报告 (软) | 全系统健康 |
| Phase gate | Phase 结束 | 阻断 (硬) | 全局一致性 |

**核心**: 不需要人记得——每次 push 和每次 cron 都会提醒。
