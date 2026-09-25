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


def test_api_endpoint_compatibility(redirector_server):
    req = urllib.request.Request(f"{redirector_server}/api/panorama/overview")
    with urllib.request.urlopen(req, timeout=3) as resp:
        assert resp.status == 200
        assert resp.headers.get_content_type() == "application/json"
        data = json.loads(resp.read().decode("utf-8"))
        assert isinstance(data, dict)
