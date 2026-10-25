"""Ausführbare Logik-/Vertragstests. Keine echte Kamera, Audioschnittstelle oder PWM."""

import copy
import tempfile
import time
import unittest
from pathlib import Path

from rovo.config import DEFAULT, load, number, save, validate
from rovo.core import Core
from rovo.esp import FakeESP32
from rovo.intents import parse
from rovo.math_de import evaluate, word_number
from rovo.motion import Motion
from rovo.storage import Store
from rovo.vision import Face, TargetSelector


def simulation_config():
    config = copy.deepcopy(DEFAULT)
    config["motion"]["calibrated"] = True
    # Ausschließlich synthetische Testgrenzen, KEINE Hardwarekalibrierung.
    for axis in ("pan", "tilt"):
        config["motion"][axis] = {"min": 60, "max": 120, "home": 90, "direction": 1}
    return config


class MathTests(unittest.TestCase):
    def test_reference_expressions(self):
        cases = {
            "5+7": 12,
            "25 mal 17": 425,
            "fünfundzwanzig mal siebzehn": 425,
            "2 plus 3 mal 4": 14,
            "(2 plus 3) mal 4": 20,
            "20 Prozent von 150": 30,
            "Wurzel aus 81": 9,
            "minus fünf plus sieben": 2,
            "eins komma fünf mal zwei": 3,
            "1,5 * 2": 3,
            "2 hoch 10": 1024,
            "2^3^2": 512,
            "-2^2": -4,
            "Was ist hundertdreiundzwanzig plus zwei?": 125,
            "15 % von 80": 12,
            "0": 0,
            "3 / 2": 1.5,
        }
        for expression, expected in cases.items():
            with self.subTest(expression=expression):
                self.assertAlmostEqual(evaluate(expression), expected)

    def test_unsafe_and_invalid_inputs(self):
        for expression in (
            "__import__('os')",
            "open('x')",
            "2**100",
            "5/0",
            "sqrt -1",
            "(" * 30 + "1" + ")" * 30,
            "1e999",
            "nan",
            "1+",
            "(1+2",
            "1 2",
            "9" * 300,
        ):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    evaluate(expression)

    def test_number_words(self):
        for word, value in {
            "dreiundzwanzig": 23,
            "neunundneunzig": 99,
            "zweihundert": 200,
            "eintausendfünf": 1005,
            "null": 0,
        }.items():
            self.assertEqual(word_number(word), value)
        self.assertIsNone(word_number("neunundhundert"))


class IntentTests(unittest.TestCase):
    def test_negation(self):
        for text in (
            "Schau nicht nach links",
            "Schalte die Kamera nicht aus",
            "Lösche nicht mein Gesicht",
            "Nicht herunterfahren",
        ):
            self.assertEqual(parse(text).name, "negated", text)
        self.assertEqual(parse("Ich möchte nicht registriert werden").name, "cancel")

    def test_explicit_stop_and_cloud_off(self):
        for text in ("Stopp", "Stoppe sofort", "Keine Bewegung mehr", "Rovo, Stopp"):
            self.assertEqual(parse(text).name, "stop")
        self.assertEqual(parse("Keine Cloud-KI verwenden").name, "llm.disable")

    def test_reference_intents(self):
        cases = {
            "Was ist 25 mal 17?": "math.evaluate",
            "Zehn Sekunden Timer": "timer.start",
            "Schau nach links": "motion.relative",
            "Noch ein Stück": "motion.repeat",
            "Verfolge mich": "tracking.enable",
            "Kennst du mich?": "people.identify",
            "Wie viel Akku hast du?": "battery.status",
            "Wie spät ist es?": "time.now",
            "Fahr vorwärts": "stationary",
            "Zeig dein normales Gesicht": "display.face",
            "Schau links und rechts": "clarify",
            "Stell einen Timer": "clarify",
        }
        for text, expected in cases.items():
            self.assertEqual(parse(text).name, expected, text)


class ConfigTests(unittest.TestCase):
    def test_invalid_numbers(self):
        for value in (True, "90", float("nan"), float("inf"), -1, 181):
            with self.assertRaises(ValueError):
                number(value, 0, 180)

    def test_incomplete_calibration(self):
        config = copy.deepcopy(DEFAULT)
        config["motion"]["calibrated"] = True
        with self.assertRaises(ValueError):
            validate(config)

    def test_save_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            save(path, simulation_config())
            self.assertEqual(load(path), simulation_config())
            path.write_text('{"unexpected":1}')
            with self.assertRaises(ValueError):
                load(path)


class StorageTests(unittest.TestCase):
    def test_persistence_and_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.sqlite3"
            store = Store(path)
            note_id = store.note("Wasser trinken")
            timer_id = store.timer(1)
            store.db.execute(
                "UPDATE timers SET due=? WHERE id=?", (time.time() - 1, timer_id)
            )
            store.db.commit()
            store.close()
            store = Store(path)
            self.assertEqual(store.notes()[0]["id"], note_id)
            self.assertEqual(store.due()[0]["id"], timer_id)
            self.assertEqual(store.due(), [])
            self.assertTrue(store.delete_note(note_id))
            self.assertFalse(store.delete_note(note_id))
            store.close()

    def test_pause_resume_cancel(self):
        store = Store()
        try:
            ident = store.timer(10)
            self.assertTrue(store.timer_action(ident, "pause"))
            self.assertEqual(store.timers()[0]["state"], "paused")
            self.assertTrue(store.timer_action(ident, "resume"))
            self.assertTrue(store.timer_action(ident, "cancel"))
            self.assertEqual(store.timers(), [])
        finally:
            store.close()


class MotionTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_locked(self):
        esp = FakeESP32()
        motion = Motion(copy.deepcopy(DEFAULT), esp)
        with self.assertRaises(ValueError):
            await motion.home()
        self.assertEqual(esp.commands, [])

    async def test_limits_stop_stale_and_reconnect(self):
        esp = FakeESP32()
        motion = Motion(simulation_config(), esp)
        await motion.home()
        await motion.relative("pan", -3)
        self.assertEqual(motion.pan, 87)
        with self.assertRaises(ValueError):
            await motion.move(200, 90)
        motion.tracking = True
        with self.assertRaises(ValueError):
            await motion.move(90, 90, "tracking", time.monotonic() - 2)
        await motion.stop()
        self.assertFalse(motion.tracking)
        self.assertIsNone(motion.pan)
        self.assertEqual(esp.commands[-1][0], "STOP")
        esp.connected = False
        self.assertFalse((await motion.stop())["hardware_acknowledged"])
        esp.connected = True
        self.assertIsNone(motion.pan)

    async def test_real_mode_needs_explicit_authorization(self):
        esp = FakeESP32()
        esp.simulated = False
        config = simulation_config()
        config["safe_mode"] = False
        with self.assertRaises(ValueError):
            await Motion(config, esp).home()

    async def test_timeout_does_not_publish_target(self):
        esp = FakeESP32()
        esp.failure = "timeout"
        motion = Motion(simulation_config(), esp)
        with self.assertRaises(TimeoutError):
            await motion.home()
        self.assertIsNone(motion.pan)


class VisionTests(unittest.TestCase):
    def test_largest_unknown_uncertain_and_hold(self):
        selector = TargetSelector()
        far = Face(1, 0.2, 0.5, 0.1, 0.1, "UNKNOWN")
        near = Face(2, 0.5, 0.5, 0.4, 0.4, "KNOWN")
        self.assertEqual(selector.choose([far, near], 0).track_id, 2)
        unknown_near = Face(3, 0.6, 0.5, 0.39, 0.4, "UNKNOWN")
        self.assertEqual(selector.choose([near, unknown_near], 0.2).track_id, 2)
        self.assertEqual(selector.choose([near, unknown_near], 2).track_id, 2)
        self.assertIsNone(selector.choose([], 3))
        uncertain = Face(4, 0.6, 0.5, 0.39, 0.4, "UNCERTAIN")
        self.assertEqual(selector.choose([near, uncertain], 4).track_id, 2)


class CoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.core = Core(copy.deepcopy(DEFAULT))

    async def asyncTearDown(self):
        await self.core.close()

    async def send(self, text, session="test"):
        return await self.core.execute(
            {"type": "text", "args": {"text": text}}, session=session
        )

    async def test_reference_flow_offline(self):
        self.assertEqual((await self.send("Was ist 25 mal 17?"))["data"]["value"], 425)
        self.assertIn("Uhr", (await self.send("Wie spät ist es?"))["spoken_reply"])
        self.assertIn(
            "nicht auslesen",
            (await self.send("Wie viel Akku hast du?"))["spoken_reply"],
        )
        self.assertIn("Richtung", (await self.send("Noch ein Stück"))["spoken_reply"])
        self.assertFalse((await self.send("Schau nach links"))["ok"])
        self.assertIsNone(self.core.status()["power"]["battery_percent"])
        self.assertEqual(self.core.llm.calls, 0)

    async def test_bad_command_cannot_invoke_unknown_tools(self):
        for command in (
            {"type": "shell", "args": {"command": "anything"}},
            {"type": "motion.set", "args": {"pan": 90, "tilt": 90, "extra": 1}},
            {"type": "display.face", "args": {"face": "HAPPY\nMOVE 0 0"}},
            {"type": "text", "args": {"text": []}},
            {"schema": "v0", "type": "stop"},
        ):
            self.assertFalse((await self.core.execute(command))["ok"])
        self.assertEqual(self.core.esp.commands, [])

    async def test_negative_commands_never_move(self):
        for sentence in (
            "Schau nicht nach links",
            "Nicht ausschalten",
            "Lösche nicht mein Gesicht",
        ):
            self.assertEqual((await self.send(sentence))["intent"], "negated")
        self.assertEqual(self.core.esp.commands, [])

    async def test_delete_confirmation_session_and_expiry(self):
        await self.send("Rovo, merk dir, dass Wasser wichtig ist")
        self.assertEqual(self.core.store.notes()[0]["text"], "Wasser wichtig ist")
        result = await self.send("Lösche meine letzte Notiz")
        self.assertEqual(result["status"], "confirmation_required")
        await self.send("Ja", session="other")
        self.assertEqual(len(self.core.store.notes()), 1)
        await self.send("Nein")
        await self.send("Ja")
        self.assertEqual(len(self.core.store.notes()), 1)
        await self.send("Lösche meine letzte Notiz")
        expiry, ident, token = self.core.pending["test"]
        self.core.pending["test"] = (time.monotonic() - 1, ident, token)
        await self.send("Ja")
        self.assertEqual(len(self.core.store.notes()), 1)
        await self.send("Lösche meine letzte Notiz")
        await self.send("Ja")
        self.assertEqual(self.core.store.notes(), [])

    async def test_privacy_and_unavailable_camera(self):
        await self.send("Aktiviere den Privatsphäre-Modus")
        self.assertTrue(self.core.privacy)
        self.assertFalse((await self.send("Aktiviere deine Kamera"))["ok"])
        self.assertIsNone(self.core.camera.status()["face_count"])

    async def test_multiple_timers_require_selection(self):
        await self.send("Timer auf zehn Sekunden")
        await self.send("Timer auf fünf Minuten")
        self.assertIn(
            "eindeutig", (await self.send("Stoppe den Timer"))["spoken_reply"]
        )
        self.assertEqual(len(self.core.store.timers()), 2)


if __name__ == "__main__":
    unittest.main()
