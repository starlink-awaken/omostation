"""HTTP server for llm-gateway — standalone testable module.

Provides a lightweight HTTP server (stdlib only) that exposes
:func:`detect_backends` and :func:`create_provider` as REST endpoints.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from .detection import detect_backends
from .provider import LLMRequest


class LLMGatewayHandler(BaseHTTPRequestHandler):
    """HTTP request handler for LLM generation."""

    def do_POST(self) -> None:
        if self.path != "/v1/generate":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"Invalid JSON"}')
            return

        prompt: str = body.get("prompt", "")
        model: str | None = body.get("model")
        provider_name: str | None = body.get("provider")  # noqa: F841

        providers = detect_backends()
        if not providers:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b'{"error":"No LLM backends available"}')
            return

        provider = providers[0]
        if not provider.is_available():
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b'{"error":"Provider not available"}')
            return

        req = LLMRequest(prompt=prompt, model=model)
        try:
            resp = provider.complete(req)
            result: dict[str, Any] = {
                "content": resp.content,
                "model": resp.model,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def do_GET(self) -> None:
        if self.path == "/v1/health":
            providers = detect_backends()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            result = {
                "status": "ok",
                "providers": len(providers),
            }
            self.wfile.write(json.dumps(result).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[llm-gateway] {args[0]} {args[1]} {args[2]}\n")


def serve(port: int = 9090) -> None:
    """Start the llm-gateway HTTP server.

    Endpoints:
        POST /v1/generate  — generate LLM response
        GET  /v1/health    — health check
    """
    server = HTTPServer(("0.0.0.0", port), LLMGatewayHandler)  # noqa: S104
    print(f"llm-gateway HTTP server: http://localhost:{port}")
    print("  POST /v1/generate  — generate LLM response")
    print("  GET  /v1/health     — health check")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
