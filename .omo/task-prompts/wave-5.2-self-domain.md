# Task Prompt: Wave 5.2 — L4 Self Domain

> 类型: P9 → P8 Task Prompt | 状态: backlog | 预估: 165min
> Phase: 5 → 5.2 | 负责人: prometheus | 日期: Day 3
> 前置: Wave 5.1.B (KOS EntityType 扩展) 已完成

## 一、目标

在KOS中新增self领域，提供身份画像、愿景系统、价值原则和认知框架的读写能力。创建3个MCP工具和1个Agent prompt注入脚本。

## 二、文件清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `kos/self/__init__.py` | 新建 | 模块声明 |
| `kos/self/api.py` | 新建 | get_profile, update_profile, get_current_role, get_vision_summary |
| `kos/self/mcp.py` | 新建 | SELF_TOOLS + SELF_HANDLERS导出 |
| `kos/mcp/server.py` | 修改 | import + dispatch补充self.前缀路由 |
| `~/.hermes/scripts/self_inject.sh` | 新建 | 每日首次注入L4上下文的shell脚本 |

## 三、验收标准

```
☐ python3 -c "from kos.self.api import get_profile; p=get_profile(); assert p['person'] == '老王'"
☐ python3 -c "from kos.self.api import get_current_role; r=get_current_role(); assert 'role_id' in r"
☐ KOS MCP Server list_tools 显示 self.get_profile, self.get_current_role, self.get_vision_summary
☐ self_inject.sh 可执行且输出L4上下文摘要
```

## 四、详细实现

### kos/self/api.py

数据存储: `~/.kos/self/profile.json`

```python
# get_profile() — 读取profile.json，不存在时创建默认
# update_profile(data) — 合并更新
# get_current_role(context_hint="") — 按时间判断: 工作日白天→最高优先级角色；非工作时间→找family角色
# get_vision_summary() — 返回愿景摘要字符串
```

profile.json初始内容:
```json
{
  "version": "v1",
  "person": "老王",
  "roles": [
    {"role_id": "role:weijiwei", "name": "卫健委信息科工程师", "priority": 1,
     "values": ["稳定性 > 新功能", "合规 > 效率"], "time_window": "工作日 09:00-18:00",
     "communication_style": "简洁正式", "tags": ["政务", "技术管理"]},
    {"role_id": "role:personal-dev", "name": "个人技术开发者/架构师", "priority": 2,
     "values": ["架构先行", "理论驱动", "红蓝对抗"], "time_window": "晚上+周末",
     "communication_style": "深度技术讨论", "tags": ["AI OS", "系统架构"]},
    {"role_id": "role:family", "name": "家庭角色", "priority": 3,
     "values": ["低心智负担", "可托管"], "time_window": "周末",
     "communication_style": "轻松", "tags": ["家事", "孩子"]}
  ],
  "vision": {
    "long_term": "蜂群智能体系 — 多人+多Agent集体智慧网络",
    "mid_term": "Workspace 联邦式 AI OS 在个人层面跑通",
    "current_okrs": {
      "Q2_2026": [
        {"kr": "架构收敛 — 4+1+3方案定稿", "progress": 100},
        {"kr": "eCOS Phase 10 全链路稳定", "progress": 100},
        {"kr": "知识管道全自动化", "progress": 60},
        {"kr": "多Agent协作初版跑通", "progress": 0}
      ]
    }
  },
  "principles": [
    {"name": "架构先行，理论驱动", "weight": 0.9, "source_axiom": "逻辑自洽比功能堆砌更重要"},
    {"name": "红蓝对抗，安全第一", "weight": 1.0, "source_axiom": "不可逆操作必须经双人验证"},
    {"name": "隐私绝不外泄", "weight": 1.0, "source_axiom": "私人信息绝对不外泄"},
    {"name": "成本敏感，零token优先", "weight": 0.8, "source_axiom": "资源有限"},
    {"name": "持久对象优于临时运行", "weight": 0.7, "source_axiom": "运行时状态不是唯一真相"}
  ],
  "frameworks": {
    "thinking_stack": "第一性原理 → 理论 → 框架 → 架构 → 场景 → 应用",
    "workflow": "审计 → 规划 → Review → 执行 → 测试 → 再审计 → 清零",
    "output_preference": {"format": "架构图 + 决策卡片 + 可执行步骤 + 验证命令"},
    "verification_driven": true,
    "validation_pattern": "先B后A"
  }
}
```

### kos/self/mcp.py

严格按照 `09-架构Review与机制设计.md` 第2节的模块契约格式：
- 导出 `SELF_TOOLS` dict (3个工具)
- 导出 `SELF_HANDLERS` dict (3个handler函数)
- 每个handler返回dict（不能raise）

### kos/mcp/server.py 修改

在run_stdio的TOOLS定义处加入:
```python
from kos.self.mcp import SELF_TOOLS, SELF_HANDLERS
TOOLS.update(SELF_TOOLS)
HANDLERS.update(SELF_HANDLERS)
```
dispatch中self.前缀路由自然由HANDLERS处理，不需额外逻辑。

### self_inject.sh

```bash
#!/bin/bash
# 每天首次交互时注入L4上下文到Hermes prompt
# 由Hermes config context_preload.schedule=daily_first 触发
python3 -m kos.self.api get_vision_summary
```

## 五、执行步骤

### Step 1: 创建 kos/self/__init__.py
### Step 2: 创建 kos/self/api.py (4个函数 + profile.json默认结构)
### Step 3: 创建 kos/self/mcp.py (3个MCP工具)
### Step 4: 修改 kos/mcp/server.py (import + 注册)
### Step 5: 创建 self_inject.sh
### Step 6: 验证

```bash
cd ~/Workspace/kos
python3 -c "from kos.self.api import get_profile; p=get_profile(); print('person:', p['person'])"
python3 -c "from kos.self.api import get_current_role; r=get_current_role(); print('role:', r.get('name','?'))"
python3 -c "from kos.self.mcp import SELF_TOOLS; print('tools:', list(SELF_TOOLS.keys()))"
```

## 六、输出

| 文件 | 操作 |
|------|------|
| `kos/self/__init__.py` | 新建 |
| `kos/self/api.py` | 新建 |
| `kos/self/mcp.py` | 新建 |
| `kos/mcp/server.py` | 修改(import+TOOLS+HANDLERS) |
| `~/.hermes/scripts/self_inject.sh` | 新建 |
| `.omo/TASK_POOL.md` | T069-T072 → done |
| `.omo/STATE.md` | Wave 5.2更新 |

## 七、→ 下一个Wave

完成后触发 **Wave 5.3 (L3 Collab Domain)**。
