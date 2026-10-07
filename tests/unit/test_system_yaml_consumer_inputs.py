"""摘库后的**消费面接线**: 创建者必须在每个「按存在性判定」的读者之前跑过一遍。

契约: `docs/superpowers/specs/2026-10-07-system-yaml-materializer-untrack.md` §5 第 6 条
BET:  BET-Y2Q4-T10-235 (第二次交付)

为什么要单独一个文件: 第一次交付只做「摘库 + 创建者」, PR #4671 因此在五个面上变红 ——
`architecture-check` 的 core_documents.STATE.md 存在性断言、`doc-link-check` 的 16 处链接、
`current-state-coherence` 的输入、`ci-surfaces` 的 unregistered-check、`bin` 净增配额。
这些红没有一个是判定语义错了, 全部是**读者按存在性判定而创建者没接线**。所以本文件钉的是
接线本身, 而不是任何检查器的结论: 削弱任一检查器 (跳过链接目标 / 去掉存在性断言) 即
circuit_breaker 命中。

判据形状对齐 AGENTS.md §7 四条纪律:
- **检测器自证**: 顺序判据吃合成违规 (缺创建者 / 创建者在读者之后), 否则「绿」可能只是装置没命中。
- **判据与被验对象不共享失效模式**: 消费者发现用 YAML 解析后的 step 内容子串, 不用
  `check-ci-surfaces.py` 的那条正则; ci-surfaces 一致性用登记表对照**全部** workflow 文件。
- **正向落点**: 创建者跑完后 coherence 交得出 system.yaml 输入, 不用「检出没报错」当验收。
- **零时钟依赖**: 不在 fixture 里写绝对时间戳。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

CREATOR = "bin/gac/materialize-system-state.py"
STATE_REL = ".omo/state/system.yaml"
WORKFLOWS_DIR = ".github/workflows"
CI_SURFACES_REL = ".omo/_truth/registry/ci-surfaces.yaml"
GOVERNANCE_CHECKS_REL = ".omo/_truth/registry/governance-checks.yaml"

#: workflow → 它里面必须排在创建者之后的读者 (gac-gate 的三个读者都嵌在 strict gate 里)。
CONSUMERS: dict[str, tuple[str, ...]] = {
    "gac-gate.yml": ("bin/gac/gac-local-gate.py",),
    "architecture-check.yml": ("bin/gac/architecture-check.py",),
    "state-goals-enforce.yml": ("bin/ssot/current-state-coherence.py",),
}


def _load(name: str, rel: str, root: Path):
    spec = importlib.util.spec_from_file_location(name, root / rel)
    assert spec and spec.loader, f"cannot load {root / rel}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def repo_root():
    return _load("consumer_repo_root", "bin/lib/repo_root.py", Path(__file__).resolve().parents[2])


@pytest.fixture(scope="module")
def root(repo_root):
    return repo_root.code_root()


def _run_steps(text: str) -> list[str]:
    """按 CI 真正执行的顺序返回每个 `run:` 步骤的内容 (折叠块已展开)。"""
    steps: list[str] = []
    document = list(yaml.safe_load_all(text))[-1]
    for job in (document.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            run = step.get("run")
            if isinstance(run, str):
                steps.append(run)
    return steps


def _position(steps: list[str], needle: str) -> tuple[int, int] | None:
    """(步骤号, 步骤内字符偏移) —— 同一步里 `A && B` 的顺序也是顺序。"""
    for index, step in enumerate(steps):
        offset = step.find(needle)
        if offset >= 0:
            return (index, offset)
    return None


def creator_order_violations(steps: list[str], consumers: tuple[str, ...]) -> list[str]:
    """核心判据: 创建者必须存在, 且严格先于每个消费者。返回违规描述 (空=合规)。

    吃的是**步骤列表**而不是文件, 所以合成违规样本可以走同一个函数 —— 判据与自检不分裂。
    """
    creator_at = _position(steps, CREATOR)
    violations: list[str] = []
    for consumer in consumers:
        consumer_at = _position(steps, consumer)
        if consumer_at is None:
            continue  # 该 workflow 里根本没这个读者 —— 不是接线问题, 由别的用例管
        if creator_at is None:
            violations.append(f"missing-creator: {consumer} 按存在性判定, 而流程里没有创建者")
        elif creator_at >= consumer_at:
            violations.append(
                f"creator-after-consumer: {consumer} 在 step {consumer_at[0]}:{consumer_at[1]}, 创建者在 {creator_at}"
            )
    return violations


# ── 接线顺序 + 检测器自证 ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("workflow", sorted(CONSUMERS))
def test_creator_runs_before_every_consumer(root, workflow):
    text = (root / WORKFLOWS_DIR / workflow).read_text(encoding="utf-8")
    assert creator_order_violations(_run_steps(text), CONSUMERS[workflow]) == []


def test_order_detector_is_not_a_no_op():
    """合成违规自证: 缺创建者、创建者在读者之后都必须被点名, 正确顺序必须放行。"""
    consumer = "bin/ssot/current-state-coherence.py"
    kinds = lambda steps: [v.split(":")[0] for v in creator_order_violations(steps, (consumer,))]

    assert kinds([f"python3 {consumer}"]) == ["missing-creator"]
    assert kinds([f"python3 {consumer}", f"python3 {CREATOR} --json"]) == ["creator-after-consumer"]
    assert kinds([f"python3 {CREATOR} --json", f"python3 {consumer}"]) == []
    # 同一步内的链式顺序也算顺序: 先创建者放行, 反序必须点名
    assert kinds([f"python3 {CREATOR} --json && python3 {consumer}"]) == []
    assert kinds([f"python3 {consumer} && python3 {CREATOR} --json"]) == ["creator-after-consumer"]
    # 读者不在该流程里时不硬造违规 (否则任何 workflow 都会红)
    assert kinds([f"python3 {CREATOR} --json"]) == []


# ── 摘库前提: 干净检出里这份生成态既不被跟踪也被忽略 ─────────────────────────────────


def test_state_yaml_is_untracked_and_ignored(root):
    """创建者的存在理由: 干净检出里没有这份文件。跟踪/忽略判据用 git 自己答, 不读工作树。"""
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", STATE_REL],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode != 0, f"{STATE_REL} 仍被跟踪 —— 摘库没生效, 创建者就是多余的"

    ignored = subprocess.run(
        ["git", "check-ignore", "-v", STATE_REL],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0, "摘库后未忽略 ⇒ CI 物化一次就会让 immutable postcondition 变脏"
    assert ".gitignore" in ignored.stdout


# ── 登记面: ci-surfaces 覆盖全部执行它的 workflow, 且两份注册表仍可解析 ───────────────


def _workflows_running(root: Path, needle: str) -> set[str]:
    """独立于 check-ci-surfaces 正则的发现口径: 解析后的 step 内容子串。"""
    found: set[str] = set()
    for wf in sorted((root / WORKFLOWS_DIR).glob("*.yml")):
        if any(needle in step for step in _run_steps(wf.read_text(encoding="utf-8"))):
            found.add(wf.name)
    return found


def test_creator_is_registered_for_every_workflow_that_runs_it(root):
    """CR-CI-SURFACE-SSOT: 执行而未登记 = error; 多处执行未声明 = overlap warning。"""
    executing = _workflows_running(root, CREATOR)
    assert executing, f"没有任何 workflow 执行 {CREATOR} —— 创建者未接线, 干净检出必红"

    registry = yaml.safe_load((root / CI_SURFACES_REL).read_text(encoding="utf-8"))
    surfaces = registry.get("surfaces") or []
    assert surfaces, f"{CI_SURFACES_REL} 解析出空 surfaces —— 读者会把整份登记当成不存在"
    entries = [s for s in surfaces if isinstance(s, dict) and s.get("tool") == CREATOR]
    assert len(entries) == 1, f"{CREATOR} 登记了 {len(entries)} 条, 应为 1 条"

    entry = entries[0]
    declared = {str(entry.get("workflow") or "")} | {str(w) for w in (entry.get("also_in") or [])}
    assert executing <= declared, f"执行面 {sorted(executing)} 未被登记覆盖: {sorted(executing - declared)}"
    assert entry.get("gate") is False, "创建者是前置供料步, 不是门禁"
    assert entry.get("status") == "active"


def test_creator_has_a_script_registry_entry(root):
    """净增一个 bin 脚本 ⇒ script-registry 的 missing 侧必须同步 (bin 摘库检查读不到它)。"""
    entries = list((root / "bin" / "_registry" / "scripts").rglob("*.yaml"))
    ids = set()
    for path in entries:
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            pytest.fail(f"{path} 解析失败 —— script-registry 会静默丢整条登记")
        if isinstance(document, dict) and document.get("id"):
            ids.add(str(document["id"]))
    assert CREATOR in ids, "创建者未登记在 bin/_registry/scripts/ ⇒ validate 报 Missing registrations"


@pytest.mark.parametrize("rel", [CI_SURFACES_REL, GOVERNANCE_CHECKS_REL])
def test_registry_yaml_parses(root, rel):
    """`check-ci-surfaces._load_yaml` 对解析失败**静默返回 {}** ⇒ 129 条 unregistered 假红。

    实测踩过: note 里一个 `: ` 就足以让整份登记消失, 而报错形状像「登记没做」。
    """
    text = (root / rel).read_text(encoding="utf-8")
    document = yaml.safe_load(text)  # 不吞异常: 这里要的就是它炸
    assert isinstance(document, dict) and document


# ── 正向落点: 创建者跑完后读者交得出输入 ────────────────────────────────────────────


def _fixture_tree(base: Path, checkout: Path) -> Path:
    """最小检出: goals 双文档 + 三个任务, write-owners 声明真实键集合。

    `checkout` 由调用方显式传入 (被检对象的根不得由 `__file__` 反推, AGENTS.md §7③)。
    """
    omo = base / ".omo"
    for sub, names in (
        ("active", ["a1", "a2"]),
        ("planned", ["p1"]),
        ("blocked", []),
        ("done", []),
    ):
        d = omo / "tasks" / sub
        d.mkdir(parents=True, exist_ok=True)
        for name in names:
            (d / f"{name}.yaml").write_text(f"id: {name}\ntitle: T {name}\n", encoding="utf-8")
    (omo / "goals").mkdir(parents=True, exist_ok=True)
    (omo / "goals" / "current.yaml").write_text(
        "---\ntype: ssot\n---\nphase: 41\ncurrent_wave: W7\nexecution_mode: rolling\ngoals: []\n",
        encoding="utf-8",
    )
    owners = omo / "_truth" / "registry" / "write-owners.yaml"
    owners.parent.mkdir(parents=True, exist_ok=True)
    real = yaml.safe_load(
        (checkout / ".omo/_truth/registry/write-owners.yaml").read_text(encoding="utf-8")
    )
    owners.write_text(
        yaml.dump(
            {"fields": {STATE_REL: {k: {"owner": "script:test"} for k in real["fields"][STATE_REL]}}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return base


def test_coherence_gets_its_input_only_after_the_creator_ran(root, tmp_path, monkeypatch):
    """同一棵合成树: 创建者之前 coherence 因缺输入 rc 2, 之后必须交得出 phase/wave。"""
    materializer = _load("consumer_materializer", CREATOR, root)
    coherence = _load("consumer_coherence", "bin/ssot/current-state-coherence.py", root)
    tree = _fixture_tree(tmp_path / "tree", root)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tree))

    before = coherence.main(["--root", str(tree)])
    assert before == 2, "合成树里这份生成态应当缺失 —— 否则这条用例压根没在测摘库后的形状"

    assert materializer.main(["--root", str(tree), "--json"]) == 0
    assert (tree / STATE_REL).is_file(), "正向落点断言: 创建者必须真的写出这份输入"

    # 实测读数: 缺失时 rc 2 + stderr 点名 system.yaml, 物化后 rc 0 + phase=41 wave=W7。
    # 断到 rc 0 而不是「不再 rc 2」—— 后者对 findings 类失败 (rc 1) 也放行。
    assert coherence.main(["--root", str(tree)]) == 0, "创建者跑完读者仍不认这份输入 ⇒ 落点与读点不是同一份"


def test_materialized_document_leaves_the_coherence_consumer_satisfied(root, tmp_path, monkeypatch):
    """创建者的产物要让读者**判定通过**, 不只是「文件在」。

    两个模块各自数一遍任务面 (materializer.task_counts vs coherence._task_counts), 所以
    「存储计数 == 同树读数」不是按构造绿; 声明面少一个键、或多一个键都会让 coherence 报 findings。
    """
    materializer = _load("consumer_materializer2", CREATOR, root)
    coherence = _load("consumer_coherence2", "bin/ssot/current-state-coherence.py", root)
    tree = _fixture_tree(tmp_path / "reachable", root)
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tree))
    assert materializer.main(["--root", str(tree), "--json"]) == 0

    doc = yaml.safe_load((tree / STATE_REL).read_text(encoding="utf-8"))
    declared = yaml.safe_load(
        (tree / ".omo/_truth/registry/write-owners.yaml").read_text(encoding="utf-8")
    )["fields"][STATE_REL]
    assert set(doc) == set(declared), "读者按声明面读, 少一个键是 ghost、多一个是 undeclared"

    counts = coherence._task_counts(tree / ".omo")
    assert counts["active"] == 2 and counts["planned"] == 1, "fixture 形状变了, 这条判据在测的空气"
    assert coherence._stored_count_mismatches(doc, counts) == []
    assert doc["current_phase"] == 41 and doc["current_wave"] == "W7"


def test_consumer_wiring_suite_is_named_by_ci(root):
    """点名判据: tests/unit/** 不在任何 CI 白名单里, 未点名即本文件只是本地证据。"""
    text = (root / ".github" / "workflows" / "governance-check.yml").read_text(encoding="utf-8")
    assert "tests/unit/test_system_yaml_consumer_inputs.py" in text, (
        "本文件的判据没接进 CI ⇒ 「CI 绿」不覆盖接线顺序"
    )
