"""Kleine lokale HTTP-Bridge mit Bearer-Token und gemeinsamem Core-Eventloop.

Kein Browser-CORS und kein direkter LAN-Listener. Node-RED setzt das Token serverseitig.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def start_server(core, loop: asyncio.AbstractEventLoop) -> ThreadingHTTPServer:
    token = os.environ.get("ROVO_API_TOKEN", "")
    if len(token) < 32:
        raise ValueError("ROVO_API_TOKEN muss mindestens 32 Zeichen enthalten.")

    class Handler(BaseHTTPRequestHandler):
        server_version = "ROVO/1"
        protocol_version = "HTTP/1.0"

        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args) -> None:
            pass  # Keine Texte, Header oder Zugangsdaten protokollieren.

        def reply(
            self, status: int, value, mime: str = "application/json; charset=utf-8"
        ) -> None:
            body = (
                value
                if isinstance(value, bytes)
                else json.dumps(value, ensure_ascii=False, allow_nan=False).encode(
                    "utf-8"
                )
            )
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self) -> bool:
            valid = hmac.compare_digest(
                self.headers.get("Authorization", "").encode(),
                ("Bearer " + token).encode(),
            )
            # Keine Browser-Anfragen von fremden Origins, auch mit lokal erreichbarem Port.
            valid = valid and not self.headers.get("Origin")
            if not valid:
                self.reply(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return valid

        def call(self, coroutine):
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
            try:
                return future.result(timeout=25)
            except TimeoutError:
                future.cancel()
                raise

        def do_GET(self) -> None:
            if not self.authorized():
                return

            async def snapshot():
                if self.path == "/api/v1/status":
                    return core.status()
                if self.path == "/api/v1/events":
                    return {"events": core.event_queue.copy()}
                if self.path == "/api/v1/camera.jpg":
                    if (
                        not core.privacy
                        and core.camera.online
                        and core.camera.status()["frame_age_s"] is not None
                        and core.camera.status()["frame_age_s"] < 1
                    ):
                        return core.camera.jpeg
                    return None
                return None

            try:
                value = self.call(snapshot())
                if value is None:
                    self.reply(404, {"error": "not_found_or_unavailable"})
                else:
                    self.reply(
                        200,
                        value,
                        "image/jpeg"
                        if isinstance(value, bytes)
                        else "application/json; charset=utf-8",
                    )
            except (OSError, TimeoutError, ValueError):
                self.reply(503, {"error": "unavailable"})

        def do_POST(self) -> None:
            if not self.authorized():
                return
            if self.path not in {"/api/v1/command", "/rpc"}:
                self.reply(404, {"error": "not_found"})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.reply(415, {"error": "json_required"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 16384:
                    self.reply(413, {"error": "invalid_size"})
                    return
                command = json.loads(self.rfile.read(length))
                session = self.headers.get("X-ROVO-Session", "dashboard")
                if not 1 <= len(session) <= 128 or not session.isascii():
                    raise ValueError("Ungültige Sitzung.")
                if self.path == "/rpc":
                    from .dashboard import execute as execute_dashboard

                    result = self.call(
                        execute_dashboard(core, command, session=session)
                    )
                else:
                    result = self.call(core.execute(command, session=session))
                self.reply(200 if result["ok"] else 422, result)
            except (ValueError, UnicodeError):
                self.reply(400, {"error": "invalid_json"})
            except (OSError, TimeoutError):
                self.reply(503, {"error": "unavailable"})

    server = ThreadingHTTPServer(
        (core.config["api"]["host"], core.config["api"]["port"]), Handler
    )
    server.daemon_threads = True
    return server
