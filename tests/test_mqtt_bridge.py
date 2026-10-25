import copy
import time
import unittest
from unittest.mock import Mock, patch

from rovo.config import DEFAULT
from rovo.core import Core
from rovo.mqtt_bridge import MQTTBridge


class MQTTTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.core = Core(copy.deepcopy(DEFAULT))
        self.bridge = MQTTBridge(self.core, DEFAULT["mqtt"])
        self.bridge.client = Mock()
        self.bridge.connected = True

    async def asyncTearDown(self):
        await self.core.close()

    def command(self, **changes):
        return {
            "id": "test_1",
            "boot_id": self.bridge.boot_id,
            "session": "client_1",
            "issued_at": time.time(),
            "action": "chat.send",
            "data": {"text": "Hallo"},
            **changes,
        }

    async def test_request_response_and_duplicate_suppression(self):
        value = self.command()
        with patch.object(self.core, "background_speech"):
            await self.bridge.handle(value)
            await self.bridge.handle(value)
        self.assertEqual(self.bridge.client.publish.call_count, 1)
        args = self.bridge.client.publish.call_args
        self.assertEqual(args.args[0], "rovo/v1/reply")
        self.assertFalse(args.kwargs["retain"])

    async def test_retained_expired_wrong_generation_and_invalid_rejected(self):
        for value, retained in (
            (self.command(), True),
            (self.command(issued_at=0), False),
            (self.command(boot_id="old"), False),
            (self.command(session="bad/session"), False),
            ({}, False),
        ):
            await self.bridge.handle(value, retained)
        self.bridge.client.publish.assert_not_called()

    async def test_reconnect_invalidates_old_commands(self):
        value = self.command()
        self.bridge.on_connected()
        self.bridge.client.publish.reset_mock()
        await self.bridge.handle(value)
        self.bridge.client.publish.assert_not_called()

    async def test_status_does_not_send_image_bytes(self):
        from rovo.dashboard import projection

        self.core.camera.jpeg = b"private-image"
        import json

        self.assertNotIn("private-image", json.dumps(projection(self.core)["snapshot"]))

    async def test_camera_http_privacy_and_token(self):
        import asyncio
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        from rovo.api import start_server

        self.core.config["api"]["port"] = 0
        with patch.dict("os.environ", {"ROVO_API_TOKEN": "x" * 40}):
            server = start_server(self.core, asyncio.get_running_loop())
        task = asyncio.create_task(asyncio.to_thread(server.serve_forever, 0.05))
        self.core.camera.online = True
        self.core.camera.updated = time.monotonic()
        self.core.camera.jpeg = b"test-jpeg"
        url = f"http://127.0.0.1:{server.server_port}/api/v1/camera.jpg"

        def fetch(auth=True):
            request = Request(
                url, headers={"Authorization": "Bearer " + "x" * 40} if auth else {}
            )
            with urlopen(request, timeout=2) as response:
                return response.read()

        try:
            self.assertEqual(await asyncio.to_thread(fetch), b"test-jpeg")
            with self.assertRaises(HTTPError) as error:
                await asyncio.to_thread(fetch, False)
            self.assertEqual(error.exception.code, 401)
            error.exception.close()
            self.core.privacy = True
            with self.assertRaises(HTTPError) as error:
                await asyncio.to_thread(fetch)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()
        finally:
            await asyncio.to_thread(server.shutdown)
            await task
            server.server_close()
