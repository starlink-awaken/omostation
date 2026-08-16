"""测试 Schema 迁移功能 — SchemaMigration + MCP 工具入口"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from eidos.errors import EidosError, ErrorCode
from eidos.mcp_server import handle_migrate, handle_migration_list
from eidos.schema import SchemaMigration, get_migrations, migrate_schema_instance, register_migration


def _transform_v1_to_v2(data: dict) -> dict:
    """模拟 v1→v2 迁移：添加 version 字段，重命名 old_field"""
    data["version"] = "2.0"
    if "old_field" in data:
        data["new_field"] = data.pop("old_field")
    return data


def _transform_v2_to_v3(data: dict) -> dict:
    """模拟 v2→v3 迁移：拆分 summary 为 short_summary + description"""
    if "summary" in data and data["summary"]:
        parts = data["summary"].split(".", 1)
        data["short_summary"] = parts[0].strip()
        data["description"] = parts[1].strip() if len(parts) > 1 else ""
    data["version"] = "3.0"
    return data


def cleanup_migration(schema_name: str) -> None:
    """清理测试注册的迁移"""
    from eidos.schema import _SCHEMA_MIGRATIONS

    _SCHEMA_MIGRATIONS.pop(schema_name, None)


# ── SchemaMigration 单元测试 ──


def test_migration_create_and_apply():
    m = SchemaMigration(
        from_version="1.0",
        to_version="2.0",
        description="v1 to v2 test",
        transform=_transform_v1_to_v2,
    )
    result = m.apply({"name": "test", "old_field": "old"})
    assert result["version"] == "2.0"
    assert "new_field" in result
    assert result["new_field"] == "old"
    assert "old_field" not in result


def test_migration_no_transform():
    m = SchemaMigration(from_version="1.0", to_version="2.0", description="no transform")
    result = m.apply({"name": "test"})
    assert result == {"name": "test"}


# ── Register/Get 测试 ──


def test_register_and_get_migrations():
    cleanup_migration("TestDoc")
    m1 = SchemaMigration(from_version="1.0", to_version="2.0", transform=_transform_v1_to_v2)
    m2 = SchemaMigration(from_version="2.0", to_version="3.0", transform=_transform_v2_to_v3)
    register_migration("TestDoc", m1)
    register_migration("TestDoc", m2)

    migrations = get_migrations("TestDoc")
    assert len(migrations) == 2
    assert migrations[0].from_version == "1.0"
    assert migrations[1].from_version == "2.0"


# ── migrate_schema_instance 测试 ──


def test_migrate_chain_v1_to_v3():
    cleanup_migration("TestDoc")
    m1 = SchemaMigration(from_version="1.0", to_version="2.0", transform=_transform_v1_to_v2)
    m2 = SchemaMigration(from_version="2.0", to_version="3.0", transform=_transform_v2_to_v3)
    register_migration("TestDoc", m1)
    register_migration("TestDoc", m2)

    data = {"name": "test", "old_field": "old", "summary": "Short. Long description."}
    result = migrate_schema_instance("TestDoc", data, from_version="1.0", to_version="3.0")

    assert result["version"] == "3.0"
    assert result["new_field"] == "old"
    assert result["short_summary"] == "Short"
    assert result["description"] == "Long description."
    assert "_migrated_version" in result


def test_migrate_partial_v1_to_v2():
    cleanup_migration("TestDoc")
    m1 = SchemaMigration(from_version="1.0", to_version="2.0", transform=_transform_v1_to_v2)
    register_migration("TestDoc", m1)

    data = {"name": "test", "old_field": "old"}
    result = migrate_schema_instance("TestDoc", data, from_version="1.0", to_version="2.0")

    assert result["version"] == "2.0"
    assert result["_migrated_version"] == "2.0"


def test_migrate_no_migrations():
    """无迁移注册时应直接返回原始数据"""
    cleanup_migration("NoSchema")
    data = {"name": "test"}
    result = migrate_schema_instance("NoSchema", data, from_version="1.0", to_version="2.0")
    assert result == data


def test_migrate_failure_raises():
    cleanup_migration("BadDoc")

    def _failing(data):
        raise ValueError("migration failed")

    m = SchemaMigration(from_version="1.0", to_version="2.0", transform=_failing)
    register_migration("BadDoc", m)

    import pytest

    with pytest.raises(EidosError) as exc:
        migrate_schema_instance("BadDoc", {"name": "test"}, from_version="1.0", to_version="2.0")
    assert exc.value.code == ErrorCode.SCHEMA_MIGRATION_FAILED


# ── MCP 工具测试 ──


def test_handle_migrate_success():
    cleanup_migration("MCPTest")
    m = SchemaMigration(from_version="1.0", to_version="2.0", transform=_transform_v1_to_v2)
    register_migration("MCPTest", m)

    result = handle_migrate(
        {
            "schema_name": "MCPTest",
            "data": {"name": "test", "old_field": "old"},
            "from_version": "1.0",
            "to_version": "2.0",
        }
    )
    assert result["migrated"] is True
    assert result["data"]["version"] == "2.0"


def test_handle_migrate_missing_schema():
    result = handle_migrate({"schema_name": "", "data": {}})
    assert result["migrated"] is False
    assert "error" in result


def test_handle_migrate_no_migrations():
    cleanup_migration("NoMig")
    result = handle_migrate(
        {
            "schema_name": "NoMig",
            "data": {"name": "test"},
            "from_version": "1.0",
            "to_version": "2.0",
        }
    )
    assert result["migrated"] is False
    assert result["note"] is not None


def test_handle_migration_list():
    cleanup_migration("ListTest")
    m = SchemaMigration(from_version="1.0", to_version="2.0", description="list test")
    register_migration("ListTest", m)

    result = handle_migration_list()
    assert result["count"] >= 1
    found = any(entry["schema"] == "ListTest" and entry["from_version"] == "1.0" for entry in result["migrations"])
    assert found, "Expected ListTest migration in results"


def test_handle_migration_list_empty():
    """清理后应返回空列表"""
    for schema_name in list(["MCPTest", "BadDoc", "NoMig", "TestDoc", "ListTest"]):
        cleanup_migration(schema_name)

    result = handle_migration_list()
    assert result["count"] == 0
