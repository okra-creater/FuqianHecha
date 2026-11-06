"""Dependency-free local web server for the FuqianHecha interface."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .analyzer import BaselineAnalyzer


STATIC_ROOT = Path(__file__).resolve().parents[1] / "web"
MAX_REQUEST_BYTES = 80_000
ANALYZER = BaselineAnalyzer()
_STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
_SECURITY_HEADERS = (
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
    (
        "Content-Security-Policy",
        "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
        "script-src 'self'; style-src 'self'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'",
    ),
)


def analyze_payload(
    payload: Any,
    analyzer: BaselineAnalyzer = ANALYZER,
) -> tuple[int, dict[str, Any]]:
    """Validate one decoded request payload and return an HTTP-style result."""

    if not isinstance(payload, dict):
        return 400, {
            "error": "invalid_request",
            "message": "请求正文必须是 JSON 对象。",
        }

    text = payload.get("text")
    scenario = payload.get("scenario", "auto")
    jurisdiction = payload.get("jurisdiction", "HK")
    if not isinstance(text, str):
        return 400, {
            "error": "invalid_request",
            "message": "text 必须是字符串。",
        }
    if not isinstance(scenario, str):
        return 400, {
            "error": "invalid_request",
            "message": "scenario 必须是字符串。",
        }
    if not isinstance(jurisdiction, str):
        return 400, {
            "error": "invalid_request",
            "message": "jurisdiction 必须是字符串。",
        }

    try:
        report = analyzer.analyze(
            text,
            scenario=scenario,
            jurisdiction=jurisdiction,
        )
    except (TypeError, ValueError) as error:
        return 400, {"error": "invalid_request", "message": str(error)}
    except Exception:
        return 500, {
            "error": "analysis_failed",
            "message": "分析暂时无法完成，请稍后重试。",
        }

    return 200, report.to_dict()


class WebRequestHandler(BaseHTTPRequestHandler):
    """Serve the local interface and its analysis endpoint."""

    server_version = "FuqianHechaWeb/0.1"
    analyzer = ANALYZER

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlsplit(self.path).path
        if path == "/api/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "fuqianhecha-web",
                    "analysis_api": "connected",
                },
            )
            return

        asset = _STATIC_ROUTES.get(path)
        if asset is None:
            self._send_json(404, {"error": "not_found"})
            return

        filename, content_type = asset
        try:
            content = (STATIC_ROOT / filename).read_bytes()
        except FileNotFoundError:
            self._send_json(500, {"error": "static_asset_missing"})
            return
        self._send_bytes(200, content, content_type)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        path = urlsplit(self.path).path
        if path != "/api/analyze":
            self._send_json(404, {"error": "not_found"})
            return

        content_type = self.headers.get("Content-Type", "")
        media_type = content_type.partition(";")[0].strip().lower()
        if media_type != "application/json":
            self._send_json(
                415,
                {
                    "error": "unsupported_media_type",
                    "message": "请求必须使用 application/json。",
                },
            )
            return

        content_length = self.headers.get("Content-Length")
        try:
            request_size = int(content_length or "")
        except ValueError:
            request_size = 0

        if request_size <= 0:
            self._send_json(
                400,
                {"error": "invalid_request", "message": "请求正文不能为空。"},
            )
            return
        if request_size > MAX_REQUEST_BYTES:
            self._send_json(
                413,
                {"error": "request_too_large", "message": "请求内容过大。"},
            )
            return

        raw_body = self.rfile.read(request_size)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(
                400,
                {"error": "invalid_json", "message": "请求正文不是有效 JSON。"},
            )
            return

        status, response_payload = analyze_payload(payload, self.analyzer)
        self._send_json(status, response_payload)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, content, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        for name, value in _SECURITY_HEADERS:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        """Keep the student-facing terminal concise."""

        return


def application(environ: dict[str, Any], start_response: Any) -> list[bytes]:
    """WSGI entry point used by Gunicorn in production deployments."""

    method = str(environ.get("REQUEST_METHOD", "GET")).upper()
    path = str(environ.get("PATH_INFO", "/"))
    status = 404
    content_type = "application/json; charset=utf-8"
    content = json.dumps({"error": "not_found"}).encode("utf-8")

    if method == "GET" and path == "/api/health":
        status = 200
        content = json.dumps(
            {
                "status": "ok",
                "service": "fuqianhecha-web",
                "analysis_api": "connected",
            }
        ).encode("utf-8")
    elif method == "GET" and path in _STATIC_ROUTES:
        filename, content_type = _STATIC_ROUTES[path]
        try:
            content = (STATIC_ROOT / filename).read_bytes()
            status = 200
        except FileNotFoundError:
            status = 500
            content_type = "application/json; charset=utf-8"
            content = json.dumps({"error": "static_asset_missing"}).encode("utf-8")
    elif method == "POST" and path == "/api/analyze":
        status, content = _wsgi_analysis_response(environ)
    elif method not in {"GET", "POST"}:
        status = 405
        content = json.dumps({"error": "method_not_allowed"}).encode("utf-8")

    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(content))),
        *_SECURITY_HEADERS,
    ]
    start_response(f"{status} {HTTPStatus(status).phrase}", headers)
    return [content]


def _wsgi_analysis_response(environ: dict[str, Any]) -> tuple[int, bytes]:
    """Read and validate one WSGI analysis request."""

    media_type = str(environ.get("CONTENT_TYPE", "")).partition(";")[0].strip().lower()
    if media_type != "application/json":
        return _json_response_bytes(
            415,
            "unsupported_media_type",
            "请求必须使用 application/json。",
        )

    try:
        request_size = int(str(environ.get("CONTENT_LENGTH", "")))
    except ValueError:
        request_size = 0
    if request_size <= 0:
        return _json_response_bytes(400, "invalid_request", "请求正文不能为空。")
    if request_size > MAX_REQUEST_BYTES:
        return _json_response_bytes(413, "request_too_large", "请求内容过大。")

    body_stream = environ.get("wsgi.input")
    if body_stream is None:
        return _json_response_bytes(400, "invalid_request", "请求正文不能为空。")
    raw_body = body_stream.read(request_size)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _json_response_bytes(400, "invalid_json", "请求正文不是有效 JSON。")

    status, response_payload = analyze_payload(payload)
    return status, json.dumps(response_payload, ensure_ascii=False).encode("utf-8")


def _json_response_bytes(status: int, error: str, message: str) -> tuple[int, bytes]:
    payload = {"error": error, "message": message}
    return status, json.dumps(payload, ensure_ascii=False).encode("utf-8")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    """Create the local HTTP server without starting its event loop."""

    return ThreadingHTTPServer((host, port), WebRequestHandler)


def build_parser() -> argparse.ArgumentParser:
    """Build command-line arguments for the local server."""

    parser = argparse.ArgumentParser(description="Run the FuqianHecha local web UI.")
    parser.add_argument("--host", default="127.0.0.1", help="local bind address")
    parser.add_argument("--port", type=int, default=8000, help="local port")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the local web server until interrupted."""

    args = build_parser().parse_args(argv)
    if not 0 <= args.port <= 65_535:
        raise SystemExit("port must be between 0 and 65535")

    server = create_server(args.host, args.port)
    host, port = server.server_address[:2]
    print(f"FuqianHecha web UI: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb UI stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
