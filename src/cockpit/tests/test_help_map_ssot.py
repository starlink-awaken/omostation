"""help_map SSOT 测试 — Phase A3 不变量.

覆盖:
  · GROUPS 由 COMMAND_CATALOG 生成 (分组 = catalog category 去重)
  · catalog 新增命令自动出现在地图 (all_command_names ⊇ catalog 键)
  · GUIDE_SECTIONS 引用的命令存在 (防 catalog 改名后悬空)
"""

from __future__ import annotations

from cockpit.commands import help_map
from cockpit.commands.delegation import ensure_delegated_catalog
from cockpit.commands.registry import CATEGORY_GROUPS, COMMAND_CATALOG


class TestGroupsFromCatalog:
    def test_groups_match_catalog_categories(self):
        ensure_delegated_catalog()
        help_map.rebuild_groups()
        group_titles = {title for title, _style, _rows in help_map.GROUPS}
        catalog_categories = {meta.category for meta in COMMAND_CATALOG.values()}
        assert group_titles == catalog_categories, "地图分组必须与 catalog category 一一对应"

    def test_all_catalog_commands_in_map(self):
        ensure_delegated_catalog()
        help_map.rebuild_groups()
        names = set(help_map.all_command_names())
        missing = set(COMMAND_CATALOG.keys()) - names
        assert not missing, f"catalog 命令未出现在产品地图: {sorted(missing)}"

    def test_every_category_has_order(self):
        unknown = {m.category for m in COMMAND_CATALOG.values()} - set(CATEGORY_GROUPS)
        assert not unknown, f"catalog 使用了 CATEGORY_GROUPS 未登记的分组: {sorted(unknown)}"


class TestGuideSections:
    def test_guide_referenced_commands_exist(self):
        names = set(help_map.all_command_names())
        missing = [c for c in help_map.GUIDE_REFERENCED_COMMANDS if c not in names]
        assert not missing, f"引导段引用了不存在的命令 (catalog 改名后悬空?): {missing}"

    def test_blurb_overrides_targets_exist(self):
        names = set(help_map.all_command_names())
        missing = [c for c in help_map.BLURB_OVERRIDES if c not in names]
        assert not missing, f"BLURB_OVERRIDES 指向不存在的命令: {missing}"
