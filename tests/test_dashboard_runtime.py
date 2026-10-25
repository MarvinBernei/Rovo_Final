import copy
import json
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from rovo.application.contracts import COMMAND_ARGUMENTS
from rovo.config import DEFAULT
from rovo.core import Core
from rovo.dashboard import RUNTIME_ACTIONS, execute, projection
from rovo.mqtt_bridge import MQTTBridge


class RuntimeExchangeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.core = Core(copy.deepcopy(DEFAULT))

    async def asyncTearDown(self):
        await self.core.close()

    async def test_periodic_snapshot_contains_actual_values(self):
        self.core.audio.speech_volume = 42
        self.core.audio.speech_rate = 0.8
        self.core.motion.pan = 93
        self.core.wakeword_online = True
        await execute(
            self.core, {"action": "display.emotion", "data": {"emotion": "happy"}}, "a"
        )
        await self.core.expressions.tick()
        snapshot = projection(self.core)["snapshot"]
        self.assertEqual(snapshot["runtime"]["audio"]["speech_volume_percent"], 42)
        self.assertEqual(snapshot["runtime"]["motion"]["pan_target_deg"], 93)
        self.assertTrue(snapshot["runtime"]["audio"]["wakeword_online"])
        self.assertEqual(snapshot["config"]["display"]["emotion"], "happy")
        self.assertTrue(snapshot["tele"]["system"]["hostname"])

    async def test_audio_update_and_invalid_input_is_atomic(self):
        packet = {
            "action": "audio.configure",
            "data": {"speech_volume": 55, "speech_rate": 1.2, "music_volume": 40},
        }
        result = await execute(self.core, packet, "a")
        self.assertTrue(result["ok"])
        self.assertEqual(result["snapshot"]["runtime"]["audio"]["speech_rate"], 1.2)
        packet["data"]["speech_volume"] = 101
        result = await execute(self.core, packet, "a")
        self.assertFalse(result["ok"])
        self.assertEqual(self.core.audio.speech_volume, 55)

    async def test_motion_configuration_keeps_motion_safety(self):
        packet = {
            "action": "motion.configure",
            "data": {"speed": 10, "acceleration": 20},
        }
        self.assertFalse((await execute(self.core, packet, "a"))["ok"])
        self.core.config["motion"]["calibrated"] = True
        result = await execute(self.core, packet, "a")
        self.assertTrue(result["ok"])
        self.assertEqual(self.core.esp.commands, [("PROFILE", (10.0, 20.0))])
        self.assertEqual(
            result["snapshot"]["runtime"]["motion"]["speed_limit_deg_s"], 10
        )

    async def test_camera_update_and_spotify_configuration_state(self):
        result = await execute(
            self.core,
            {"action": "camera.configure", "data": {"deadzone": 0.2, "gain": 1.5}},
            "a",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["snapshot"]["runtime"]["camera"]["deadzone"], 0.2)
        self.assertFalse(self.core.camera.online)
        from unittest.mock import patch

        with patch.dict(
            "os.environ",
            {"ROVO_SPOTIFY_ACCESS_TOKEN": "test", "ROVO_SPOTIFY_DEVICE_ID": "device"},
        ):
            status = projection(self.core)["status"]["spotify"]
            self.assertTrue(status["configured"])
            self.assertFalse(status["verified"])

    async def test_mqtt_request_roundtrip_updates_runtime(self):
        bridge = MQTTBridge(self.core, DEFAULT["mqtt"])
        bridge.client, bridge.connected = Mock(), True
        await bridge.handle(
            {
                "id": "audio1",
                "boot_id": bridge.boot_id,
                "session": "a",
                "issued_at": time.time(),
                "action": "audio.configure",
                "data": {"speech_volume": 38, "speech_rate": 0.9, "music_volume": 20},
            }
        )
        packet = json.loads(bridge.client.publish.call_args.args[1])
        self.assertEqual(packet["id"], "audio1")
        self.assertEqual(
            packet["result"]["snapshot"]["runtime"]["audio"]["speech_volume_percent"],
            38,
        )

    def test_all_runtime_actions_are_allowed_on_both_sides(self):
        source = (
            Path(__file__).resolve().parents[1] / "nodered/mqtt_prepare.js"
        ).read_text(encoding="utf-8")
        for action in RUNTIME_ACTIONS:
            with self.subTest(action=action):
                self.assertIn(action, COMMAND_ARGUMENTS)
                self.assertIn("'" + action + "'", source)
