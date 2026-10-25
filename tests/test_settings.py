import copy
import json
import tempfile
import unittest
from pathlib import Path

from rovo.config import DEFAULT
from rovo.core import Core
from rovo.dashboard import execute, projection


class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data = Path(self.directory.name)
        self.config = copy.deepcopy(DEFAULT)
        self.config["motion"]["calibrated"] = True
        for axis in ("pan", "tilt"):
            self.config["motion"][axis] = {
                "min": 60,
                "max": 120,
                "home": 90,
                "direction": 1,
            }
        self.core = Core(self.config, self.data)

    async def asyncTearDown(self):
        await self.core.close()
        self.directory.cleanup()

    async def test_save_reload_previous_and_no_automatic_movement(self):
        self.core.audio.speech_volume = 41
        self.core.settings.write(self.core.settings.capture(self.core))
        self.core.audio.speech_volume = 52
        self.core.settings.write(self.core.settings.capture(self.core))
        self.assertEqual(
            self.core.settings.read("previous")["audio"]["speech_volume"], 41
        )
        fresh = Core(copy.deepcopy(self.config), self.data)
        try:
            self.assertEqual(fresh.audio.speech_volume, 52)
            self.assertEqual(fresh.esp.commands, [])
        finally:
            await fresh.close()
        text = (self.data / "settings.json").read_text()
        self.assertNotIn("endpoint", text)
        self.assertNotIn("serial_port", text)

    async def test_restore_requires_confirmation_and_stops(self):
        self.core.settings.write(self.core.settings.capture(self.core))
        self.core.audio.speech_volume = 22
        result = await execute(
            self.core,
            {
                "action": "settings.restore",
                "data": {"source": "saved", "confirm": False},
            },
            "a",
        )
        self.assertFalse(result["ok"])
        result = await execute(
            self.core,
            {
                "action": "settings.restore",
                "data": {"source": "saved", "confirm": True},
            },
            "a",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(self.core.audio.speech_volume, 70)
        self.assertTrue(self.core.motion.stopped)

    async def test_display_modes_and_brightness(self):
        packet = {
            "action": "display.configure",
            "data": {"brightness": 35, "mode": "manual", "face": "HAPPY"},
        }
        self.assertTrue((await execute(self.core, packet, "a"))["ok"])
        await self.core.expressions.tick()
        self.assertEqual(self.core.expressions.last, "HAPPY")
        self.assertIn(("BRIGHTNESS", (35,)), self.core.esp.commands)
        packet["data"]["mode"] = "off"
        await execute(self.core, packet, "a")
        self.assertEqual(
            projection(self.core)["snapshot"]["runtime"]["display"][
                "applied_brightness"
            ],
            0,
        )

    async def test_limits_narrow_only_persist_and_never_move(self):
        limits = {
            axis: {"min": 70, "max": 110, "home": 90, "direction": 1}
            for axis in ("pan", "tilt")
        }
        packet = {"action": "calibration.apply", "data": {**limits, "confirm": True}}
        self.assertTrue((await execute(self.core, packet, "a"))["ok"])
        self.assertEqual(self.core.esp.commands, [("STOP", ())])
        limits["pan"]["max"] = 130
        self.assertFalse((await execute(self.core, packet, "a"))["ok"])
        fresh = Core(copy.deepcopy(self.config), self.data)
        try:
            self.assertEqual(fresh.config["motion"]["pan"]["max"], 110)
            self.assertEqual(fresh.esp.commands, [])
        finally:
            await fresh.close()

    async def test_corrupt_settings_keep_defaults_and_can_be_repaired(self):
        (self.data / "settings.json").write_text('{"schema":123}')
        fresh = Core(copy.deepcopy(self.config), self.data)
        try:
            self.assertIsNotNone(fresh.settings.error)
            self.assertEqual(fresh.audio.speech_volume, 70)
            fresh.settings.write(fresh.settings.capture(fresh))
            self.assertEqual(
                json.loads((self.data / "settings.json").read_text())["schema"], 1
            )
        finally:
            await fresh.close()
