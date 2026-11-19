#!/usr/bin/env python3
"""Run the exact Vercel payload locally.

Vercel serves `public/` as static files and `api/index.py` as a Python
function. This script does both on one port so the deployed behaviour can be
smoke-tested with curl before pushing:

    python scripts/vercel_dev.py            # http://0.0.0.0:8000
    PORT=8080 python scripts/vercel_dev.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(ROOT, "public")
for path in (ROOT, os.path.join(ROOT, "api")):
    if path not in sys.path:
        sys.path.insert(0, path)

import index as fn  # noqa: E402  (the deployed function module)


class DevHandler(SimpleHTTPRequestHandler):
    server_version = "GROKSCALP-dev"
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC, **kwargs)

    # -- API ---------------------------------------------------------------
    def _send(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(raw)

    def _api(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        try:
            status, payload = fn.dispatch(method, self.path, body)
        except Exception as exc:  # pragma: no cover - defensive
            status, payload = 500, {"error": f"{type(exc).__name__}: {exc}"}
        self._send(status, payload)

    def do_GET(self):  # noqa: N802
        if urlparse(self.path).path.startswith("/api"):
            return self._api("GET")
        return super().do_GET()

    def do_HEAD(self):  # noqa: N802
        if urlparse(self.path).path.startswith("/api"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            return None
        return super().do_HEAD()

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path.startswith("/api"):
            return self._api("POST")
        self.send_error(405, "POST only on /api")

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):  # keep the log terse and flushable
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))
        sys.stderr.flush()


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), DevHandler)
    print(f"GROK SCALP dev server → http://0.0.0.0:{port}  (static: {PUBLIC})", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
