import http.server
import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sunset_redirector",
    ROOT / "bin" / "panorama" / "sunset_redirector.py",
)
sunset_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sunset_mod)

SunsetRedirectHandler = sunset_mod.SunsetRedirectHandler
get_latest_telemetry = sunset_mod.get_latest_telemetry


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not follow redirects automatically


@pytest.fixture(scope="module")
def redirector_server():
    # Bind to random ephemeral port
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SunsetRedirectHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_root_redirect(redirector_server):
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        response = opener.open(f"{redirector_server}/", timeout=3)
        status_code = response.getcode()
        headers = response.info()
    except urllib.error.HTTPError as e:
        status_code = e.code
        headers = e.headers

    assert status_code == 302
    assert headers.get("Location") == "http://localhost:5173/panorama"


def test_health_endpoint(redirector_server):
    req = urllib.request.Request(f"{redirector_server}/health")
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "SUNSET_REDIRECTING"
        assert data.get("converged") is True
        # 新鲜度必须在探活面可见 (stale 不再静默)
        assert "data_stale" in data
        assert "data_age_seconds" in data


def test_api_endpoint_compatibility(redirector_server):
    req = urllib.request.Request(f"{redirector_server}/api/panorama/overview")
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200
        assert resp.headers.get_content_type() == "application/json"
        data = json.loads(resp.read().decode("utf-8"))
        assert isinstance(data, dict)


def test_telemetry_marks_missing_snapshot_as_stale(tmp_path, monkeypatch):
    """没有扁平快照时必须显式 stale=True, 不能静默返回降级载荷冒充最新遥测."""
    monkeypatch.setattr(sunset_mod, "RUNTIME_DATA_PATH", tmp_path / "nope.json")
    data = get_latest_telemetry()
    meta = data["_meta"]
    assert meta["stale"] is True
    assert meta["generated_at"] is None
    assert meta["age_seconds"] is None
    assert data["status"] == "CONVERGED_TO_COCKPIT"


def test_telemetry_marks_fresh_snapshot_not_stale(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    payload = {"generated_at": (now - timedelta(seconds=30)).isoformat()}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(sunset_mod, "RUNTIME_DATA_PATH", path)

    data = get_latest_telemetry()
    meta = data["_meta"]
    assert meta["stale"] is False
    assert meta["generated_at"] == payload["generated_at"]
    assert 0 <= meta["age_seconds"] <= 60


def test_telemetry_marks_out_of_cadence_snapshot_as_stale(tmp_path, monkeypatch):
    """refresh job 断档时(> stale_after_seconds) 必须把 stale 暴露给调用方."""
    from datetime import datetime, timedelta, timezone

    stale_at = datetime.now(timezone.utc) - timedelta(seconds=sunset_mod.DATA_STALE_SECONDS + 60)
    payload = {"generated_at": stale_at.isoformat()}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(sunset_mod, "RUNTIME_DATA_PATH", path)

    data = get_latest_telemetry()
    meta = data["_meta"]
    assert meta["stale"] is True
    assert meta["age_seconds"] > sunset_mod.DATA_STALE_SECONDS
    assert meta["stale_after_seconds"] == sunset_mod.DATA_STALE_SECONDS


def test_telemetry_survives_malformed_snapshot(tmp_path, monkeypatch):
    """坏 JSON → 降级载荷 + stale, 不抛异常 (兼容层绝不 500)."""
    path = tmp_path / "data.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(sunset_mod, "RUNTIME_DATA_PATH", path)

    data = get_latest_telemetry()
    assert data["status"] == "CONVERGED_TO_COCKPIT"
    assert data["_meta"]["stale"] is True
