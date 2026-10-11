"""Dependency-free HTTP API and dashboard server."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .simulation import SortingLine

STATIC_DIR = Path(__file__).parent / "static"


def make_handler(line: SortingLine) -> type[BaseHTTPRequestHandler]:
    state_lock = threading.RLock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "SorterLab/0.1"

        def _json(self, status: int, body: object) -> None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route == "/api/state":
                with state_lock:
                    state = line.snapshot()
                self._json(200, state)
            elif route == "/api/tick":
                with state_lock:
                    state = line.step(5)
                self._json(200, state)
            elif route == "/":
                page = (STATIC_DIR / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 4096:
                    self._json(413, {"error": "request too large"})
                    return
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError("request body must be a JSON object")
                if route == "/api/action":
                    action = body.get("action")
                    if not isinstance(action, str):
                        raise ValueError("action must be a string")
                    enabled = body.get("enabled")
                    if enabled is not None and not isinstance(enabled, bool):
                        raise ValueError("enabled must be a boolean")
                    with state_lock:
                        line.command(action, enabled)
                        state = line.snapshot()
                    self._json(200, state)
                elif route == "/api/reset":
                    seed = body.get("seed", line.seed)
                    if not isinstance(seed, int) or isinstance(seed, bool):
                        raise ValueError("seed must be an integer")
                    replacement = SortingLine(seed=seed)
                    with state_lock:
                        line.__dict__.update(replacement.__dict__)
                        state = line.snapshot()
                    self._json(200, state)
                else:
                    self._json(404, {"error": "not found"})
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

        def log_message(self, fmt: str, *args: object) -> None:
            print(f"[{self.log_date_time_string()}] {fmt % args}")

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765, seed: int = 7) -> None:
    line = SortingLine(seed=seed)
    server = ThreadingHTTPServer((host, port), make_handler(line))
    print(f"Sorter Lab running at http://{host}:{port} (seed={seed})")
    print("Press Ctrl+C to stop. This simulator is for education, not safety control.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Sorter Lab...")
    finally:
        server.server_close()
