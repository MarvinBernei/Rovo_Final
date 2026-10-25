"""V5-Vertrag gegen den echten Core mit FakeESP32, ohne Gerätezustart."""

import copy
import unittest

from rovo.config import DEFAULT
from rovo.core import Core
from rovo.dashboard import execute, projection


class V5Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.core = Core(copy.deepcopy(DEFAULT))

    async def asyncTearDown(self):
        await self.core.close()

    async def rpc(self, action, data=None):
        return await execute(
            self.core, {"action": action, "data": data or {}}, "v5-test"
        )

    async def test_status_does_not_turn_simulator_into_hardware(self):
        result = await self.rpc("status")
        self.assertTrue(result["ok"])
        self.assertTrue(result["snapshot"]["bridge"]["simulation"])
        self.assertIsNone(result["snapshot"]["tele"]["esp32"]["connected"])
        self.assertIsNone(result["snapshot"]["tele"]["battery"]["percent"])
        self.assertFalse(result["status"]["llm"]["verified"])
        self.assertIsNone(result["status"]["llm"]["provider"])

    async def test_config_reads_only_actual_core_values(self):
        result = await self.rpc("config.read")
        motion = result["config"]["motion"]
        self.assertFalse(motion["enabled"])
        self.assertIsNone(motion["homePan"])
        self.assertIsNone(motion["panMin"])
        self.assertIsNone(motion["speed"])

    async def test_chat_uses_local_router(self):
        result = await self.rpc("chat.send", {"text": "Was ist 25 mal 17?"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["data"]["value"], 425)
        self.assertIn("425", result["reply"])
        self.assertEqual(self.core.llm.calls, 0)

    async def test_move_does_not_accept_ui_test_limits(self):
        result = await self.rpc("motion.set", {"pan": 75, "tilt": 90})
        self.assertFalse(result["ok"])
        self.assertEqual(self.core.esp.commands, [])
        result = await self.rpc("motion.set", {"pan": 75, "tilt": 90, "speed": 65})
        self.assertFalse(result["ok"])

    async def test_stop_uses_shared_manager(self):
        result = await self.rpc("motion.stop")
        self.assertTrue(result["ok"])
        self.assertEqual(self.core.esp.commands[-1][0], "STOP")
        self.assertFalse(self.core.motion.tracking)

    async def test_emotion_maps_to_firmware_face(self):
        result = await self.rpc("display.emotion", {"emotion": "happy"})
        self.assertTrue(result["ok"])
        self.assertEqual(self.core.esp.commands[-1], ("FACE", ("HAPPY",)))
        self.assertEqual(result["result"]["status"], "acknowledged")
        rejected = await self.rpc("display.emotion", {"emotion": "HAPPY\nMOVE 0 0"})
        self.assertFalse(rejected["ok"])

    async def test_admin_features_never_change_config(self):
        before = copy.deepcopy(self.core.config)
        for action in (
            "config.update",
            "config.reset",
            "llm.save",
            "people.delete",
            "spotify.save",
        ):
            with self.subTest(action=action):
                result = await self.rpc(
                    action, {"apiKey": "PRIVATE_TEST", "confirmLimits": True}
                )
                self.assertFalse(result["ok"])
                self.assertNotIn("PRIVATE_TEST", str(result))
        self.assertEqual(self.core.config, before)
        self.assertEqual(self.core.esp.commands, [])

    async def test_projection_contains_no_private_endpoints(self):
        self.core.config["llm"]["endpoint"] = "http://192.168.1.123:11434"
        self.core.config["audio"]["voice"] = "/private/path/voice.onnx"
        self.assertNotIn("192.168.1.123", str(projection(self.core)))
        self.assertNotIn("/private/path", str(projection(self.core)))

    async def test_no_fake_audio_test_or_wakeword(self):
        self.assertFalse((await self.rpc("audio.test"))["ok"])
        self.assertFalse((await self.rpc("audio.listen"))["ok"])

    async def test_offline_nano_stop_is_partial(self):
        self.core.esp.connected = False
        result = await self.rpc("motion.stop")
        self.assertEqual(result["result"]["status"], "partial")
        self.assertFalse(result["result"]["data"]["hardware_acknowledged"])

    async def test_privacy_and_missing_camera_report_failure(self):
        await self.rpc("privacy.enable")
        self.assertFalse((await self.rpc("camera.enable"))["ok"])
        self.assertFalse((await self.rpc("tracking.start"))["ok"])

    async def test_bad_packets_rejected(self):
        for packet in (
            {"action": "status", "extra": True},
            {"action": []},
            {"action": "status", "data": {"not": "empty"}},
            {"action": "motion.stop", "data": []},
        ):
            self.assertFalse((await execute(self.core, packet, "test"))["ok"])
        self.assertEqual(self.core.esp.commands, [])


if __name__ == "__main__":
    unittest.main()
