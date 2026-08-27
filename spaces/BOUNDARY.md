# spaces — System Boundary

> 本文档描述 spaces 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 架构演进对比参见：[`docs/ARCHITECTURE-EVOLUTION.md`](../docs/ARCHITECTURE-EVOLUTION.md)

---

## 1. 暴露接口

### BOS URI



### 入口

- **Config**: `registry.yaml, system-space.yaml, runtime-space.yaml` 

## 2. 上游依赖



## 3. 下游影响

- agora (routing)
- runtime (KEI admission)

## 4. 配置 / SSOT

- 项目源码：`projects/spaces/`
- 入口定义：`projects/spaces/pyproject.toml` 或 `package.json`
- 测试：`bash tests/integration/run-all.sh`
