---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: T137 — TokenJuice 压缩层

> 类型: P10 Task | 预估: 4天 | Wave: 10.2 | Phase: 10
> 参考: OpenHuman TokenJuice (理念借鉴，独立实现)

## 一、目标

在Agora Router中嵌入数据压缩中间件，对MCP调用的输入/输出做智能压缩，目标降低30-50% token消耗。

## 二、设计

### 文件: `~/Workspace/agora/src/agora/compressor.py` (~200LOC)

```python
class Compressor:
    """智能数据压缩层"""
    
    def compress(self, content: str, content_type: str = "auto") -> CompressedResult:
        """自动检测类型并压缩"""
    
    def detect_type(self, content: str) -> str:
        """auto → json/html/code/plaintext/error"""
    
    def compress_json(self, content: str) -> str:
        """JSON短key压缩：{"my_long_key": v} → {"a": v}"""
    
    def compress_html(self, content: str) -> str:
        """HTML→Markdown"""
    
    def compress_urls(self, content: str) -> tuple[str, dict]:
        """URL检测→替换为{ref_N}→独立存储"""
    
    def dedup_summary(self, content: str, similarity_threshold: float = 0.85) -> str:
        """重复内容→仅保留摘要"""
    
    def compress_stacktrace(self, content: str) -> str:
        """错误栈→只保留首行+关键异常类型"""

class CompressedResult:
    content: str       # 压缩后内容
    original_len: int  # 原始长度
    compressed_len: int
    ratio: float       # 压缩率 (0-1)
    stats: dict        # 各项压缩策略的贡献
```

### Agora Router 集成

```python
# agora/router.py 增强
from agora.compressor import Compressor

class Router:
    def __init__(self):
        self.compressor = Compressor()
    
    def _compress_params(self, params: dict) -> dict:
        """遍历参数中的字符串值，对大文本做压缩"""
        compressed = {}
        stats = {"total_before": 0, "total_after": 0}
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 500:
                result = self.compressor.compress(value)
                compressed[key] = result.content
                stats["total_before"] += result.original_len
                stats["total_after"] += result.compressed_len
            else:
                compressed[key] = value
        return compressed, stats
```

### 压缩策略表

| 内容类型 | 策略 | 预期压缩率 |
|---------|------|-----------|
| JSON (MCP参数) | 短key | 20-40% |
| HTML (网页) | → Markdown | 40-60% |
| 代码 (告警/报错) | Stack trace裁剪 | 30-50% |
| 长URL | 短ref替换 | 50-70% |
| 重复内容 | 去重摘要 | 60-80% |
| 普通文本 | 摘要化 (长度>3000char) | 30-50% |

## 三、验证

```bash
# 3.1 基础压缩测试
python3 -c "
import sys; sys.path.insert(0, '/Users/xiamingxing/Workspace/agora/src')
from agora.compressor import Compressor
import json

c = Compressor()

# HTML压缩
html = '<html><body><div class=\"content\"><p>这是一段HTML内容需要压缩</p>' * 50
r = c.compress(html)
assert r.ratio > 0, f'Expected compression, got {r.ratio}'
print(f'HTML: {r.original_len} → {r.compressed_len} ({r.ratio*100:.0f}% saved)')

# JSON短key
json_content = json.dumps({'very_long_parameter_name': 'some_value', 'another_long_name': 'more'})
r2 = c.compress(json_content, 'json')
print(f'JSON: {r2.original_len} → {r2.compressed_len} ({r2.ratio*100:.0f}% saved)')

# URL压缩
text_with_url = '参考文档: https://very-long-url.example.com/a/b/c/d/e/f?param1=value1&param2=value2'
r3 = c.compress(text_with_url)
print(f'URL: {r3.original_len} → {r3.compressed_len} ({r3.ratio*100:.0f}% saved)')

# Stack trace压缩
trace = 'Traceback (most recent call last):\n  File \"a.py\", line 10, in main\n  File \"b.py\", line 20, in run\nTypeError: unsupported operand type(s) for |'
r4 = c.compress(trace, 'error')
print(f'Trace: {r4.original_len} → {r4.compressed_len} ({r4.ratio*100:.0f}% saved)')

print('T137: ALL PASSED')
" 2>&1

# 3.2 压缩效果基准测试
python3 -c "
from agora.compressor import Compressor
c = Compressor()

# 模拟真实场景
samples = [
    ('{"arguments": {"query": \"架构先行理论驱动\"}}', 'json'),
    ('<html><body><p>' + '测试数据' * 100 + '</p></body></html>', 'html'),
    ('请分析这段代码: ' + 'print(\"hello world\")' * 200, 'code'),
]

total_before = 0
total_after = 0
for content, ctype in samples:
    r = c.compress(content, ctype)
    total_before += r.original_len
    total_after += r.compressed_len
    print(f'  {ctype:10s} {r.original_len:6d} → {r.compressed_len:6d} ({r.ratio*100:.0f}%)')

overall = (total_before - total_after) / total_before * 100
print(f'---')
print(f'Overall: {total_before} → {total_after} ({overall:.0f}% saved)')
assert overall >= 20, f'Expected ≥20% compression, got {overall}%'
print('T137 BENCHMARK: PASSED')
" 2>&1
```

## 四、验收

```
☐ Compressor能处理JSON/HTML/URL/Stack trace/Text五种类型
☐ 每种类型压缩率≥20%
☐ Agora Router集成：所有MCP调用过压缩层
☐ 压缩统计：每次调用记录原始/压缩大小
☐ 无损压缩：JSON短key可逆（key mapping存了映射表）
☐ 单元测试全部通过
