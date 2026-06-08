# CLAUDE.md — ecos 认知层

> eCOS v5 L0 Cognitive Layer · MOF 模型 · SSB 签名链 · BOS 路由

---

## 项目身份

ecos 是 eCOS v5 7 层架构的 **L0 认知层**。负责系统信息架构的底层根定义。

**核心职责**：
1. **MOF 元模型** — M3/M2/M1 三层 ~130 个 YAML 定义
2. **SSB 签名链** — 认知操作的不可篡改签名
3. **BOS URI 路由** — `bos://<domain>/<package>/<action>` 统一寻址
4. **X1-X4 治理维度** — 审计/新鲜度/价值/一致性

---

## 架构

```
L0 ecos
├── src/ecos/ssot/mof/       ← MOF 元模型 (SSOT)
│   ├── m3.yaml              ← 元元模型 (Layer/Type/Relation)
│   ├── ontology.yaml        ← 本体映射
│   ├── m2/                  ← 类型定义 (12 个 YAML)
│   └── m1/                  ← 实例定义 (~100+ 个 YAML)
│       ├── architecture/    ← 架构定义
│       ├── domain/          ← 19 个域定义 (L0-L4)
│       ├── process/         ← 流程 (CARDS 等)
│       ├── specification/   ← 约束 (12 个 CLAUDE 规范)
│       ├── bosroute/        ← BOS URI 路由
│       ├── artifact/        ← 制品脚本 (24 个 L4)
│       ├── skill/           ← 定时技能 (30 个)
│       ├── mechanism/       ← 执行机制
│       └── entity/          ← 实体定义
├── src/ecos/core/           ← 核心库 (ssb_client, signature)
├── src/ecos/ssot/tools/     ← MOF 工具链 (mof + OutputFormatter)
├── src/ecos/cli/            ← CLI 入口 (dashboard, scheduler)
└── src/ecos/services/       ← 服务层 (governance, integration)
```

---

## 快速命令

```bash
cd projects/ecos

# 测试 (197 tests)
uv run pytest tests/ -q

# MOF 验证
uv run mof list      # 列出 MOF 定义的域
uv run mof-validate  # 验证 YAML schema
uv run mof-audit     # 审计 MOF 一致性

# 格式化 + 检查
uv run ruff format src/ecos/
uv run ruff check src/ecos/

# 安装
uv sync
```

---

## MOF 建模约定

1. **M3 → M2 → M1 自上而下** — 修改 M1 前先检查 M2 类型定义
2. **每个 YAML 有 `id` + `layer`** — 唯一标识 + 层级归属
3. **层归属**: L0=认知/L1=运行时/L2=引擎/L3=入口/L4=自我
4. **SSOT 级联** — MOF YAML 是操作模型的唯一真相源
5. **`mof-validate` 应始终通过** — 新增 M1 后立即跑验证

---

## GPTCHAS

1. **MOF 是 SSOT** — L0 模型定义驱动所有上层代码生成
2. **不要直接改 MOF tool 的 output** — 修改 `_output.py` 影响所有 CLI
3. **Python 3.10+** — 非 kairon 的 3.13+
4. **测试路径是 `tests/`** — `pythonpath = ["src"]`
5. **SSB 签名链不可篡改** — 所有认知操作有签名验证
6. **MOF M1 目录按类型组织** — architecture/domain/process/specification/...
