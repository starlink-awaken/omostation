# Phase 1 — Eidos + KOS 知识基座实现计划

## TL;DR

> **目标**: 创建 Eidos 知识定义系统 + KOS ingest 接入 46k 知识文件
> **工作流**: Phase 1.1→1.2→1.3 顺序, 1.4-1.5-1.6 并行
> **预计**: 3-5 天
> **执行**: `/start-work`

---

## Context

### 架构定位

```
Eidos (知识定义/Schema) ← JSON Schema → KOS (知识存取/索引/检索)
                                          ← Fact Schema → OntoDerive (推理)
```

Eidos 是全局知识定义层（新建），KOS 是知识存取层（进化），OntoDerive 是知识推导层（适配）。

### 设计原则
- 三层分离：定义/存取/推导各司其职，通过 JSON Schema 契约通信
- Eidos 零外部依赖，纯 Python
- KOS 保持现有架构不动，只加 ingest 子命令
- 所有 Schema 先走最小可行版本，再迭代细化

---

## Execution Strategy

```
Wave 1 (顺序执行 — 必须先建 Eidos):
├── 1.1 创建 Eidos 项目 + pyproject.toml + git init
├── 1.2 实现核心 3 个 Schema (KnowledgeCard, Fact, OntologyNode)
└── 1.3 实现 validator + CLI

Wave 2 (Eidos 就绪后，并行):
├── 1.4 KOS 加 ingest 命令
├── 1.5 KOS 产出走 Eidos 校验
└── 1.6 批量索引 knowledge/ingested/ (46k)
     └── 1.7 验证索引质量
```

---

## TODOs

- [x] 1.1 创建 Eidos 项目

  **What to do**:
  - 创建目录结构: `eidos/eidos/schema/`, `eidos/schemas/`, `eidos/tests/`
  - 写 `pyproject.toml`:
    - name: eidos, version: 0.1.0
    - requires-python: >=3.10
    - scripts: `eidos = eidos.cli:main`
    - optional-dependencies: dev = ["pytest", "ruff"]
  - 写 `eidos/__init__.py` — 空文件带注释
  - 写 `.gitignore` — 标准 Python + `.venv/`
  - 写 `README.md` — 项目用途 + CLI 示例
  - `git init && git add -A && git commit -m "chore: init eidos project"`
  - `.venv/bin/pip install -e ".[dev]"` 验证可安装

  **Must NOT do**:
  - 不要添加任何外部依赖（Eidos 必须是零依赖）

  **Recommended Agent Profile**: quick
  **Parallelization**: Wave 1, sequential

  **QA Scenarios**:
  ```bash
  cd /Users/xiamingxing/Workspace/eidos
  # Scenario 1: 安装验证
  .venv/bin/python3 -c "import eidos; print(eidos.__version__)"
  # Scenario 2: CLI 可用
  .venv/bin/python3 -m eidos.cli --help
  ```

- [x] 1.2 实现核心 3 个 Schema

  **What to do**:
  创建 `eidos/eidos/schema/__init__.py` (空)
  创建 `eidos/eidos/schema/knowledge_card.py`:

  ```python
  """KnowledgeCard — KOS 知识点的类型定义。"""
  from dataclasses import dataclass, field
  from datetime import datetime
  from typing import Optional

  @dataclass
  class Relation:
      target_id: str
      relation_type: str  # "references" | "parent" | "child" | "derived_from"
      label: str = ""

  @dataclass
  class KnowledgeCard:
      id: str
      title: str
      content: str
      source: str               # 来源路径
      source_type: str          # "ingested" | "obsidian" | "kos" | "eidos"
      schema_type: str          # "KnowledgeCard" | ...
      tags: list[str] = field(default_factory=list)
      relations: list[Relation] = field(default_factory=list)
      created_at: str = ""      # ISO datetime
      updated_at: str = ""

      def to_dict(self) -> dict: ...
      @classmethod
      def from_dict(cls, d: dict) -> "KnowledgeCard": ...
      def validate(self) -> list[str]: ...
  ```

  创建 `eidos/eidos/schema/fact.py`:

  ```python
  """Fact — 事实断言，OntoDerive 推理的基础单位。"""
  @dataclass
  class Fact:
      id: str
      subject: str
      predicate: str
      object: str
      confidence: float = 1.0
      source_card_id: str = ""
      derived_from: str = ""
      # 同上的 to_dict, from_dict, validate
  ```

  创建 `eidos/eidos/schema/ontology_node.py`:

  ```python
  """OntologyNode — 本体概念定义。"""
  @dataclass
  class OntologyNode:
      id: str
      name: str
      node_type: str  # "concept" | "relation" | "attribute"
      parent: str = ""
      properties: dict = field(default_factory=dict)
      aliases: list[str] = field(default_factory=list)
      description: str = ""
      # 同上的 to_dict, from_dict, validate
  ```

  创建 `eidos/eidos/schema/registry.py`:

  ```python
  """Schema 注册中心 — 管理所有已知 Schema。"""
  _registry: dict = {}

  def register(schema_type: str, cls: type) -> None: ...
  def get(schema_type: str) -> type: ...
  def list_types() -> list[str]: ...
  def validate(data: dict, schema_type: str) -> list[str]: ...
  ```

  每个 dataclass 必须有 `validate()` 返回错误列表，空列表=校验通过。

  **Must NOT do**:
  - 不要引入任何外部包
  - 不要做复杂的 Schema 解析引擎
  - validate() 只做结构校验，不做语义校验

  **Parallelization**: Wave 1, 依赖 1.1
  **Recommended Agent Profile**: quick

  **QA Scenarios**:
  ```bash
  cd /Users/xiamingxing/Workspace/eidos
  .venv/bin/python3 -c "
  from eidos.schema.knowledge_card import KnowledgeCard
  c = KnowledgeCard(id='test1', title='测试', content='hello', source='/tmp', source_type='ingested', schema_type='KnowledgeCard')
  errs = c.validate()
  print(f'valid: {len(errs) == 0}, errors: {errs}')
  "
  # 验证 to_dict/from_dict 往返
  .venv/bin/python3 -c "
  from eidos.schema.fact import Fact
  f = Fact(id='f1', subject='A', predicate='is_a', object='B', confidence=0.95)
  d = f.to_dict()
  f2 = Fact.from_dict(d)
  assert f2.subject == 'A'
  assert f2.confidence == 0.95
  print('roundtrip OK')
  "
  ```

- [x] 1.3 实现 validator + CLI

  **What to do**:
  创建 `eidos/eidos/validator.py`:
  ```python
  """通用校验器 — 校验任意 dict 是否符合指定 Schema。"""
  def validate_object(obj: dict, schema_type: str) -> list[str]: ...
  def validate_card(card_dict: dict) -> list[str]: ...
  def validate_fact(fact_dict: dict) -> list[str]: ...
  def validate_node(node_dict: dict) -> list[str]: ...
  ```

  创建 `eidos/eidos/cli.py`:
  ```python
  """CLI: eidos list — 列出所有 Schema; eidos validate <file> — 校验文件"""
  import sys, json, argparse
  def build_parser(): ...
  def main():
      parser = build_parser()
      args = parser.parse_args()
      if args.command == "list": ...
      elif args.command == "validate": ...
  if __name__ == "__main__": main()
  ```

  **commands**:
  - `eidos list` — 列出所有注册 Schema
  - `eidos validate <file>` — 校验一个 JSON 文件是否符合 Schema
  - `eidos validate <file> --type KnowledgeCard` — 指定类型

  写 `tests/test_validator.py`:
  - test_valid_card_passes
  - test_invalid_card_missing_fields
  - test_valid_fact_passes
  - test_roundtrip_preserves_data

  **Parallelization**: Wave 1, 依赖 1.2
  **Recommended Agent Profile**: quick

  **QA Scenarios**:
  ```bash
  cd /Users/xiamingxing/Workspace/eidos
  # CLI list
  .venv/bin/python3 -m eidos.cli list
  # CLI validate
  echo '{"id":"t","title":"t","content":"c","source":"s","source_type":"i","schema_type":"KnowledgeCard"}' > /tmp/test_card.json
  .venv/bin/python3 -m eidos.cli validate /tmp/test_card.json
  rm /tmp/test_card.json
  # pytest
  .venv/bin/python3 -m pytest tests/ -x -q
  ```

- [x] 1.4 KOS 加 ingest 命令

  **What to do**:
  在 `/Users/xiamingxing/Workspace/kos/` 中：
  1. 读 `kos-cli.py` 了解子命令注册方式
  2. 在 CLI 子命令列表中加入 `ingest`:
     ```
     kos ingest <path>
     kos ingest <path> --watch         (选做)
     kos ingest ~/knowledge/ingested/  (目标)
     ```
  3. `ingest` 子命令的逻辑:
     - 递归扫描 `<path>` 下所有 `.md`, `.json`, `.txt` 文件
     - 文件分类: `.json` → 尝试匹配 Eidos Schema; `.md` → KnowledgeCard; 其他 → RawDocument
     - 调用 KOS 已有索引函数入库
     - 打印统计: "Found X files, indexed Y, skipped Z"
  4. 依赖: `pip install eidos` 或把 `eidos/` 加到 `sys.path`
  5. 把 `sys.path.insert(0, '/Users/xiamingxing/Workspace/eidos')` 加到入口

  **注意**: `ingest` 命令调用 `eidos.validator.validate()` 来校验每条记录。

  **Parallelization**: Wave 2, 依赖 1.3
  **Recommended Agent Profile**: deep

  **QA Scenarios**:
  ```bash
  # 创建测试目录
  mkdir /tmp/test_ingest
  echo "# Hello\nTest content" > /tmp/test_ingest/test.md
  echo '{"id":"t","title":"t","content":"c","source":"s","source_type":"i","schema_type":"KnowledgeCard"}' > /tmp/test_ingest/test.json
  
  # 运行 ingest
  KOS_HOME=/tmp/kos_test_home cd /Users/xiamingxing/Workspace/kos && .venv/bin/python3 kos-cli.py ingest /tmp/test_ingest
  
  # 验证索引结果
  KOS_HOME=/tmp/kos_test_home .venv/bin/python3 kos-cli.py search "test"
  
  rm -rf /tmp/test_ingest /tmp/kos_test_home
  ```

- [x] 1.5 KOS 产出走 Eidos 校验

  **What to do**:
  - 在 `kos-mcp-server.py` 的 `compile_paradigm` / `search` 等工具中，返回前调用 `eidos.validator.validate_card()`
  - 如果校验失败，记录 warning 但不阻断（不能因为 Schema 版本不一致就让服务挂掉）
  - 在 KOS 配置 `config.py` 中加 `EIDOS_ENABLED = True/False` 开关

  **Parallelization**: Wave 2, 依赖 1.3
  **Recommended Agent Profile**: deep

  **QA Scenarios**:
  ```bash
  # 启动 MCP 服务器并测试 search 返回是否带 Schema 标记
  KOS_HOME=/tmp/kos_test KOS_EIDOS_ENABLED=1 .venv/bin/python3 kos-mcp-server.py &
  # 通过 MCP stdio 发送 search 请求
  # 验证 response 中有 schema_type 字段
  kill %1 2>/dev/null
  ```

- [x] 1.6 批量索引

  **What to do**:
  ```bash
  # P0: 知识核心
  kos ingest ~/knowledge/ingested/
  
  # P1: KOS 设计文档
  kos ingest ~/Documents/KOS-*.md
  
  # P2: Obsidian 知识库
  kos ingest ~/ObsidianDocument/
  
  # P3: 公文
  kos ingest ~/Documents/公文/
  ```

  每次执行后记录: 文件数 / 索引数 / 失败数 / 耗时

  **在 1.4 和 1.5 完成后执行**
  **Recommended Agent Profile**: quick (batch script)

  **QA Scenarios**:
  ```bash
  # 验证搜索可以找到 ingested 内容
  kos search "知识" | head -10
  kos search "KOS" | head -10
  kos search "架构" | head -10
  ```

- [x] 1.7 验证索引质量

  **What to do**:
  - 随机抽查 50 条已索引记录，检查 Schema 字段完整性
  - 运行 5 个不同类型的搜索 query，验证结果相关度
  - 输出验证报告到 `.omo/evidence/eidos-ingest-validation.md`

  **Recommended Agent Profile**: deep

  **QA Scenarios**:
  ```bash
  # 统计索引的 schema_type 分布
  kos stats --by-schema-type
  
  # 搜索测试
  kos search "神经网络" --limit 5
  kos search "知识图谱" --limit 5
  kos search "研究" --limit 5
  kos search "python" --limit 5
  kos search "architecture" --limit 5
  ```

---

## Success Criteria

- [x] `eidos list` 显示 3 个注册 Schema
- [x] `eidos validate card.json` 校验通过/失败正确
- [x] `kos ingest ~/knowledge/ingested/` 完成索引 (46,075 files)
- [x] `kos search "知识"` 返回 ingested 内容
- [x] KOS 返回结果带 `schema_type` 字段
- [x] 所有 tests 通过 (23 passed)
