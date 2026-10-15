import importlib.util
import hashlib
import json
import subprocess

import pytest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


@pytest.fixture(autouse=True)
def _no_implicit_state_profile(monkeypatch):
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)


def _module():
    spec = importlib.util.spec_from_file_location("panorama_task_projection_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_collect_tasks_reads_canonical_per_file_queue(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path / "runtime")
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    _write(tmp_path / "code/.omo/tasks/active/active-task.yaml", "id: TASK-A\ntitle: Active\nstatus: pending\npriority: P0\nowner: agent\n")
    _write(tmp_path / "code/.omo/tasks/planned/planned-task.yaml", "id: TASK-B\ntitle: Planned\nstatus: candidate\npriority: P1\nowner: human\n")
    _write(tmp_path / "code/.omo/tasks/blocked/blocked-task.yaml", "id: TASK-C\ntitle: Blocked\nstatus: blocked\npriority: P1\nowner: human\n")
    _write(tmp_path / "code/.omo/tasks/done/done-task.yaml", "id: TASK-D\ntitle: Done\nstatus: done\n")
    _write(tmp_path / "code/.omo/tasks/planned/duplicate-task.yaml", "id: TASK-A\ntitle: Duplicate\nstatus: candidate\n")

    report = module.collect_tasks()

    assert report["source"] == ".omo/tasks/{active,planned,blocked,done}/*.yaml"
    assert report["total"] == 5
    assert report["open_count"] == 4
    assert report["by_bucket"] == {"active": 1, "planned": 2, "blocked": 1, "done": 1}
    assert report["duplicates"] == [{"id": "TASK-A", "buckets": ["active", "planned"]}]
    assert report["open_recent"][0]["id"] == "TASK-A"
    assert report["open_recent"][0]["bucket"] == "active"
    assert {task["id"] for task in report["open_recent"]} == {"TASK-A", "TASK-B", "TASK-C"}


def test_collect_service_lifecycle_separates_service_registry(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path / "runtime")
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    registry = tmp_path / "code/.omo/state/task-registry.yaml"
    _write(registry, "tasks:\n  daemon-a:\n    system: compute\n    carrier: launchd\n    lifecycle: active\n    purpose: daemon\n  daemon-b:\n    system: compute\n    carrier: cron\n    lifecycle: proposed\n    purpose: pending\n")

    report = module.collect_service_lifecycle()

    assert report["source"] == ".omo/state/task-registry.yaml"
    assert report["total"] == 2
    assert report["by_lifecycle"] == {"active": 1, "proposed": 1}
    assert {row["id"] for row in report["recent"]} == {"daemon-a", "daemon-b"}


def test_task_projection_does_not_read_stale_runtime_root(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path / "runtime")
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    _write(tmp_path / "runtime/.omo/tasks/planned/stale.yaml", "id: STALE\ntitle: Must not read\n")
    _write(tmp_path / "code/.omo/tasks/active/fresh.yaml", "id: FRESH\ntitle: Must read\nstatus: pending\n")

    report = module.collect_tasks()

    assert report["total"] == 1
    assert report["open_recent"][0]["id"] == "FRESH"


def test_explicit_task_profile_is_resolved_at_call_time(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    monkeypatch.setattr(module, "ROOT", tmp_path / "output")
    _write(tmp_path / "code/.omo/tasks/done/old.yaml", "id: CODE-ONLY\nstatus: done\n")
    _write(tmp_path / "state/.omo/tasks/done/new.yaml", "id: NATIVE\nstatus: done\ngoal_id: OBJ-VALUE\nowner: agent\ncompleted_at: 2026-10-14T08:53:18Z\n")
    assert module.collect_tasks()["recent_done"][0]["id"] == "CODE-ONLY"
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path / "state"))
    report = module.collect_tasks()
    assert report["total"] == 1
    assert report["source_root"] == str(tmp_path / "state")
    assert report["source_kind"] == "declared_state_root"
    task = report["recent_done"][0]
    assert task["id"] == "NATIVE"
    assert task["goal_id"] == "OBJ-VALUE"
    assert task["owner"] == "agent"
    assert task["completed_at"] == "2026-10-14 08:53:18+00:00"
    assert task["task_ref"] == str(tmp_path / "state/.omo/tasks/done/new.yaml")


def test_recent_done_orders_by_completion_not_filename(tmp_path, monkeypatch):
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path)
    for index in range(12):
        _write(tmp_path / f".omo/tasks/done/{11-index:02}.yaml",
               f"id: DONE-{index:02}\nstatus: done\ncompleted_at: '2026-10-14T{index:02}:00:00Z'\n")
    _write(tmp_path / ".omo/tasks/active/new.yaml", "id: STILL-OPEN\nstatus: pending\nupdated_at: '2026-10-15T00:00:00Z'\n")
    report = module.collect_tasks()
    assert [task["id"] for task in report["recent_done"]] == [f"DONE-{index:02}" for index in range(11, 3, -1)]
    assert report["open_recent"][0]["id"] == "STILL-OPEN"


def test_three_linked_markdown_deliverables_have_exact_text_and_hash(tmp_path, monkeypatch):
    import yaml
    module = _module()
    root = tmp_path / "artifacts"
    monkeypatch.setattr(module, "task_artifact_root", lambda: root)
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    paths = []
    for name, text in [("周报.md", "# 周报\n实际进展"), ("证据.md", "来源与缺口"), ("变更.md", "<script>window.bad=true</script>")]:
        path = root / name
        _write(path, text)
        paths.append(str(path))
    _write(root / "receipt.json", '{"private":"not a preview"}')
    _write(root / "ignored.md", "fourth file")
    _write(tmp_path / "code/.omo/tasks/done/weekly.yaml", yaml.safe_dump({
        "id": "WEEKLY", "status": "done", "goal_id": "OBJ-VALUE",
        "evidence_paths": [str(root / "receipt.json"), *paths, str(root / "ignored.md")],
    }, allow_unicode=True))
    report = module.collect_tasks()
    artifacts = report["recent_done"][0]["artifacts"]
    assert len(artifacts) == 3
    for artifact, path in zip(artifacts, paths):
        body = Path(path).read_bytes()
        assert artifact["status"] == "ready"
        assert artifact["preview"] == body.decode()
        assert artifact["sha256"] == hashlib.sha256(body).hexdigest()
        assert artifact["bytes"] == len(body)
        assert artifact["truncated"] is False
    assert "not a preview" not in json.dumps(report)
    assert "artifacts" not in report["recent"][0]
    assert "_evidence_paths" not in json.dumps(report)


@pytest.mark.parametrize("kind", ["outside", "traversal", "file_symlink", "ancestor_symlink", "root_symlink", "hardlink", "fifo"])
def test_artifact_preview_rejects_escaping_or_nonregular_files(tmp_path, monkeypatch, kind):
    import os
    module = _module()
    root = tmp_path / "artifacts"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("PRIVATE MUST NOT READ")
    monkeypatch.setattr(module, "task_artifact_root", lambda: root)
    target = root / "file.md"
    if kind == "outside":
        target = outside
    elif kind == "traversal":
        target = root / ".." / "outside.md"
    elif kind == "file_symlink":
        target.symlink_to(outside)
    elif kind == "ancestor_symlink":
        (root / "alias").symlink_to(tmp_path, target_is_directory=True)
        target = root / "alias/outside.md"
    elif kind == "root_symlink":
        root.rmdir()
        root.symlink_to(tmp_path, target_is_directory=True)
        target = root / "outside.md"
    elif kind == "hardlink":
        os.link(outside, target)
    else:
        os.mkfifo(target)
    result = module._task_artifact_preview(str(target), module.TASK_PREVIEW_TOTAL_BYTES)
    assert result["status"] in {"outside_allowed_root", "symlink_or_invalid"}
    assert "preview" not in result
    assert "PRIVATE" not in json.dumps(result)


def test_artifact_preview_limits_and_missing_permission_are_explicit(tmp_path, monkeypatch):
    module = _module()
    root = tmp_path / "artifacts"
    monkeypatch.setattr(module, "task_artifact_root", lambda: root)
    _write(root / "large.md", "x" * (module.TASK_PREVIEW_FILE_BYTES + 1))
    _write(root / "small.md", "1234")
    assert module._task_artifact_preview(str(root / "large.md"), 1000000)["status"] == "too_large"
    assert module._task_artifact_preview(str(root / "small.md"), 3)["status"] == "budget_exceeded"
    assert module._task_artifact_preview(str(root / "missing.md"), 100)["status"] == "missing"
    (root / "bad.md").write_bytes(b"\xff")
    assert module._task_artifact_preview(str(root / "bad.md"), 100)["status"] == "invalid_utf8"
    real_open = module.os.open
    def deny(path, *args, **kwargs):
        if path == "small.md":
            raise PermissionError("denied")
        return real_open(path, *args, **kwargs)
    monkeypatch.setattr(module.os, "open", deny)
    result = module._task_artifact_preview(str(root / "small.md"), 100)
    assert result["status"] == "permission_denied"
    assert "preview" not in result


def test_total_preview_budget_is_shared_across_recent_done_tasks(tmp_path, monkeypatch):
    import yaml
    module = _module()
    root = tmp_path / "artifacts"
    monkeypatch.setattr(module, "task_artifact_root", lambda: root)
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path / "code")
    for index in range(3):
        path = root / f"{index}.md"
        _write(path, "x" * (32 * 1024))
        _write(tmp_path / f"code/.omo/tasks/done/{index}.yaml", yaml.safe_dump({
            "id": f"DONE-{index}", "status": "done", "evidence_paths": [str(path)]}))
    artifacts = [a for t in module.collect_tasks()["recent_done"] for a in t["artifacts"]]
    assert [a["status"] for a in artifacts] == ["ready", "ready", "budget_exceeded"]
    assert sum(a.get("bytes", 0) for a in artifacts if a["status"] == "ready") == module.TASK_PREVIEW_TOTAL_BYTES


def test_task_goal_association_exposes_only_declared_ids(tmp_path, monkeypatch):
    import yaml
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path)
    ids = {"vision_id": "VISION-2029", "objective_id": "OBJ-VALUE",
           "campaign_id": "CMP-Y1-VALUE-PROOF", "key_result_id": "KR-VALUE-WEEKLY-ADOPTION"}
    _write(tmp_path / ".omo/tasks/done/weekly.yaml", yaml.safe_dump({
        "id": "WEEKLY", "status": "done", "goal_id": "OBJ-VALUE",
        "metadata": {**ids, "principal_feedback": "PRIVATE-FEEDBACK",
                     "secret": "PRIVATE-KEY", "kr_attainment_claimed": True,
                     "bet_binding_registered": True},
    }))
    task = module.collect_tasks()["recent_done"][0]
    association = task["goal_association"]
    assert association["state"] == "declared"
    assert association["ids"] == ids
    assert association["kind"] == "task_record_association"
    assert association["binding_status"] == "unverified"
    assert association["effect_status"] == "unproven"
    assert association["issues"] == []
    assert "PRIVATE-" not in json.dumps(task)
    assert "kr_attainment_claimed" not in json.dumps(task)
    assert "bet_binding_registered" not in json.dumps(task)


@pytest.mark.parametrize("metadata,goal_id,issue", [
    (None, "OBJ-VALUE", "vision_id:missing"),
    ([], "OBJ-VALUE", "metadata:invalid"),
    ({}, "OBJ-VALUE", "vision_id:missing"),
    ({"vision_id": True}, "OBJ-VALUE", "vision_id:invalid"),
    ({"vision_id": "V" * 121}, "OBJ-VALUE", "vision_id:invalid"),
    ({"vision_id": "<img src=x onerror=alert(1)>"}, "OBJ-VALUE", "vision_id:invalid"),
    ({"objective_id": "OBJ-OTHER"}, "OBJ-VALUE", "objective_id:conflict"),
    ({"objective_id": "OBJ-VALUE"}, ["OBJ-VALUE"], "goal_id:invalid"),
])
def test_task_goal_association_missing_malformed_or_conflicting_is_unknown(
        tmp_path, monkeypatch, metadata, goal_id, issue):
    import yaml
    module = _module()
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path)
    _write(tmp_path / ".omo/tasks/done/weekly.yaml", yaml.safe_dump({
        "id": "LEGACY", "status": "done", "goal_id": goal_id, "metadata": metadata,
    }))
    task = module.collect_tasks()["recent_done"][0]
    association = task["goal_association"]
    assert association["state"] == "unknown"
    assert issue in association["issues"]
    assert association["binding_status"] == "unverified"
    assert association["effect_status"] == "unproven"
    if not isinstance(goal_id, str):
        assert task["goal_id"] == ""
    assert task["artifacts"] == []


@pytest.mark.parametrize("state", ["declared", "unknown"])
def test_task_goal_ui_uses_safe_text_and_does_not_claim_effect(state):
    module = _module()
    malicious = "<img src=x onerror=alert(1)>"
    task = {"id": "WEEKLY", "status": "done", "goal_id": "OBJ-VALUE",
            "goal_association": {"state": state, "ids": {
                "vision_id": malicious, "objective_id": "OBJ-VALUE",
                "campaign_id": "CMP-DECLARED", "key_result_id": "KR-DECLARED"},
                "binding_status": "unverified", "effect_status": "unproven"},
            "artifacts": [{"path": "周报.md", "status": "ready", "preview": "# 原成品",
                           "sha256": "abc", "bytes": 14}]}
    script = r"""
const nodes=[];
function make(tag){
  const node={tag,children:[],style:{},textContent:'',
    appendChild(child){this.children.push(child);return child;}};
  Object.defineProperty(node,'innerHTML',{set(){throw Error('unsafe HTML rendering');}});
  nodes.push(node);return node;
}
const host=make('section');
const document={getElementById(id){return id==='next'?host:null;},
  querySelector(){return null;},createElement:make};
const D={tasks:{recent_done:[TASK]}};
UI
process.stdout.write(JSON.stringify(nodes.map(node=>({tag:node.tag,text:node.textContent}))));
""".replace("TASK", json.dumps(task, ensure_ascii=False)).replace("UI", module.NATIVE_TASK_UI)
    result = subprocess.run(["node", "-e", script], text=True, capture_output=True, check=True)
    nodes = json.loads(result.stdout)
    text = "\\n".join(node["text"] for node in nodes)
    assert "任务关联目标" in text and "阶段目标" in text and "成果证据" in text
    assert "任务完成不代表目标效果已证明" in text
    assert "不是 BET 正式组合绑定" in text
    assert malicious in text
    assert not any(node["tag"] in {"img", "script"} for node in nodes)
    assert any(node["tag"] == "pre" and node["text"] == "# 原成品" for node in nodes)
    assert ("关联未知" in text) == (state == "unknown")


def test_production_priority_template_gets_safe_native_task_ui():
    from html.parser import HTMLParser
    module = _module()
    malicious = "__DATA__ __SNAPSHOT_JSON__ </script><script>window.injected=true</script><img src=x onerror=alert(1)>"
    payload = {"tasks": {"recent_done": [{"id": "WEEKLY", "title": malicious, "artifacts": [{"preview": malicious}]}]}}
    template = '<html><body><section id="next"></section><script id="snapshot" type="application/json">__SNAPSHOT_JSON__</script><script>const D=JSON.parse(document.getElementById("snapshot").textContent);</script></body></html>'
    page = module.render_projection_page(template, payload)
    class Scripts(HTMLParser):
        def __init__(self):
            super().__init__(); self.scripts = []; self.current = None; self.images = 0
        def handle_starttag(self, tag, attrs):
            if tag == "script":
                self.current = []; self.scripts.append(self.current)
            if tag == "img": self.images += 1
        def handle_endtag(self, tag):
            if tag == "script": self.current = None
        def handle_data(self, data):
            if self.current is not None: self.current.append(data)
    parsed = Scripts(); parsed.feed(page)
    assert len(parsed.scripts) == 3
    assert parsed.images == 0
    assert json.loads("".join(parsed.scripts[0])) == payload
    assert "native-completed-tasks" in "".join(parsed.scripts[2])
    assert "textContent" in module.NATIVE_TASK_UI
    assert "innerHTML" not in module.NATIVE_TASK_UI
    subprocess.run(["node", "--check"], input=module.NATIVE_TASK_UI, text=True, check=True, capture_output=True)
