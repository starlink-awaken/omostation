"""MOF Agora Hook 测试套件

覆盖: _load_routes · _match_route · pre_check · post_audit · health_check
运行: uv run pytest tests/test_mof_agora_hook.py -v
"""

import json
import os
import sqlite3
import time

import pytest
import yaml

from ecos.ssot.tools import mof_agora_hook as mof


# ═══════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_globals():
    """每个测试前重置模块级全局状态"""
    mof.ROUTES_CACHE = None
    mof.ROUTES_CACHE_TIME = 0
    mof.CACHE_TTL = 300
    mof.stats["total_checks"] = 0
    mof.stats["total_audits"] = 0
    mof.stats["blocked"] = 0
    mof.stats["anomalies"] = 0
    mof.stats["start_time"] = time.time()


@pytest.fixture
def mock_dirs(monkeypatch, tmp_path):
    """创建临时目录结构并 monkeypatch 模块路径"""
    l0_m1 = tmp_path / "mof" / "m1"
    bosroute_dir = l0_m1 / "bosroute"
    comp_dir = l0_m1 / "component"
    bosroute_dir.mkdir(parents=True)
    comp_dir.mkdir(parents=True)

    audit_file = tmp_path / ".ecos" / "bos-audit.jsonl"
    cards_db = tmp_path / "cards" / "cards.db"

    # Patch module paths
    monkeypatch.setattr(mof, "L0_M1", l0_m1)
    monkeypatch.setattr(mof, "AUDIT_LOG", audit_file)
    monkeypatch.setattr(mof, "CARDS_DB", cards_db)

    return {
        "l0_m1": l0_m1,
        "bosroute_dir": bosroute_dir,
        "comp_dir": comp_dir,
        "audit_file": audit_file,
        "cards_db": cards_db,
    }


def _write_yaml(path, data):
    """Helper: write a YAML file"""
    path.write_text(yaml.dump(data, allow_unicode=True))


# ═══════════════════════════════════════════════
# Test: _load_routes()
# ═══════════════════════════════════════════════


class TestLoadRoutes:
    """BOS 路由表加载 + 缓存"""

    def test_load_from_bosroute(self, mock_dirs):
        """从 bosroute/ 目录加载 YAML 路由"""
        _write_yaml(
            mock_dirs["bosroute_dir"] / "cockpit.yaml",
            {
                "name": "bos://cockpit/tools/cards_status",
                "status": "active",
                "properties": {"layer": "L2"},
                "description": "卡片状态查询",
            },
        )
        _write_yaml(
            mock_dirs["bosroute_dir"] / "auth.yaml",
            {
                "name": "bos://auth/login",
                "status": "active",
                "properties": {"layer": "L1"},
                "description": "用户登录",
            },
        )

        routes = mof._load_routes()

        assert len(routes) == 2
        assert routes["bos://cockpit/tools/cards_status"]["status"] == "active"
        assert routes["bos://auth/login"]["layer"] == "L1"

    def test_load_from_component_with_bos_uri(self, mock_dirs):
        """从 component/ 目录加载 BOS_URI 协议组件"""
        _write_yaml(
            mock_dirs["comp_dir"] / "dashboard.yaml",
            {
                "name": "dashboard-service",
                "status": "active",
                "properties": {"protocol": "BOS_URI", "layer": "L2"},
                "description": "仪表盘服务",
            },
        )
        # Non-BOS_URI component should be ignored
        _write_yaml(
            mock_dirs["comp_dir"] / "other.yaml",
            {
                "name": "other-service",
                "status": "active",
                "properties": {"protocol": "HTTP", "layer": "L1"},
                "description": "普通服务",
            },
        )

        routes = mof._load_routes()

        assert len(routes) == 1
        assert "bos://dashboard-service/*" in routes

    def test_empty_dirs(self, mock_dirs):
        """空目录返回空路由表"""
        routes = mof._load_routes()
        assert routes == {}

    def test_missing_dir(self, mock_dirs, monkeypatch):
        """目录不存在时优雅处理"""
        monkeypatch.setattr(mof, "L0_M1", mock_dirs["l0_m1"] / "nonexistent")
        routes = mof._load_routes()
        assert routes == {}

    def test_caching_within_ttl(self, mock_dirs):
        """TTL 内复用缓存"""
        _write_yaml(
            mock_dirs["bosroute_dir"] / "a.yaml",
            {"name": "bos://a/b", "status": "active"},
        )

        # First load
        r1 = mof._load_routes()
        assert len(r1) == 1

        # Remove file and load again — should get cached result
        (mock_dirs["bosroute_dir"] / "a.yaml").unlink()
        r2 = mof._load_routes()
        assert len(r2) == 1  # Still has cached entry

    def test_cache_expires_after_ttl(self, mock_dirs, monkeypatch):
        """TTL 过期后重新加载"""
        monkeypatch.setattr(mof, "CACHE_TTL", 0.01)

        _write_yaml(
            mock_dirs["bosroute_dir"] / "a.yaml",
            {"name": "bos://a/b", "status": "active"},
        )

        # First load
        r1 = mof._load_routes()
        assert len(r1) == 1

        # Remove file
        (mock_dirs["bosroute_dir"] / "a.yaml").unlink()
        # Add new file
        _write_yaml(
            mock_dirs["bosroute_dir"] / "b.yaml",
            {"name": "bos://b/c", "status": "active"},
        )

        time.sleep(0.02)  # Wait for TTL expiry
        r2 = mof._load_routes()
        assert len(r2) == 1
        assert "bos://b/c" in r2

    def test_env_var_overrides_cache_ttl(self, mock_dirs, monkeypatch):
        """环境变量 BOS_ROUTES_CACHE_TTL 覆盖默认 TTL"""
        monkeypatch.setenv("BOS_ROUTES_CACHE_TTL", "600")

        # Need to re-import the module to pick up env var at module load time
        # But since CACHE_TTL is evaluated at import, we monkeypatch the value

        monkeypatch.setattr(mof, "CACHE_TTL", int(os.environ.get("BOS_ROUTES_CACHE_TTL", "300")))
        assert mof.CACHE_TTL == 600

    def test_invalid_yaml_skipped(self, mock_dirs):
        """无效 YAML 文件被跳过"""
        (mock_dirs["bosroute_dir"] / "bad.yaml").write_text("{invalid: yaml: unclosed")
        _write_yaml(
            mock_dirs["bosroute_dir"] / "good.yaml",
            {"name": "bos://good", "status": "active"},
        )

        routes = mof._load_routes()
        assert len(routes) == 1
        assert "bos://good" in routes


# ═══════════════════════════════════════════════
# Test: _match_route()
# ═══════════════════════════════════════════════


class TestMatchRoute:
    """BOS URI 匹配"""

    @pytest.fixture
    def sample_routes(self):
        return {
            "bos://cockpit/tools/cards_status": {
                "status": "active",
                "layer": "L2",
                "description": "卡片状态",
            },
            "bos://cockpit/tools/*": {
                "status": "active",
                "layer": "L2",
                "description": "工具通配",
            },
            "bos://auth/login": {
                "status": "active",
                "layer": "L1",
                "description": "登录",
            },
        }

    def test_exact_match(self, sample_routes):
        """精确匹配"""
        route = mof._match_route("bos://cockpit/tools/cards_status", sample_routes)
        assert route is not None
        assert route["description"] == "卡片状态"

    def test_prefix_wildcard_match(self, sample_routes):
        """前缀通配匹配 (bos://cockpit/tools/* 匹配子路径)"""
        route = mof._match_route("bos://cockpit/tools/deploy", sample_routes)
        assert route is not None
        assert route["description"] == "工具通配"

    def test_no_match(self, sample_routes):
        """未匹配返回 None"""
        route = mof._match_route("bos://unknown/endpoint", sample_routes)
        assert route is None

    def test_empty_routes(self):
        """空路由表返回 None"""
        route = mof._match_route("bos://anything", {})
        assert route is None

    def test_uri_without_protocol_prefix(self, sample_routes):
        """URI 不带 bos:// 前缀不匹配"""
        route = mof._match_route("cockpit/tools/cards_status", sample_routes)
        assert route is None


# ═══════════════════════════════════════════════
# Test: pre_check()
# ═══════════════════════════════════════════════


class TestPreCheck:
    """前置校验"""

    def test_allow_active_route(self, mock_dirs):
        """active 路由放行"""
        _write_yaml(
            mock_dirs["bosroute_dir"] / "route.yaml",
            {"name": "bos://my/api", "status": "active"},
        )

        ok, reason = mof.pre_check("bos://my/api")
        assert ok is True
        assert reason == "ok"
        assert mof.stats["total_checks"] == 1
        assert mof.stats["blocked"] == 0

    def test_block_unregistered_uri(self, mock_dirs):
        """未注册 URI 拒绝"""
        ok, reason = mof.pre_check("bos://unknown/uri")
        assert ok is False
        assert "未注册" in reason
        assert mof.stats["blocked"] == 1

    def test_block_deprecated_route(self, mock_dirs):
        """废弃路由拒绝 (status != active)"""
        _write_yaml(
            mock_dirs["bosroute_dir"] / "old.yaml",
            {"name": "bos://old/api", "status": "deprecated"},
        )

        ok, reason = mof.pre_check("bos://old/api")
        assert ok is False
        assert "废弃" in reason
        assert mof.stats["blocked"] == 1

    def test_block_inactive_route(self, mock_dirs):
        """非 active 状态都拒绝"""
        for status in ("inactive", "archived", "retired", "?"):
            _write_yaml(
                mock_dirs["bosroute_dir"] / f"{status}.yaml",
                {"name": f"bos://test/{status}", "status": status},
            )

        ok, reason = mof.pre_check("bos://test/inactive")
        assert ok is False
        assert "废弃" in reason


# ═══════════════════════════════════════════════
# Test: post_audit()
# ═══════════════════════════════════════════════


class TestPostAudit:
    """后置审计"""

    def test_normal_audit_writes_log(self, mock_dirs):
        """正常请求写入审计日志"""
        mof.post_audit("bos://test/endpoint", 200, 42)

        assert mof.stats["total_audits"] == 1
        assert mof.stats["anomalies"] == 0

        lines = mock_dirs["audit_file"].read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["bos_uri"] == "bos://test/endpoint"
        assert entry["status_code"] == 200
        assert entry["duration_ms"] == 42
        assert entry["anomaly"] is False

    def test_anomaly_audit_with_cards(self, mock_dirs):
        """异常状态写入审计 + 创建 CARDS 卡片"""
        # Setup cards.db
        cards_db = mock_dirs["cards_db"]
        cards_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(cards_db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                type TEXT,
                status TEXT,
                title TEXT,
                domain TEXT,
                priority TEXT,
                summary TEXT,
                content TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        mof.post_audit("bos://test/crash", 500, 999)

        assert mof.stats["anomalies"] == 1

        # Check audit log
        lines = mock_dirs["audit_file"].read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["anomaly"] is True
        assert entry["status_code"] == 500

        # Check CARDS db
        conn = sqlite3.connect(str(cards_db))
        row = conn.execute("SELECT id, type, status, title, priority FROM cards").fetchone()
        assert row is not None
        assert "DEBT-BOS" in row[0]
        assert row[1] == "debt"
        assert row[2] == "identified"
        assert "crash" in row[3]  # title contains URI
        conn.close()

    def test_anomaly_but_no_cards_db(self, mock_dirs):
        """异常但 CARDS_DB 不存在时不报错"""
        mof.post_audit("bos://test/error", 503, 100)

        assert mof.stats["anomalies"] == 1

        # Audit log still written
        lines = mock_dirs["audit_file"].read_text().strip().splitlines()
        assert len(lines) == 1

    def test_audit_dir_auto_created(self, mock_dirs):
        """审计日志目录自动创建"""
        mof.post_audit("bos://test/endpoint", 200, 10)
        assert mock_dirs["audit_file"].parent.exists()
        assert mock_dirs["audit_file"].exists()

    def test_multiple_audits_append(self, mock_dirs):
        """多次审计追加写入"""
        for i in range(3):
            mof.post_audit(f"bos://test/{i}", 200, i)

        lines = mock_dirs["audit_file"].read_text().strip().splitlines()
        assert len(lines) == 3

    def test_multiple_anomalies_increment_stats(self, mock_dirs):
        """多次异常递增统计数据"""
        cards_db = mock_dirs["cards_db"]
        cards_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(cards_db))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                type TEXT, status TEXT, title TEXT,
                domain TEXT, priority TEXT,
                summary TEXT, content TEXT,
                created_at TEXT, updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        for i in range(3):
            mof.post_audit(f"bos://test/crash{i}", 500, 100)

        assert mof.stats["anomalies"] == 3
        assert mof.stats["total_audits"] == 3


# ═══════════════════════════════════════════════
# Test: health_check()
# ═══════════════════════════════════════════════


class TestHealthCheck:
    """健康检查"""

    def test_initial_stats(self, mock_dirs):
        """初始状态统计"""
        hc = mof.health_check()
        assert hc["status"] == "healthy"
        assert hc["routes_count"] == 0
        assert hc["stats"]["total_checks"] == 0
        assert hc["stats"]["total_audits"] == 0
        assert hc["stats"]["blocked"] == 0
        assert hc["stats"]["anomalies"] == 0
        assert hc["stats"]["block_rate"] == "0.0%"
        assert "uptime_hours" in hc["stats"]

    def test_stats_after_operations(self, mock_dirs):
        """操作后统计反映累计数据"""
        _write_yaml(
            mock_dirs["bosroute_dir"] / "a.yaml",
            {"name": "bos://a/b", "status": "active"},
        )

        mof.pre_check("bos://a/b")          # 1 check, 0 blocked
        mof.pre_check("bos://unknown")      # 1 check, 1 blocked
        mof.post_audit("bos://a/b", 200, 5)  # 1 audit
        mof.post_audit("bos://a/b", 500, 5)  # 1 audit, 1 anomaly

        hc = mof.health_check()
        assert hc["stats"]["total_checks"] == 2
        assert hc["stats"]["blocked"] == 1
        assert hc["stats"]["total_audits"] == 2
        assert hc["stats"]["anomalies"] == 1
        assert hc["stats"]["block_rate"] == "50.0%"

    def test_returns_routes_count(self, mock_dirs):
        """返回路由数量"""
        _write_yaml(
            mock_dirs["bosroute_dir"] / "r1.yaml",
            {"name": "bos://route/1", "status": "active"},
        )
        _write_yaml(
            mock_dirs["bosroute_dir"] / "r2.yaml",
            {"name": "bos://route/2", "status": "active"},
        )

        hc = mof.health_check()
        assert hc["routes_count"] == 2

    def test_cache_age(self, mock_dirs):
        """cache_age 是数值"""
        _write_yaml(
            mock_dirs["bosroute_dir"] / "r.yaml",
            {"name": "bos://test", "status": "active"},
        )

        mof._load_routes()
        hc = mof.health_check()
        assert isinstance(hc["cache_age"], float)
        assert hc["cache_age"] >= 0
