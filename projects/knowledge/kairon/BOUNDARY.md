---
title: BOUNDARY
type: doc
---

# kairon — System Boundary

> 本文档描述 kairon 与 eCOS 系统其他部分的边界：暴露的接口、依赖的上游、影响的下游。
>
> 系统全景参见：[`../../docs/PANORAMA.md`](../../docs/PANORAMA.md)

---

## 1. 暴露接口

### BOS URI

- `bos://memory/kos/search`
- `bos://memory/kronos/ingest`
- `bos://analysis/minerva/research`
- `bos://analysis/ontoderive/derive`
- `bos://analysis/codeanalyze/scan`
- `bos://capability/forge/registry`

### 入口

- **CLI**: `per-package (kos, kronos, minerva, ...)` 
- **BOS**: `bos://memory/*, bos://analysis/*, bos://persona/*` 

## 2. 上游依赖

- agora (I0)
- gbrain (L2 memory)
- ecos (L0 MOF)

## 3. 下游影响

- cockpit
- omo
- runtime

## 4. 配置 / SSOT

- 项目源码：`projects/kairon/`
- 入口定义：`projects/kairon/pyproject.toml` 或 `package.json`
- 测试：`cd projects/kairon && make test-diff  # or make test`

## 架构演进与项目边界索引

参见工作区架构演进与项目边界：[`../../docs/ARCHITECTURE-EVOLUTION.md`](../../docs/ARCHITECTURE-EVOLUTION.md)
