# 卫健委 Facts Runtime Owner 迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将卫健委 facts 的执行逻辑从 Documents 域移到 Workspace Runtime，同时保留日常审计的只读边界和显式人工维护能力。

**Architecture:** Runtime 新增一个 YAML facts 审计模块，并把它注册为 `runtime documents run documents-weijian-facts-audit`；该 job 只读 Documents，并把回执写入 Runtime state。原先会写 Documents 的三份小型维护脚本迁入 Runtime 的 `scripts/weijian_facts/`，均要求显式指定域根；它们不注册为 job 或 schedule。Documents 仅保留 facts 数据、生成视图与使用说明，控制器不再从 Documents `_runtime` 自动拉起 Dashboard 生成器。

**Tech Stack:** Python 3.13、PyYAML、pytest、Runtime Documents Plane、macOS sandbox-exec。

## Global Constraints

- 日常 owner job 只能读取 Documents，不能写 Documents。
- 写 content 的维护脚本必须显式传入 `--root`，且不注册 schedule。
- 域路径必须以相对 `DOCUMENTS_CONTENT_ROOT` 的形式声明；拒绝绝对路径和 `..`。
- 迁移不修改 facts YAML、facts.md 或 Dashboard 的内容数据，只移动执行实现与入口引用。
- 保留 Documents 中的历史巡检记录；只改活跃入口、说明和四个脚本本体。
- 所有新行为先用 pytest 观察 RED，再写最小实现。

---

### Task 1: 只读 facts 审计与 Runtime job

**Files:**
- Create: `projects/runtime/src/runtime/documents_plane/facts.py`
- Modify: `projects/runtime/src/runtime/documents_plane/cli.py`
- Create: `projects/runtime/tests/test_documents_plane_facts.py`
- Modify: `projects/runtime/tests/test_documents_plane_jobs.py`

**Interfaces:**
- Produces: `audit_facts(domain_root: Path) -> FactAudit`，结果包含 `status`、`facts_total`、`by_type`、`errors`、`warnings`。
- Produces: `main(argv: Sequence[str] | None = None) -> int`，供 Runtime sandbox 的 `python -m runtime.documents_plane.facts` 调用。
- Consumes: `DOCUMENTS_CONTENT_ROOT` 和 `--domain-relative @工作文档/卫健委`；不接受 Documents 根外路径。
- Produces: 默认 job `documents-weijian-facts-audit`，owner 为 `runtime-facts`、reads 仅为卫健委域、writes 为空、schedule 为 `manual`。

- [x] **Step 1: 写出域 YAML 成功审计的失败测试**

```python
def test_audit_facts_counts_valid_yaml_without_writing_domain(tmp_path: Path):
    domain = make_domain(tmp_path, facts=[valid_fact("fact-20260813-001")])
    result = audit_facts(domain)
    assert result.status == "ok"
    assert result.facts_total == 1
    assert result.by_type == {"info": 1}
    assert not result.errors
```

- [x] **Step 2: 运行该测试确认 RED**

Run: `uv run pytest tests/test_documents_plane_facts.py::test_audit_facts_counts_valid_yaml_without_writing_domain -q`

Expected: FAIL，因为 `runtime.documents_plane.facts` 尚不存在。

- [x] **Step 3: 实现最小只读审计**

```python
@dataclass(frozen=True)
class FactAudit:
    status: str
    facts_total: int
    by_type: dict[str, int]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

def audit_facts(domain_root: Path) -> FactAudit:
    # 只读取 _entities/facts/[0-9][0-9]-*.yaml 和 _index.yaml；
    # 验证 fid、type、trust、importance、statement、summary、日期、重复 fid 与 index 计数。
    ...
```

- [x] **Step 4: 运行 facts 测试确认 GREEN**

Run: `uv run pytest tests/test_documents_plane_facts.py -q`

Expected: PASS；无测试创建或修改 domain 文件。

- [x] **Step 5: 写出 Runtime 注册与 sandbox 调用的失败测试**

```python
def test_default_registry_registers_read_only_weijian_facts_job(tmp_path: Path):
    registry = _default_registry({"DOCUMENTS_CONTENT_ROOT": str(tmp_path)})
    spec, command = registry.resolve("documents-weijian-facts-audit")
    assert spec.reads == ("@工作文档/卫健委",)
    assert spec.writes == ()
    assert spec.schedule == "manual"
    assert command[-2:] == ("--domain-relative", "@工作文档/卫健委")
```

- [x] **Step 6: 运行注册测试确认 RED，再接入 CLI**

Run: `uv run pytest tests/test_documents_plane_jobs.py -k weijian_facts -q`

Expected: FAIL，因为 job 尚未注册。

实现以 `sys.executable -m runtime.documents_plane.facts audit` 作为 owner command，并把相对域路径传入；不增加任何 write declaration。

- [x] **Step 7: 运行受影响测试并提交 Runtime 审计层**

Run: `uv run pytest tests/test_documents_plane_facts.py tests/test_documents_plane_jobs.py -q`

Expected: PASS。

Commit: `feat(runtime): add read-only weijian facts audit`

### Task 2: 迁入手工 facts 维护脚本

**Files:**
- Create: `projects/runtime/scripts/weijian_facts/gen-facts-view.py`
- Create: `projects/runtime/scripts/weijian_facts/migrate-facts-yaml.py`
- Create: `projects/runtime/scripts/weijian_facts/gen-dashboard.py`
- Create: `projects/runtime/tests/test_weijian_facts_scripts.py`

**Interfaces:**
- Produces: 三份 Runtime-owned maintenance scripts；每份通过 `--root <卫健委域根>` 定位 Documents 内容，不读取脚本自身所在路径作为域根。
- Produces: `gen-dashboard.py [--root PATH] [--out PATH]`；不由 `controller.py` 自动调用。
- Consumes: facts YAML、已有 Documents 内容；不进入 `_default_registry`，不接受 schedule。

- [x] **Step 1: 写出 portable-root 的失败测试**

```python
def test_facts_view_script_uses_explicit_root(tmp_path: Path) -> None:
    result = run_script("gen-facts-view.py", "--root", str(make_domain(tmp_path)))
    assert result.returncode == 0
    assert (domain / "_entities" / "facts.md").exists()
```

- [x] **Step 2: 运行测试确认 RED**

Run: `uv run pytest tests/test_weijian_facts_scripts.py -k explicit_root -q`

Expected: FAIL，因为 Runtime 还没有 maintenance script。

- [x] **Step 3: 复制并最小参数化三份原有脚本**

将 `gen-facts-view.py`、`migrate-facts-yaml.py` 与 `gen-dashboard.py` 迁到 `projects/runtime/scripts/weijian_facts/`。保留现有生成逻辑，新增 `--root`，不注册 cron 或 Runtime job。Dashboard 的 `get_controller()` 只消费已给出的控制器输出或退化为未知状态，绝不从脚本中执行 Documents `controller.py`。

- [x] **Step 4: 运行 portable-root 回归并提交**

Run: `uv run pytest tests/test_weijian_facts_scripts.py -q`

Expected: PASS。

Commit: `feat(runtime): move weijian facts maintenance scripts`

### Task 3: Documents 域切换到 Workspace 实现

**Files:**
- Delete: `/Users/xiamingxing/Documents/@工作文档/卫健委/_runtime/check-facts.py`
- Delete: `/Users/xiamingxing/Documents/@工作文档/卫健委/_runtime/gen-facts-view.py`
- Delete: `/Users/xiamingxing/Documents/@工作文档/卫健委/_runtime/migrate-facts-yaml.py`
- Delete: `/Users/xiamingxing/Documents/@工作文档/卫健委/_runtime/gen-dashboard.py`
- Modify: `/Users/xiamingxing/Documents/@工作文档/卫健委/_control/controller.py`
- Modify: `/Users/xiamingxing/Documents/@工作文档/卫健委/_control/control-rules.md`
- Modify: `/Users/xiamingxing/Documents/@工作文档/卫健委/_entities/facts/README.md`
- Modify: `/Users/xiamingxing/Documents/@工作文档/卫健委/_entities/facts.md`
- Modify: `/Users/xiamingxing/Documents/@工作文档/卫健委/_entities/facts/*.yaml`

**Interfaces:**
- Documents 只记录 Workspace command：日常 `runtime documents run documents-weijian-facts-audit --json`，人工维护 `python projects/runtime/scripts/weijian_facts/<script>.py --root <卫健委域根>`。
- `controller.py` 不再寻找或运行 Documents `_runtime/gen-dashboard.py`。
- 新 facts YAML 注释指向 Runtime maintenance script，而不是 Documents `_runtime`。

- [ ] **Step 1: 在 Workspace replacement 已存在后，写出无 Documents 脚本的失败检查**

```python
assert not (domain / "_runtime" / "check-facts.py").exists()
assert "_runtime/gen-dashboard.py" not in active_controller_source
```

- [ ] **Step 2: 执行检查确认 RED**

Run: `test ! -e "_runtime/check-facts.py"`

Expected: FAIL，证明旧执行层仍在 Documents。

- [ ] **Step 3: 删除四个 Documents 脚本并更新活跃入口/说明**

仅替换活跃文档中的执行路径，保留 `_runtime/巡检报告`、`_storage` 中的历史记录。控制器删除自动启动 Dashboard 的块，不删除其余现有控制逻辑。

- [ ] **Step 4: 用 Runtime CLI 对真实卫健委域做只读验证**

Run: `DOCUMENTS_CONTENT_ROOT="/Users/xiamingxing/Documents" runtime documents run documents-weijian-facts-audit --json`

Expected: `exit_code: 0`，并且 Documents git diff 只包含本任务列出的删除/路径替换，不含由审计引起的写入。

- [ ] **Step 5: 精确提交 Documents 改动**

只提交上述 eight scopes；保留并行 facts 内容编辑及无关 staged 文件。

Commit: `refactor(weijian): move facts execution out of Documents`

### Task 4: Workspace 集成、评审与合并

**Files:**
- Modify: `projects/runtime` gitlink in Workspace root
- Modify: `docs/superpowers/plans/2026-08-13-weijian-facts-runtime-owner.md` (checkbox closeout only)

- [ ] **Step 1: 先跑 Runtime 定向与全量测试**

Run: `uv run pytest tests/test_documents_plane_facts.py tests/test_documents_plane_jobs.py tests/test_weijian_facts_scripts.py -q && uv run pytest tests/ -q`

Expected: PASS。

- [ ] **Step 2: 运行静态检查与真实 no-write smoke**

Run: `uv run ruff check src/runtime/documents_plane tests/test_documents_plane_*.py && uv run ruff format --check src/runtime/documents_plane tests/test_documents_plane_*.py`

Run: `DOCUMENTS_CONTENT_ROOT="/Users/xiamingxing/Documents" runtime documents run documents-weijian-facts-audit --json`

Expected: lint PASS；审计成功且 Documents worktree 未新增写入。

- [ ] **Step 3: 更新 Runtime gitlink、验证 workflow、提交 root**

Run: `uv run --with pyyaml python bin/agent-workflow.py verify 20260813T071346Z-project-code-change-ea4dace0 --from-diff --execute`

Expected: workflow verification PASS；然后提交 Runtime gitlink 和计划 closeout。

Commit: `chore(workspace): adopt runtime facts owner`

- [ ] **Step 4: 提交/合并前复核**

检查三份 diff、精确 commit 文件列表、Runtime 与 Documents 都无本任务外的 staged 文件；再通过既有 `gac-worktree.sh submit/merge` 发起并合并 PR。
