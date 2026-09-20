#!/usr/bin/env python3
"""Unit tests for scene-card-autogen.py.

Tests slugify, infer_scene_class, infer_scene_type, scaffold_scene,
from_signal, yaml_dump, list_templates.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "ssot" / "scene-card-autogen.py"


def _load():
    spec = importlib.util.spec_from_file_location("scene_card_autogen", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["scene_card_autogen"] = m
    spec.loader.exec_module(m)
    return m


def test_slugify_basic():
    m = _load()
    assert m.slugify("Hello World") == "hello-world"
    assert m.slugify("foo bar  baz") == "foo-bar-baz"


def test_slugify_camelcase():
    m = _load()
    assert m.slugify("CamelCase") == "camel-case"
    assert m.slugify("XMLParser") == "xml-parser"


def test_slugify_dot_notation():
    m = _load()
    assert m.slugify("calendar.event.upcoming") == "calendar-event-upcoming"
    assert m.slugify("user.query.received") == "user-query-received"


def test_slugify_special_chars():
    m = _load()
    assert m.slugify("a:b/c") == "a-b-c"
    assert m.slugify("test_name") == "test-name"


def test_infer_scene_class():
    m = _load()
    assert m.infer_scene_class("work") == "business"
    assert m.infer_scene_class("health") == "business"
    assert m.infer_scene_class("governance") == "governance"
    assert m.infer_scene_class("unknown") == "infra"


def test_infer_scene_type_classify():
    m = _load()
    assert m.infer_scene_type("对邮件做分类") == "inbound"
    assert m.infer_scene_type("classify mail") == "inbound"


def test_infer_scene_type_produce():
    m = _load()
    assert m.infer_scene_type("生成报告") == "outbound"
    assert m.infer_scene_type("produce summary") == "outbound"


def test_infer_scene_type_cycle():
    m = _load()
    assert m.infer_scene_type("周期 cron 任务") == "cycle"
    assert m.infer_scene_type("schedule daily report") == "cycle"


def test_scaffold_scene_basic():
    m = _load()
    scene = m.scaffold_scene(
        scene_id="test-scene",
        domain="work",
        description="对邮件分类",
        consumer="alice",
        trigger="email.received",
    )
    assert scene["scene_id"] == "test-scene"
    assert scene["domain"] == "work"
    assert scene["scene_class"] == "business"
    assert scene["scene_type"] == "inbound"
    assert scene["lifecycle"] == "draft"
    assert scene["schema"] == "scene-card/v3"
    assert scene["version"] == "3.0.0"
    assert scene["consumer"] == "alice"
    assert scene["trigger"] == "email.received"
    assert scene["operator"] == "test-scene-dispatch"


def test_from_signal_with_filter():
    m = _load()
    scene = m.from_signal("calendar.event.upcoming:meeting")
    assert scene["scene_id"] == "calendar-event-upcoming-meeting"
    assert scene["domain"] == "work"
    assert "filter: meeting" in scene["description"]


def test_from_signal_no_filter():
    m = _load()
    scene = m.from_signal("user.query.received")
    assert scene["scene_id"] == "user-query-received"
    assert scene["domain"] == "work"


def test_yaml_dump_basic():
    m = _load()
    scene = m.scaffold_scene(
        scene_id="test-yaml",
        domain="work",
        description="test",
    )
    yaml_str = m.yaml_dump(scene)
    assert "scene-card/v3" in yaml_str
    assert "scene_id: test-yaml" in yaml_str
    assert "domain: work" in yaml_str


def test_yaml_dump_handles_chinese():
    m = _load()
    scene = m.scaffold_scene(
        scene_id="zh-test",
        domain="work",
        description="对中文测试",
    )
    yaml_str = m.yaml_dump(scene)
    assert "zh-test" in yaml_str
    assert "对中文测试" in yaml_str


def test_yaml_inline_quoting():
    m = _load()
    # Strings with special chars should be quoted
    assert m._yaml_inline("test:value") == '"test:value"'
    assert m._yaml_inline("hello world") == "hello world"
    assert m._yaml_inline(None) == "null"
    assert m._yaml_inline(True) == "true"
    assert m._yaml_inline(False) == "false"
    assert m._yaml_inline(42) == "42"


def test_list_templates_returns_data():
    m = _load()
    templates = m.list_templates()
    # If PyYAML available and scenes exist, should have entries
    if templates:
        first = templates[0]
        assert "file" in first
        assert "scene_id" in first
        assert "domain" in first


def test_default_template_has_required_fields():
    m = _load()
    scene = m.scaffold_scene(
        scene_id="x",
        domain="work",
        description="d",
    )
    required = [
        "schema", "version", "scene_id", "domain", "scene_class",
        "scene_type", "lifecycle", "approval_state", "owner",
        "trigger", "input_contract", "result_contract", "outcome_metric",
        "consumer", "operator", "triggers", "notes",
    ]
    for r in required:
        assert r in scene, f"missing required field: {r}"


if __name__ == "__main__":
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failures.append((name, e))
    if failures:
        sys.exit(1)
    print(f"\n{len(tests)} tests passed")