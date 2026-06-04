# Task Prompt: T140 — 进化引擎

> 类型: P10 Task | 预估: 3天 | Wave: 10.3 | Phase: 10
> 参考: X2抗熵进化层设计 + eCOS复盘机制

## 一、目标

每次Phase/复杂Task完成后自动分析执行数据，识别改进模式，生成可落地的改进建议。部分低风建议自动落地。

## 二、设计

### 文件: `~/.hermes/scripts/evolution_engine.py` (~200LOC)

```python
#!/usr/bin/env python3
"""Evolution Engine — 自动复盘与持续改进"""

class EvolutionEngine:
    """分析执行数据→识别模式→生成建议→自动落地"""
    
    def analyze_phase(self, phase_id: str, phase_data: dict = None) -> dict:
        """分析Phase执行数据"""
    
    def analyze_task(self, task_id: str, task_log: list[dict]) -> dict:
        """分析单个Task执行过程"""
    
    def _find_patterns(self, events: list[dict]) -> list[dict]:
        """识别重复模式"""
        # 1. 重复错误: 同一error出现3次以上
        # 2. 用户纠正: user纠正agent行为的记录
        # 3. 效率低下: 超过预估时间2倍以上的task
        # 4. 遗漏步骤: task完成但用户补充了步骤
    
    def _generate_suggestion(self, pattern: dict) -> dict:
        """将模式转化为具体建议"""
    
    def auto_apply(self, suggestion: dict) -> bool:
        """自动落地（仅auto_apply=True的建议）"""
    
    def list_pending(self) -> list[dict]:
        """列出待审批的改进建议"""
    
    def apply_pending(self, suggestion_id: str) -> bool:
        """手动批准一条建议"""
}

# 建议格式:
{
    "id": "evol-20260525-001",
    "type": "skill_patch" | "memory_update" | "cron_add" | 
           "principle_revise" | "config_change" | "doc_update",
    "target": "skill:systematic-debugging",
    "title": "调试skill添加依赖检查步骤",
    "change": "在第3步'定位根因'之前增加'检查所有依赖'步骤",
    "impact": "medium",
    "auto_apply": False,  # 高风险需要人工审
    "evidence": ["T099 took 2x estimated time", "user said '检查依赖'"],
    "created_at": "2026-05-25",
    "status": "pending" | "applied" | "rejected"
}
```

### 自动落地规则

| 建议类型 | 自动落地条件 | 人工审批条件 |
|---------|-------------|-------------|
| memory_update | 用户明确纠正过 → 自动 | 模糊建议 |
| skill_patch | 步骤错误+证据明确 | 影响多条skill |
| cron_add | 明确周期需求 | 依赖外部服务 |
| principle_revise | — | 必须人工 |
| config_change | — | 必须人工 |
| doc_update | 事实错误 | 新功能文档 |

## 三、验证

```bash
# 3.1 模式识别测试
python3 -c "
import sys; sys.path.insert(0, '/Users/xiamingxing/.hermes/scripts')
from evolution_engine import EvolutionEngine
import json

ee = EvolutionEngine()

# 模拟Phase执行日志
phase_log = [
    {'type': 'task', 'id': 'T099', 'estimated_days': 2, 'actual_days': 4, 'status': 'done'},
    {'type': 'user_correction', 'when': 'T099执行中', 'content': '先做审计再看代码'},
    {'type': 'error', 'when': 'T100', 'error': 'ImportError: no module config'},
    {'type': 'error', 'when': 'T101', 'error': 'ImportError: no module config'},
    {'type': 'user_correction', 'when': 'T102', 'content': '不要使用python3.9'},
]

result = ee.analyze_phase('Phase 9 Mock', {'tasks': phase_log})
suggestions = result.get('suggestions', [])
print(f'Phase analysis generated {len(suggestions)} suggestions:')
for s in suggestions:
    print(f'  [{s[\"impact\"]:6s}] {s[\"type\"]:18s} → {s[\"title\"][:50]}')
    print(f'         evidence: {s.get(\"evidence\", [])}')

# 验证至少检测到效率低下+错误模式
assert len(suggestions) >= 2
print('T140: ALL PASSED')
" 2>&1

# 3.2 自动落地测试
python3 -c "
from evolution_engine import EvolutionEngine
import json
ee = EvolutionEngine()

# 模拟一条可自动落地的建议
suggestion = {
    'type': 'memory_update',
    'target': 'memory:user_preference',
    'title': '记录老王偏好架构先行方法',
    'change': '老王明确说过架构先行理论驱动',
    'evidence': [\"user: '先做好调研和分析'\", \"user: '架构思维强'\"],
    'impact': 'low',
    'auto_apply': True,
}
applied = ee.auto_apply(suggestion)
print(f'Auto-apply result: {json.dumps(applied, ensure_ascii=False)[:100]}')
assert applied.get('status') == 'applied' or applied.get('applied') == True
print('T140 AUTO-APPLY: PASSED')
" 2>&1

# 3.3 待审批列表测试
python3 -c "
from evolution_engine import EvolutionEngine
ee = EvolutionEngine()
pending = ee.list_pending()
print(f'Pending suggestions: {len(pending)}')
# 至少有一条需要审批的（模拟数据）
print('T140 LIST: PASSED')
" 2>&1
```

## 四、验收

```
☐ 能分析Phase执行日志→识别至少4种模式(重复错误/用户纠正/效率低/遗漏)
☐ 每种模式对应1+条具体建议
☐ 自动落地：memory_update类型可自动执行
☐ 待审批列表：高风险建议等待人工
☐ 审批通过后自动执行落地
☐ 所有单元测试通过
