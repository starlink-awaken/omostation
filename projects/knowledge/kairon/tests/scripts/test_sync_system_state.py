"""sync_system_state.py 测试 — 覆盖:
1. 真实状态收集 (collect_actual_state)
2. 差异检测 (diff_with_system_yaml)
3. 白名单机制 (非白名单字段被拒绝)
4. system.yaml 读写 (去重 / 替换 / 添加)
5. 备份机制 (apply 模式生成 .bak 文件)
6. 报告渲染
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# ── 加载被测模块（避免依赖 kairon 包结构）──────────────
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "sync_system_state.py"
SPEC = importlib.util.spec_from_file_location("_sync_system_state_under_test", SCRIPT_PATH)
assert SPEC and SPEC.loader, "failed to load spec"
sync_mod = importlib.util.module_from_spec(SPEC)
# 必须把模块挂到 sys.modules 上，@dataclass 才能找到 __module__
sys.modules[SPEC.name] = sync_mod  # type: ignore[arg-type]
SPEC.loader.exec_module(sync_mod)  # type: ignore[union-attr]
# 暴露符号
collect_actual_state = sync_mod.collect_actual_state
diff_with_system_yaml = sync_mod.diff_with_system_yaml
apply_diff = sync_mod.apply_diff
render_report = sync_mod.render_report
ALLOWED_FIELDS = sync_mod.ALLOWED_FIELDS
SYSTEM_YAML = sync_mod.SYSTEM_YAML
TASKS_PLANNED = sync_mod.TASKS_PLANNED
read_system_yaml = sync_mod.read_system_yaml
_get_top_level_value = sync_mod._get_top_level_value
_detect_duplicate_key = sync_mod._detect_duplicate_key
_remove_duplicate_keys = sync_mod._remove_duplicate_keys
_replace_top_level_key = sync_mod._replace_top_level_key
_parse_task_yaml = sync_mod._parse_task_yaml
_collect_task_state = sync_mod._collect_task_state
_collect_debt_state = sync_mod._collect_debt_state
_collect_audit_data = sync_mod._collect_audit_data
_count_adrs = sync_mod._count_adrs
_count_packages = sync_mod._count_packages
_find_next_pending_task = sync_mod._find_next_pending_task
_values_equal = sync_mod._values_equal


# ── 1. collect_actual_state 测试 ───────────────────────────


class TestCollectActualState:
    """测试真实状态收集。"""

    def test_returns_required_keys(self):
        """actual 字典必须包含所有白名单字段。"""
        actual = collect_actual_state()
        for f in ALLOWED_FIELDS:
            assert f in actual, f"missing key: {f}"

    def test_current_phase_is_int_and_in_range(self):
        """current_phase 必须是正整数（>= 28）。"""
        actual = collect_actual_state()
        assert isinstance(actual["current_phase"], int)
        assert actual["current_phase"] >= 28

    def test_total_tasks_matches_actual_dir(self):
        """total_tasks 必须等于 .omo/tasks/planned/ 文件数。"""
        actual = collect_actual_state()
        expected = len(list(TASKS_PLANNED.glob("*.yaml")))
        assert actual["total_tasks"] == expected

    def test_completed_tasks_le_total_tasks(self):
        """completed <= total。"""
        actual = collect_actual_state()
        assert actual["completed_tasks"] <= actual["total_tasks"]
        assert actual["completed_tasks"] >= 0

    def test_health_score_is_non_negative(self):
        """health_score 来自 audit，必须 >= 0。"""
        actual = collect_actual_state()
        assert actual["health_score"] >= 0.0
        assert actual["health_score"] <= 100.0

    def test_updated_at_is_iso_format(self):
        """updated_at 必须是 ISO 8601 字符串。"""
        actual = collect_actual_state()
        assert "T" in actual["updated_at"]
        assert actual["updated_at"].endswith("Z")

    def test_meta_includes_adr_and_package_count(self):
        """_meta 中必须包含 ADR 数与包数。"""
        actual = collect_actual_state()
        assert "adrs" in actual["_meta"]
        assert "packages" in actual["_meta"]
        assert isinstance(actual["_meta"]["adrs"], int)
        assert isinstance(actual["_meta"]["packages"], int)


# ── 2. diff_with_system_yaml 测试 ──────────────────────────


class TestDiffWithSystemYaml:
    """测试差异检测。"""

    def test_no_diff_when_matches(self):
        """actual 与 system.yaml 一致时返回空列表。"""
        actual = collect_actual_state()
        # 用 actual 反向构造 system.yaml 文本
        lines = []
        for f in sorted(ALLOWED_FIELDS):
            v = actual[f]
            if isinstance(v, str):
                lines.append(f'{f}: "{v}"')
            else:
                lines.append(f"{f}: {v}")
        text = "\n".join(lines) + "\n"
        diffs = diff_with_system_yaml(actual, text)
        assert diffs == [], f"unexpected diffs: {diffs}"

    def test_detects_value_change(self):
        """actual 与 system.yaml 不一致时返回差异。"""
        actual = collect_actual_state()
        text = "current_phase: 99\nhealth_score: 1.0\n"
        diffs = diff_with_system_yaml(actual, text)
        # current_phase 必有 diff（actual != 99）
        fields = {d.field for d in diffs}
        assert "current_phase" in fields

    def test_detects_missing_field(self):
        """system.yaml 缺字段时返回 diff with old_value=None。"""
        actual = collect_actual_state()
        text = "current_phase: 28\n"  # only one field
        diffs = diff_with_system_yaml(actual, text)
        missing_diffs = [d for d in diffs if d.old_value is None]
        assert len(missing_diffs) > 0

    def test_detects_duplicate_keys(self):
        """system.yaml 中某 key 重复出现时返回 dedupe diff。"""
        actual = collect_actual_state()
        text = "current_phase: 28\ncurrent_phase: 29\n"
        diffs = diff_with_system_yaml(actual, text)
        dup = [d for d in diffs if d.field == "current_phase"]
        assert len(dup) == 1
        assert "duplicate" in dup[0].reason

    def test_handles_duplicate_next_milestone(self):
        """回归测试：即使 system.yaml 中 next_milestone 不重复，sync 也能处理。"""
        actual = collect_actual_state()
        # 真实文件可能或可能不重复；用合成数据强制制造重复场景
        text = 'next_milestone: "A"\nnext_milestone: "B"\n'
        dup_count = _detect_duplicate_key(text, "next_milestone")
        assert dup_count == 2, "synthetic input should have 2 duplicates"
        diffs = diff_with_system_yaml(actual, text)
        # 真实 next_milestone 在 actual 中存在，dup_count>=2 必产生 dedupe diff
        dup_diffs = [d for d in diffs if d.field == "next_milestone"]
        assert len(dup_diffs) >= 1
        assert "duplicate" in dup_diffs[0].reason


# ── 3. 白名单机制测试 ──────────────────────────────────────


class TestWhitelistEnforcement:
    """测试 apply_diff 拒绝非白名单字段。"""

    def test_refuses_non_whitelisted_field(self, tmp_path: Path):
        """非白名单字段写入必须 raise PermissionError。"""
        fake_yaml = tmp_path / "system.yaml"
        fake_yaml.write_text("foo: 1\n", encoding="utf-8")
        bad_diff = sync_mod.FieldDiff(field="foo", old_value=1, new_value=2, reason="test")
        with pytest.raises(PermissionError, match="refused"):
            apply_diff([bad_diff], fake_yaml, apply=False)

    def test_goals_cannot_be_modified(self, tmp_path: Path):
        """goals 字段必须被拒绝（人类专属）。"""
        fake_yaml = tmp_path / "system.yaml"
        fake_yaml.write_text("goals: keep\n", encoding="utf-8")
        bad_diff = sync_mod.FieldDiff(field="goals", old_value="keep", new_value="change", reason="test")
        with pytest.raises(PermissionError):
            apply_diff([bad_diff], fake_yaml, apply=False)

    def test_debt_weight_items_cannot_be_modified(self, tmp_path: Path):
        """debt_weight_items 字段必须被拒绝。"""
        fake_yaml = tmp_path / "system.yaml"
        fake_yaml.write_text("debt_weight_items: {}\n", encoding="utf-8")
        bad_diff = sync_mod.FieldDiff(
            field="debt_weight_items",
            old_value="{}",
            new_value="x",
            reason="test",
        )
        with pytest.raises(PermissionError):
            apply_diff([bad_diff], fake_yaml, apply=False)

    def test_next_active_tasks_cannot_be_modified(self, tmp_path: Path):
        """next_active_tasks 字段必须被拒绝。"""
        fake_yaml = tmp_path / "system.yaml"
        fake_yaml.write_text("next_active_tasks: []\n", encoding="utf-8")
        bad_diff = sync_mod.FieldDiff(field="next_active_tasks", old_value="[]", new_value="x", reason="test")
        with pytest.raises(PermissionError):
            apply_diff([bad_diff], fake_yaml, apply=False)


# ── 4. system.yaml 读写测试 ────────────────────────────────


class TestYamlIO:
    """测试 YAML 读/写/去重。"""

    def test_get_top_level_value_simple(self):
        """_get_top_level_value 应能取顶层 key。"""
        text = "current_phase: 28\nhealth_score: 80.0\n"
        line = _get_top_level_value(text, "current_phase")
        assert line == "current_phase: 28"

    def test_get_top_level_value_missing(self):
        """缺 key 时返回 None。"""
        text = "current_phase: 28\n"
        assert _get_top_level_value(text, "missing_key") is None

    def test_detect_duplicate_keys(self):
        """重复 key 检测正确。"""
        text = "foo: 1\nfoo: 2\nfoo: 3\n"
        assert _detect_duplicate_key(text, "foo") == 3

    def test_remove_duplicate_keeps_last(self):
        """_remove_duplicate_keys 保留最后一条。"""
        text = "foo: 1\nfoo: 2\nfoo: 3\n"
        result = _remove_duplicate_keys(text, "foo", keep_last=True)
        # 只应剩 1 个 foo
        assert _detect_duplicate_key(result, "foo") == 1
        assert "foo: 3" in result

    def test_replace_top_level_key(self):
        """_replace_top_level_key 替换已有 key。"""
        text = "foo: 1\nbar: 2\n"
        result = _replace_top_level_key(text, "foo", "999")
        assert "foo: 999" in result
        assert "bar: 2" in result
        # foo 应只出现 1 次
        assert _detect_duplicate_key(result, "foo") == 1

    def test_replace_top_level_key_adds_when_missing(self):
        """_replace_top_level_key 缺 key 时追加。"""
        text = "foo: 1\n"
        result = _replace_top_level_key(text, "bar", "2")
        assert "bar: 2" in result
        assert "foo: 1" in result


# ── 5. 备份机制测试 ────────────────────────────────────────


class TestBackupMechanism:
    """测试 apply 模式生成备份。"""

    def test_apply_creates_backup(self, tmp_path: Path):
        """apply=True 时必须生成 .bak 文件。"""
        fake_yaml = tmp_path / "system.yaml"
        fake_yaml.write_text("current_phase: 28\n", encoding="utf-8")
        diff = sync_mod.FieldDiff(field="current_phase", old_value=28, new_value=29, reason="test")
        apply_diff([diff], fake_yaml, apply=True)
        backups = list(tmp_path.glob("system.yaml.bak-*"))
        assert len(backups) == 1
        # 验证新文件已更新
        new_text = fake_yaml.read_text()
        assert "current_phase: 29" in new_text

    def test_dryrun_does_not_create_backup(self, tmp_path: Path):
        """apply=False 时**不**写文件、不生成备份。"""
        fake_yaml = tmp_path / "system.yaml"
        original = "current_phase: 28\n"
        fake_yaml.write_text(original, encoding="utf-8")
        diff = sync_mod.FieldDiff(field="current_phase", old_value=28, new_value=29, reason="test")
        apply_diff([diff], fake_yaml, apply=False)
        backups = list(tmp_path.glob("system.yaml.bak-*"))
        assert len(backups) == 0
        # 文件未改
        assert fake_yaml.read_text() == original


# ── 6. 报告渲染测试 ────────────────────────────────────────


class TestReportRendering:
    """测试 render_report 输出。"""

    def test_report_contains_required_sections(self):
        """报告必须包含 4 个主要章节。"""
        actual = collect_actual_state()
        diffs = diff_with_system_yaml(actual, read_system_yaml(SYSTEM_YAML))
        report = render_report(actual, diffs, SYSTEM_YAML)
        for header in [
            "## 1. 真实状态",
            "## 2. 差异清单",
            "## 3. 白名单",
            "## 4. 安全机制",
        ]:
            assert header in report, f"missing section: {header}"

    def test_report_lists_all_whitelisted_fields(self):
        """报告白名单章节必须列出所有允许字段。"""
        actual = collect_actual_state()
        report = render_report(actual, [], SYSTEM_YAML)
        for f in sorted(ALLOWED_FIELDS):
            assert f"`{f}`" in report, f"missing field in whitelist section: {f}"

    def test_report_handles_no_diffs(self):
        """无差异时报告必须显示「无差异」。"""
        actual = collect_actual_state()
        report = render_report(actual, [], SYSTEM_YAML)
        assert "**无差异**" in report


# ── 7. 集成测试：真实 system.yaml dry-run ─────────────────


class TestIntegration:
    """对真实 system.yaml 跑 dry-run。"""

    def test_dryrun_finds_inconsistencies(self):
        """真实 system.yaml 必须有差异（否则任务无意义）。"""
        actual = collect_actual_state()
        text = read_system_yaml(SYSTEM_YAML)
        diffs = diff_with_system_yaml(actual, text)
        # 至少应该有 1 处差异（健康分/状态）
        assert len(diffs) > 0, "expected at least one inconsistency"

    def test_dryrun_does_not_modify_real_file(self):
        """dry-run 必须不修改真实 system.yaml。"""
        original = SYSTEM_YAML.read_text()
        try:
            actual = collect_actual_state()
            text = read_system_yaml(SYSTEM_YAML)
            diffs = diff_with_system_yaml(actual, text)
            apply_diff(diffs, SYSTEM_YAML, apply=False)
            # 验证文件未变
            assert SYSTEM_YAML.read_text() == original
        finally:
            # 保险：恢复（其实不应该被改）
            assert SYSTEM_YAML.read_text() == original
