"""SSRF防护单元测试。"""

import pytest
from agora.ssrf_guard import validate_external_url


class TestValidateExternalUrl:
    def test_allows_valid_public_https(self):
        validate_external_url("https://api.example.com/v1")

    def test_allows_valid_public_http(self):
        validate_external_url("http://example.com:8080/api")

    def test_rejects_localhost_loopback(self):
        with pytest.raises(ValueError, match="内网地址"):
            validate_external_url("http://127.0.0.1:8000/api")

    def test_rejects_localhost_ipv6(self):
        with pytest.raises(ValueError, match="内网地址"):
            validate_external_url("http://[::1]:8000/api")

    def test_rejects_private_10_network(self):
        with pytest.raises(ValueError, match="内网地址"):
            validate_external_url("http://10.0.0.1/api")

    def test_rejects_private_172_network(self):
        with pytest.raises(ValueError, match="内网地址"):
            validate_external_url("http://172.16.0.1/api")

    def test_rejects_private_192_network(self):
        with pytest.raises(ValueError, match="内网地址"):
            validate_external_url("http://192.168.1.1/api")

    def test_rejects_link_local_metadata_ip(self):
        with pytest.raises(ValueError, match="内网地址"):
            validate_external_url("http://169.254.169.254/latest/meta-data")

    def test_rejects_localhost_hostname(self):
        with pytest.raises(ValueError, match="保留/内部主机名"):
            validate_external_url("http://localhost/api")

    def test_rejects_internal_hostname(self):
        with pytest.raises(ValueError, match="保留/内部主机名"):
            validate_external_url("http://service.internal/api")

    def test_rejects_empty_url(self):
        with pytest.raises(ValueError, match="URL不能为空"):
            validate_external_url("")

    def test_rejects_non_http_scheme(self):
        with pytest.raises(ValueError, match="不支持的协议"):
            validate_external_url("file:///etc/passwd")

    def test_rejects_gopher_scheme(self):
        with pytest.raises(ValueError, match="不支持的协议"):
            validate_external_url("gopher://evil.com/_curl%20http://target")

    def test_rejects_0_0_0_0(self):
        with pytest.raises(ValueError, match="内网地址"):
            validate_external_url("http://0.0.0.0/api")
