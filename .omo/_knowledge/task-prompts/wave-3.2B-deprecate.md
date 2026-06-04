# Task Prompt: Wave 3.2.B — 废弃清理

> 类型: P9 → P8 Task Prompt | 状态: pending (depends on Wave 3.1) | 预估: 45min

## 一、目标

执行 Wave 1.2.B 审计后的决策：标记废弃模块、保持代码库洁净。

## 二、范围

| 事项 | 决策依据 | 操作 |
|------|---------|------|
| agora monitoring/ 模块 | 刚修复但从未被外部调用 | 加 `@deprecated` 标注 |
| MetaOS | Wave 1.2.B 审计结论 | 归档或补 README |
| SSOT | Wave 1.2.B 审计结论 | 归档或补 README |

## 三、验收标准

```
☐ agora monitoring/ 所有文件 import 时有 deprecation warning
☐ MetaOS 决策已在 AGENTS.md 和 STATE.md 记录
☐ SSOT 决策已在 AGENTS.md 和 STATE.md 记录
☐ CLAUDE.md 治理规则 4 "废弃即标记" 已执行
```

## 四、执行步骤

### Step 1: monitoring deprecation

```python
# agora/src/agora/monitoring/__init__.py 文件首行
import warnings
warnings.warn(
    "agora.monitoring is deprecated and will be removed in a future version. "
    "Use agora health CLI instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

### Step 2: MetaOS/SSOT 决策落地

编辑 `AGENTS.md`，添加明确的 decision record。

## 五、输出

| 文件 | 操作 |
|------|------|
| `agora/src/agora/monitoring/__init__.py` | 加 deprecation warning |
| `AGENTS.md` | 更新 MetaOS/SSOT 决策 |
| `.omo/TASK_POOL.md` | T051-T053 → done |

## 六、→ Phase 3 门禁

```
☐ workspace status 可用
☐ workspace demo 30 秒完整版
☐ agentmesh 编译通过
☐ WorkspaceMCPClient → Agora 链路验证
☐ 废弃模块已标记
```

全部通过 → **触发 Phase 4**。
