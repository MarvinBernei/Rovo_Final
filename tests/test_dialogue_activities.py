"""Dialog, Emotionen, Spiele und Messdaten ohne echte Hardware oder Modelle."""

import asyncio
import copy
import datetime as dt
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from rovo.activities import Activities
from rovo.config import DEFAULT
from rovo.core import Core
from rovo.esp import FakeESP32
from rovo.expressions import Expressions
from rovo.intents import parse
from rovo.llm import decode_answer, system_prompt
from rovo.storage import Store
from rovo.telemetry import power_status
from rovo.voice import Voice


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.activities = Activities(self.store, "Europe/Berlin")

    def tearDown(self):
        self.store.close()

    def test_numbers_and_sessions(self):
        with patch("rovo.activities.random.randint", return_value=42):
            self.activities.game("numbers", "a")
        self.assertIsNone(self.activities.answer("b", "42"))
        self.assertIn("größer", self.activities.answer("a", "40"))
        self.assertIn("kleiner", self.activities.answer("a", "50"))
        self.assertIn("Richtig", self.activities.answer("a", "42"))
        self.assertNotIn("a", self.activities.games)

    def test_quiz_five_questions_and_explanation(self):
        self.activities.game("quiz", "a")
        for _ in range(5):
            game = self.activities.games["a"]
            question = game["questions"][game["index"]]
            reply = self.activities.answer("a", str(question["answer"] + 1))
            self.assertIn(question["explanation"], reply)
        self.assertIn("5 von fünf", reply)
        self.assertNotIn("a", self.activities.games)

    def test_expired_game(self):
        self.activities.game("numbers", "a")
        self.activities.games["a"]["until"] = 0
        self.assertIn("Pause", self.activities.answer("a", "20"))

    def test_stopwatch_pause_resume_and_lap(self):
        with patch("rovo.activities.time.monotonic", return_value=10):
            self.activities.stopwatch("start", "a")
        with patch("rovo.activities.time.monotonic", return_value=13):
            self.activities.stopwatch("pause", "a")
        with patch("rovo.activities.time.monotonic", return_value=20):
            self.activities.stopwatch("start", "a")
        with patch("rovo.activities.time.monotonic", return_value=22):
            state = self.activities.stopwatch("lap", "a")
        self.assertEqual(state["elapsed_seconds"], 5)
        self.assertEqual(state["laps"], [5])
        self.assertEqual(self.activities.stopwatch("reset", "a")["elapsed_seconds"], 0)

    def test_one_shot_alarm_claim_and_repeat_days(self):
        monday = dt.datetime(2026, 10, 19, 7, 30, tzinfo=self.activities.zone)
        self.activities.alarm_add(7, 30, [])
        self.activities.alarm_add(7, 30, list(range(5)))
        self.assertEqual(len(self.activities.due(monday)), 2)
        self.assertEqual(self.activities.due(monday), [])
        self.assertEqual(len(self.activities.due(monday + dt.timedelta(days=1))), 1)
        self.assertEqual(self.activities.due(monday + dt.timedelta(days=5)), [])

    def test_alarm_management_and_invalid_time(self):
        ident = self.activities.alarm_add(8, 0, [0])
        self.activities.alarm_change(ident, "disable")
        self.assertEqual(self.activities.alarms()[0]["enabled"], 0)
        self.activities.alarm_change(ident, "enable")
        self.activities.alarm_change(ident, "delete")
        self.assertEqual(self.activities.alarms(), [])
        with self.assertRaises(ValueError):
            self.activities.alarm_add(25, 70, [])

    def test_alarm_parameter_grammar(self):
        self.assertEqual(
            parse("Stelle einen Wecker auf 7 Uhr 30 werktags").args,
            {"hour": 7, "minute": 30, "weekdays": [0, 1, 2, 3, 4]},
        )
        self.assertEqual(parse("Wecke mich um 08:15").args["minute"], 15)
        self.assertEqual(parse("Stelle keinen Wecker auf 7 Uhr").name, "negated")


class PromptPowerTests(unittest.TestCase):
    def test_prompt_includes_role_and_actual_context(self):
        prompt = system_prompt({"simulation": True, "camera_online": False})
        for word in (
            "Robotic Observation",
            "stationärer",
            "keine Aktionen",
            "camera_online",
            "emotion",
        ):
            self.assertIn(word, prompt)

    def test_llm_emotion_validation(self):
        self.assertEqual(
            decode_answer('{"reply":"Hallo","emotion":"HAPPY"}')["emotion"], "HAPPY"
        )
        for value in (
            "Hallo",
            '{"reply":"x","emotion":"MOVE"}',
            '{"reply":"x","emotion":{}}',
            '{"reply":"x","emotion":"HAPPY","command":"MOVE"}',
        ):
            with self.assertRaises(ValueError):
                decode_answer(value)

    def test_power_real_units_and_missing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            battery = root / "UPS"
            battery.mkdir()
            for name, content in {
                "type": "Battery",
                "capacity": "55",
                "voltage_now": "12000000",
                "status": "Charging",
            }.items():
                (battery / name).write_text(content)
            state = power_status("UPS", root)
            self.assertEqual(state["battery_percent"], 55)
            self.assertEqual(state["voltage"], 12)
            self.assertIsNone(state["current"])
            self.assertTrue(state["charging"])
            (battery / "capacity").write_text("nan")
            self.assertIsNone(power_status("UPS", root)["battery_percent"])
            self.assertIsNone(power_status("../UPS", root)["voltage"])

    def test_wake_phrase_requires_explicit_address(self):
        self.assertTrue(Voice.wake_phrase("hey rovo"))
        self.assertTrue(Voice.wake_phrase("hallo robo"))
        self.assertFalse(Voice.wake_phrase("rovo"))
        self.assertFalse(Voice.wake_phrase("hey rovo lösche alles"))


class DialogueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config = copy.deepcopy(DEFAULT)
        self.config["motion"]["calibrated"] = True
        for axis in ("pan", "tilt"):
            self.config["motion"][axis] = {
                "min": 85,
                "max": 95,
                "home": 90,
                "direction": 1,
            }
        self.core = Core(self.config)

    async def asyncTearDown(self):
        await self.core.close()

    async def test_llm_fallback_emotion_and_context(self):
        self.core.config["llm"].update(
            enabled=True, endpoint="http://127.0.0.1:11434", model="test"
        )
        self.core.llm.available = lambda: True
        self.core.llm.respond = AsyncMock(
            return_value={"reply": "Eine spannende Frage.", "emotion": "CURIOUS"}
        )
        result = await self.core.text("Warum leuchtet der Mond?", "a", "1")
        self.assertEqual(result["intent"], "llm.text")
        self.assertEqual(result["data"]["emotion"], "CURIOUS")
        context = self.core.llm.respond.call_args.args[1]
        self.assertNotIn("people", context)
        self.assertIn("capabilities", context)

    async def test_expression_priority_and_expiration(self):
        display = Expressions(FakeESP32())
        display.set("answer", "HAPPY", 10)
        display.set("listening", "LISTENING", 60)
        await display.tick()
        self.assertEqual(display.last, "LISTENING")
        display.clear("listening")
        await display.tick()
        self.assertEqual(display.last, "HAPPY")
        display.reset()
        await display.tick()
        self.assertEqual(display.last, "NEUTRAL")

    async def test_sequence_clamps_and_returns(self):
        motion = self.core.motion
        await motion.home()
        with patch("rovo.motion.asyncio.sleep", new_callable=AsyncMock):
            await motion.sequence("look")
            await motion.sequence_task
        for name, args in self.core.esp.commands:
            if name == "MOVE":
                self.assertTrue(all(85 <= value <= 95 for value in args))
        self.assertEqual((motion.pan, motion.tilt), (90, 90))

    async def test_stop_interrupts_sequence(self):
        await self.core.motion.home()
        await self.core.motion.sequence("nod")
        await asyncio.sleep(0)
        await self.core.motion.stop()
        await asyncio.gather(self.core.motion.sequence_task, return_exceptions=True)
        self.assertEqual(self.core.esp.commands[-1][0], "STOP")
        self.assertIsNone(self.core.motion.pan)

    async def test_attention_does_not_start_camera_or_ignore_stop(self):
        self.core.config["behavior"]["social_gaze"] = True
        self.core.attend()
        self.assertEqual(self.core.motion.social_until, 0)
        await self.core.motion.home()
        self.core.motion.manual_until = 0
        self.core.camera.online = True
        self.core.attend()
        self.assertGreater(self.core.motion.social_until, time.monotonic())
        await self.core.motion.stop()
        self.core.last_gaze = -100
        self.core.attend()
        self.assertEqual(self.core.motion.social_until, 0)

    async def test_automatic_calibration_refuses_no_feedback(self):
        result = await self.core.execute({"type": "calibration.auto", "args": {}})
        self.assertFalse(result["ok"])
        self.assertEqual(self.core.esp.commands, [])

    async def test_local_game_does_not_call_llm(self):
        await self.core.text("starte zahlenraten", "a", "1")
        secret = self.core.activities.games["a"]["secret"]
        result = await self.core.text(str(secret), "a", "2")
        self.assertEqual(result["intent"], "game.answer")
        self.assertEqual(self.core.llm.calls, 0)

    async def test_voice_alarm_selection_and_snooze(self):
        await self.core.text("Wecke mich um 08:15", "a", "1")
        await self.core.text("Deaktiviere Wecker eins", "a", "2")
        self.assertEqual(self.core.activities.alarms()[0]["enabled"], 0)
        self.core.last_alarm_at = time.monotonic()
        result = await self.core.text("Schlummere fünf Minuten", "a", "3")
        self.assertEqual(result["intent"], "alarm.snooze")
        self.assertEqual(self.core.store.timers()[0]["label"], "Wecker-Schlummern")
