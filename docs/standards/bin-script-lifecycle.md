# bin/ Script Lifecycle Standard

> 最后更新: 2026-08-30
> 状态: active

## 1. 分层组织规范

所有 `bin/` 脚本必须按架构分层放置：

```
bin/
  L0/          # 协议层：MOF compiler、L0 constraint checker
  L1/          # 运行时：submodule、runtime health
  L2/          # 引擎面：omo、knowledge、metaos
  I0/          # 织层：agora、bos routing
  L3/          # 入口层：cockpit readiness
  L4/          # 自我层：l4-kernel
  M0/          # 横切框架：model-driven tools
  X/           # 横切扩展：bus-foundation、observability
  shared/      # 跨层工具：argparse helper、state helper
```

## 2. 脚本声明规范

每个新脚本必须在头部声明：

```python
SFOP_SLOT = "S"  # K/H/P/C/B/J/O/F
DAO_LAYER = "L2"  # L0/L1/L2/L3/L4/I0/M0/X
```

## 3. 脚本生命周期

### 3.1 注册前置

新脚本必须在 `bin/_registry/scripts/<layer>/` 下有对应 YAML 注册项，否则 CI 拒绝。

### 3.2 1:1 置换

新增 1 个脚本必须 retire/归档/删除 1 个旧脚本。这是硬性 CI 门禁。

### 3.3 30 天观察期

被合并脚本移至 `_archive/` 后保留 30 天，确认无调用方后删除。

### 3.4 Thin Wrapper 兼容期

被合并脚本保留为 thin wrapper（≤10 行），30 天后删除。

## 4. 状态管理规范

所有 state file 必须通过 `bin/ssot/state-manager.py` 管理，不允许直接 `json.dump` 到 `.omo/state/`。

## 5. 测试门槛

新脚本必须有测试，否则 CI 警告→拒绝。
