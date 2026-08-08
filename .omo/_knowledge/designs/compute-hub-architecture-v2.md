# 算力中枢架构设计 v2.0

> 2026-08-09 · 基于 aetherforge + omlxc + LiteLLM + 业内调研
> 状态: 设计完成, P0实施中

## 一、现状总结

### 已有资产
- **本地**: omlxc 22个MLX模型, 3节点(MBP 128G + mini 24G + Y7000P 8G)
- **网关**: LiteLLM proxy :4000, 29别名+4通配+fallback chain
- **自启**: omlxc autostart :9000 (已启动)
- **云端Key**: Z.AI(GLM), DeepSeek(余额0%), Kimi, LongCat, BigModel, Minerva
- **数据源**: codexbar(60+provider配额), cc-switch DB(57模型定价), models CLI(完整定价)
- **Agent**: omo 6 agents + LLM深判(已接入omlx coding-fast)

### 已验证可用
- coding-fast (Qwen3.6-35B, 28token JSON eval, 2.3 tok/s) ✅
- gateway :4000 (29别名路由+fallback) ✅
- autostart :9000 ✅

### 待解决
- NVIDIA NIM / OpenRouter API Key未注册
- agent代码直连omlx(:8081)应改为走gateway(:4000)
- 免费模型池未建立
- codexbar配额数据未接入路由决策

## 二、目标架构

```
Layer 4: 消费层 (omo agents, CLI, MCP, 外部消费者)
    ↓
Layer 3: 语义路由层 (Phase 2: 规则→嵌入→RouteLLM)
    ↓
Layer 2: LiteLLM网关 (:4000, 已运行)
    别名映射 · fallback chain · cost tracking · 熔断 · 限流
    ↓
Layer 1: 算力后端
    ├── omlxc本地 (22 MLX模型, 免费, 低延迟)
    ├── 免费云端池 (NVIDIA NIM 100+模型, OpenRouter 28+模型)
    └── 付费云端 (DeepSeek需充值, Z.AI/Kimi/LongCat已有Key)

Data Layer (决策数据, 只读):
    ├── codexbar → 实时配额% (5min缓存)
    ├── cc-switch DB → API Key + Provider配置
    └── models CLI → 模型定价 + 能力
```

## 三、实施路线

### P0: 即时修复 (0.5d) — 让系统跑起来
- [x] omlxc autostart start
- [x] gateway :4000 运行中 (29别名)
- [x] coding-fast模型在线
- [ ] agent代码改用gateway :4000 (别名coder-fast)
- [ ]LiteLLM config加云端Provider (Z.AI, Kimi, LongCat)

### P1: 免费模型池 (1d) — 常态化机制
- [ ] 注册NVIDIA NIM API Key (build.nvidia.com, 免费)
- [ ] 注册OpenRouter API Key (openrouter.ai, $10 deposit → 1000 req/day)
- [ ] LiteLLM config加免费模型 (NVIDIA 100+, OpenRouter 28+)
- [ ] 建 `bin/ssot/free-model-scanner.py`:
      每日扫描NVIDIA/OpenRouter可用免费模型
      自动更新LiteLLM config
      记录到 `.omo/_knowledge/free-model-pool/`
- [ ] 进化agent定期维护池子 (常态化)

### P2: 配额感知 (1d)
- [ ] `bin/ssot/quota-checker.py`: 封装codexbar查询(5min缓存)
- [ ] 路由前检查: provider配额<10% → 跳过
- [ ] scanner定期记录配额到metrics

### P3: 语义路由 (1d, Phase 2)
- [ ] 规则路由: token长度+关键词+agent类型 → model选择
- [ ] 配额+成本感知: codexbar+models数据驱动路由

### P4: Dashboard (1d)
- [ ] omlxc dashboard增强
- [ ] 全局大盘: 模型/配额/成本/节点/请求量

### 总计 P0-P1: ~1.5d (核心可用)
### 总计 P0-P4: ~4.5d (完整算力中枢)

## 四、LiteLLM Config增强方案

### 本地模型 (已有, 无需改)
```yaml
# 29个别名已配置, fallback chain已设
coder-fast → omlx:8081 (Qwen3.6-35B)
reasoner   → omlx:8083 (GLM-4.7)
```

### 云端Provider (需加到litellm-config.yaml)
```yaml
  # ========== 云端: 已有Key ==========
  - model_name: glm                    # Z.AI/GLM (Anthropic compat)
    litellm_params:
      model: anthropic/glm-4.7-flash
      api_base: https://open.bigmodel.cn/api/anthropic
      api_key: os.environ/ZHIPU_API_KEY
  - model_name: kimi                   # Moonshot Kimi
    litellm_params:
      model: openai/moonshot-v1-auto
      api_base: https://api.moonshot.cn/v1
      api_key: os.environ/KIMI_CODE_API_KEY
  - model_name: longcat                # LongCat
    litellm_params:
      model: openai/longcat-flash
      api_base: https://api.longcat.chat/openapi
      api_key: os.environ/LONGCAT_API_KEY

  # ========== 云端: 免费池 (需注册Key) ==========
  - model_name: nvidia-deepseek       # NVIDIA NIM 免费
    litellm_params:
      model: openai/deepseek-ai/deepseek-r1
      api_base: https://integrate.api.nvidia.com/v1
      api_key: os.environ/NVIDIA_API_KEY
  - model_name: or-free               # OpenRouter免费路由
    litellm_params:
      model: openrouter/openrouter/free
      api_key: os.environ/OPENROUTER_API_KEY
```

### 增强Fallback Chain
```yaml
router_settings:
  fallbacks:
    - coder: [coder-fast, kimi, or-free]       # 本地→Kimi→免费池
    - reasoner: [coder, glm, nvidia-deepseek]  # 本地→GLM→NVIDIA
    - coder-fast: [mini-chat, or-free]         # 主力→mini→免费池
```

## 五、免费模型池维护机制 (常态化)

### 数据源
1. NVIDIA NIM: build.nvidia.com/models (100+免费, 40 RPM)
2. OpenRouter: openrouter.ai/collections/free-models (28+免费, 20 RPM)
3. OpenCode Zen: opencode.ai/zen (3-5个轮换免费)

### Scanner设计
```python
# bin/ssot/free-model-scanner.py
# 每日运行, 扫描免费模型可用性, 更新LiteLLM config

def scan_nvidia_free():
    """查NVIDIA NIM免费模型列表"""
    # GET https://integrate.api.nvidia.com/v1/models
    # 过滤免费模型

def scan_openrouter_free():
    """查OpenRouter免费模型 ($0/token)"""
    # GET https://openrouter.ai/api/v1/models
    # 过滤 pricing.prompt == "0"

def update_litellm_config(models):
    """更新litellm-config.yaml, 重启gateway"""
```

### 与进化agent集成
进化agent定期(每周)运行free-model-scanner → 发现新免费模型 → 创建EVO-PROP debt item → 人审后加入LiteLLM config → gateway自动路由。

## 六、设计原则

1. **不重写LiteLLM** — 别名/fallback/cost/熔断全用内置
2. **不重写omlxc** — 模型生命周期/集群管理已完整
3. **数据层只读** — codexbar/cc-switch/models不修改
4. **路由层无状态** — 每次请求独立决策
5. **graceful降级** — 任何后端挂了→fallback→不阻塞
6. **免费优先** — 本地>免费云端>付费云端
