"""Neue Sprachsteuerung ohne Netzwerk, Audioausgabe oder reale Bewegung."""

import copy
import time
import unittest
from unittest.mock import AsyncMock, patch

from rovo.audio import Audio
from rovo.config import DEFAULT
from rovo.core import Core
from rovo.esp import FakeESP32
from rovo.intents import parse
from rovo.motion import Motion
from rovo.spotify import Spotify


class VoiceControls(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        config = copy.deepcopy(DEFAULT)
        config["motion"]["calibrated"] = True
        for axis in ("pan", "tilt"):
            config["motion"][axis] = {"min": 60, "max": 120, "home": 90, "direction": 1}
        self.config = config

    def test_parameters_and_negation(self):
        for text, axis, delta in (
            ("10 Grad nach links", "pan", -10),
            ("20 Grad nach rechts", "pan", 20),
            ("3 Grad nach oben", "tilt", -3),
            ("40 Grad nach unten", "tilt", 40),
        ):
            self.assertEqual(parse(text).args, {"axis": axis, "delta": delta})
        self.assertEqual(parse("Lautstärke auf 40 Prozent").args, {"value": 40})
        self.assertEqual(parse("spiele nicht musik von ABBA").name, "negated")
        self.assertEqual(parse("10 Grad links und 20 Grad rechts").name, "clarify")
        self.assertEqual(parse("fahr nach links").name, "stationary")

    async def test_endpoint_and_tracking_return(self):
        motion = Motion(self.config, FakeESP32())
        await motion.home()
        self.assertTrue((await motion.relative("pan", 100))["limited"])
        self.assertEqual(motion.pan, 120)
        motion.manual_until = 0
        await motion.tick()
        self.assertEqual(motion.pan, 120)  # Ohne Tracking bleibt der Kopf dort.
        motion.tracking = True
        await motion.relative("pan", -10)
        self.assertGreater(motion.manual_until, time.monotonic() + 4)
        motion.manual_until = 0
        await motion.tick()
        self.assertEqual(motion.pan, 90)
        self.assertFalse(motion.return_pending)
        self.assertGreater(motion.manual_until, time.monotonic())

    async def test_stop_cancels_return(self):
        motion = Motion(self.config, FakeESP32())
        await motion.home()
        motion.tracking = True
        await motion.relative("tilt", 10)
        await motion.stop()
        await motion.tick()
        self.assertFalse(motion.return_pending)
        self.assertIsNone(motion.pan)

    async def test_profile_limits_and_failure(self):
        motion = Motion(self.config, FakeESP32())
        await motion.profile(0.5, 0.5)
        self.assertEqual(motion.speed, 10)
        await motion.profile(2, 2)
        self.assertEqual(motion.speed, 20)
        motion.esp.command = AsyncMock(side_effect=ValueError("alte Firmware"))
        with self.assertRaises(ValueError):
            await motion.profile(0.5, 0.5)
        self.assertEqual(motion.speed, 20)

    async def test_audio_bounds(self):
        audio = Audio(self.config["audio"])
        try:
            for _ in range(20):
                audio.speech_settings(10, 1.2)
            self.assertEqual(audio.speech_volume, 100)
            self.assertEqual(audio.speech_rate, 1.5)
            for _ in range(20):
                audio.speech_settings(-10, 0.8)
            self.assertEqual(audio.speech_volume, 0)
            self.assertEqual(audio.speech_rate, 0.5)
            with self.assertRaises(ValueError):
                await audio.set_volume(101)
        finally:
            await audio.close()

    async def test_spotify_explicit_device_and_search(self):
        spotify = Spotify()
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                await spotify.play("ABBA")
        spotify.request = AsyncMock(
            side_effect=[
                {
                    "tracks": {
                        "items": [
                            {
                                "uri": "spotify:track:test",
                                "name": "Test",
                                "artists": [{"name": "ABBA"}],
                            }
                        ]
                    }
                },
                {},
            ]
        )
        result = await spotify.play("ABBA")
        self.assertEqual(result["title"], "Test")
        self.assertEqual(
            spotify.request.call_args.args,
            ("PUT", "me/player/play", {"uris": ["spotify:track:test"]}),
        )

    async def test_power_confirmation_simulation_and_cancel(self):
        core = Core(self.config)
        try:
            result = await core.text("fahr herunter", "a", "1")
            self.assertEqual(result["status"], "confirmation_required")
            result = await core.text("ja", "b", "2")
            self.assertNotEqual(result["intent"], "system.shutdown")
            with patch(
                "asyncio.create_subprocess_exec", new_callable=AsyncMock
            ) as spawn:
                result = await core.text("ja", "a", "3")
                self.assertEqual(result["intent"], "system.shutdown")
                spawn.assert_not_called()
            await core.text("fahr herunter", "a", "4")
            await core.action("stop", {}, "b")
            result = await core.text("ja", "a", "5")
            self.assertNotEqual(result["intent"], "system.shutdown")
        finally:
            await core.close()
