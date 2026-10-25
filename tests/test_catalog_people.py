"""Katalog, Einwilligung, lokale Profile und Zielauswahl ohne Kamerazugriff."""

import copy
import datetime as dt
import json
import tempfile
import time
import unittest
from pathlib import Path

from rovo.catalog import entries, match
from rovo.config import DEFAULT
from rovo.core import Core
from rovo.intents import parse
from rovo.people import POSES, Observation, unit
from rovo.vision import Face, TargetSelector


class CatalogTests(unittest.TestCase):
    def test_every_catalog_phrase_is_routed(self):
        self.assertGreaterEqual(sum(len(e["phrases"]) for e in entries()), 400)
        for entry in entries():
            for phrase in entry["phrases"]:
                phrase = (
                    phrase.replace("{name}", "Max Müller")
                    .replace("{fact}", "Ich baue Modellautos")
                    .replace("{topic}", "Modellbau")
                    .replace("{query}", "Dancing Queen von ABBA")
                )
                with self.subTest(phrase=phrase):
                    self.assertEqual(parse(phrase).name, entry["intent"])

    def test_synonyms_and_preserved_name(self):
        for phrase in (
            "Schau mich an",
            "Sieh zu mir",
            "Guck mal zu mir",
            "Bitte folge mir",
        ):
            self.assertEqual(parse(phrase).name, "tracking.enable")
        self.assertEqual(parse("Rovo, ich heiße Max Müller").args["name"], "Max Müller")

    def test_negation_is_not_fuzzy_execution(self):
        for phrase in (
            "schau nicht nach links",
            "schalte die kamera nicht aus",
            "speichere nicht mein gesicht",
        ):
            self.assertEqual(parse(phrase).name, "negated")
        self.assertEqual(parse("verfolge mich nicht mehr").name, "tracking.disable")
        self.assertEqual(parse("beweg dich nicht").name, "stop")
        self.assertIsNone(match("schu mich ann"))


class PeopleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        config = copy.deepcopy(DEFAULT)
        config["people"].update(recognition_verified=True, samples_per_pose=5)
        self.core = Core(config)
        self.people = self.core.people
        self.events = []
        self.people.emit = lambda text, kind: self.events.append((kind, text))
        self.people.activate("test-model")

    async def asyncTearDown(self):
        await self.core.close()

    def observation(self, track=1, vector=(1.0, 0.0, 0.0), **kwargs):
        return Observation(track, unit(vector), time.monotonic(), **kwargs)

    def target(self):
        obs = self.observation()
        self.people.observations = {1: obs}
        self.people.identities = {1: ("UNKNOWN", None)}
        self.people.target_id = 1
        return obs

    def fixture_profile(self, ident="person-A", name="Max", vector=(1.0, 0.0, 0.0)):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        with self.people.db:
            self.people.db.execute(
                "INSERT INTO persons(id,name,model_id,consent_at,store_images,created_at) VALUES(?,?,?,?,?,?)",
                (ident, name, "test-model", now, 0, now),
            )
            self.people.db.execute(
                "INSERT INTO face_samples VALUES(?,?,?,?)",
                (ident, "front", json.dumps(unit(vector)), None),
            )
        self.people.reload()
        return ident

    async def test_no_capture_before_consent(self):
        self.target()
        request = self.people.request("Max", "session-A", True)
        self.assertEqual(self.people.job["state"], "WAIT_CONSENT")
        self.assertEqual(self.people.profiles(), [])
        self.assertIsNone(
            self.people.db.execute("SELECT image FROM face_samples").fetchone()
        )
        with self.assertRaises(ValueError):
            self.people.consent("session-B", request["confirmation_token"], True)
        self.people.consent("session-A", request["confirmation_token"], False)
        self.assertIsNone(self.people.job)
        self.assertEqual(self.people.profiles(), [])

    async def test_expired_confirmation_and_target_change(self):
        self.target()
        request = self.people.request("Max", "A")
        self.people.job["deadline"] = time.monotonic() - 1
        with self.assertRaises(ValueError):
            self.people.consent("A", request["confirmation_token"], True)
        self.people.cancel()
        self.target()
        request = self.people.request("Max", "A")
        self.people.observations = {2: self.observation(track=2)}
        with self.assertRaises(ValueError):
            self.people.consent("A", request["confirmation_token"], True)
        self.assertEqual(self.people.profiles(), [])

    async def test_multiple_faces_cannot_be_enrolled(self):
        self.target()
        self.people.observations[2] = self.observation(track=2)
        with self.assertRaises(ValueError):
            self.people.request("Max", "A")

    async def test_guided_commit_all_five_poses_and_optional_images(self):
        self.target()
        request = self.people.request("Max", "A", True)
        self.people.consent("A", request["confirmation_token"], True)
        clock = time.monotonic()
        index = 0
        for pose in POSES:
            for _ in range(5):
                index += 1
                yaw = 0.2 if pose == "left" else -0.2 if pose == "right" else 0.0
                pitch = 0.3 if pose == "up" else 0.6 if pose == "down" else 0.45
                fingerprint = (1 << index) | (1 << (index + 1))
                self.people.observations = {
                    1: self.observation(
                        yaw=yaw,
                        pitch=pitch,
                        image=b"test-crop",
                        fingerprint=fingerprint,
                    )
                }
                self.people._capture(clock + index * 0.4)
        self.assertIsNone(self.people.job)
        profile = self.people.profiles()[0]
        self.assertEqual(profile["name"], "Max")
        self.assertEqual(profile["sample_count"], 25)
        self.assertEqual(profile["image_count"], 25)
        self.assertEqual(
            {
                row[0]
                for row in self.people.db.execute(
                    "SELECT DISTINCT pose FROM face_samples"
                )
            },
            set(POSES),
        )
        self.assertTrue(any(kind == "people.enrolled" for kind, _ in self.events))

    async def test_bad_quality_and_repeated_images_not_collected(self):
        self.target()
        request = self.people.request("Max", "A")
        self.people.consent("A", request["confirmation_token"], True)
        clock = time.monotonic()
        self.people.observations = {1: self.observation(sharpness=1)}
        self.people._capture(clock + 1)
        self.assertEqual(self.people.job["samples"], [])
        self.people.observations = {1: self.observation(fingerprint=3)}
        self.people._capture(clock + 2)
        self.people.observations = {1: self.observation(fingerprint=3)}
        self.people._capture(clock + 3)
        self.assertEqual(len(self.people.job["samples"]), 1)
        self.assertIsNone(self.people.job["samples"][0][2])

    async def test_foreign_face_cancels_capture(self):
        self.target()
        request = self.people.request("Max", "A")
        self.people.consent("A", request["confirmation_token"], True)
        self.people.observations = {1: self.observation(vector=(0.0, 1.0, 0.0))}
        self.people._capture(time.monotonic())
        self.assertIsNone(self.people.job)
        self.assertEqual(self.people.profiles(), [])

    async def test_duplicate_profile_is_not_committed(self):
        self.fixture_profile()
        self.target()
        request = self.people.request("Max nochmal", "A")
        self.people.consent("A", request["confirmation_token"], True)
        self.people.job["samples"] = [
            (pose, unit((1.0, 0.0, 0.0)), None) for pose in POSES for _ in range(5)
        ]
        self.people._commit()
        self.assertEqual(len(self.people.profiles()), 1)
        self.assertIsNone(self.people.job)

    async def test_identity_unknown_uncertain_known_and_validation_gate(self):
        self.fixture_profile()
        self.assertEqual(self.people.classify(self.observation())[0], "KNOWN")
        self.assertEqual(
            self.people.classify(self.observation(vector=(0.0, 1.0, 0.0)))[0], "UNKNOWN"
        )
        self.assertEqual(
            self.people.classify(self.observation(sharpness=1))[0], "UNCERTAIN"
        )
        self.people.config["recognition_verified"] = False
        self.assertEqual(self.people.classify(self.observation())[0], "UNCERTAIN")
        self.people.activate("another-model")
        self.assertTrue(self.people.incompatible_profiles)
        self.assertEqual(self.people.classify(self.observation())[0], "UNCERTAIN")

    async def test_daily_greeting_and_opt_in_topic(self):
        person = self.fixture_profile()
        self.people.add_fact(person, "Modellbau", "Ich baue Modellautos.", True)
        self.people.greet(person)
        self.people.greet(person)
        self.assertEqual(len(self.events), 1)
        self.assertIn("Hallo Max", self.events[0][1])
        self.assertIn("Modellbau", self.events[0][1])
        self.assertEqual(
            self.people.db.execute("SELECT COUNT(*) FROM greetings").fetchone()[0], 1
        )

    async def test_profile_delete_requires_confirmation_and_cascades(self):
        person = self.fixture_profile()
        self.people.add_fact(person, "Hobby", "Modellbau")
        self.people.greet(person)
        with self.assertRaises(ValueError):
            self.people.delete(person, False)
        self.people.delete(person, True)
        for table in ("persons", "face_samples", "person_facts", "greetings"):
            self.assertEqual(
                self.people.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], 0
            )

    async def test_restart_preserves_daily_greeting(self):
        with tempfile.TemporaryDirectory() as directory:
            config = copy.deepcopy(DEFAULT)
            first = Core(config, Path(directory))
            first.people.activate("test-model")
            stamp = dt.datetime.now(dt.timezone.utc).isoformat()
            with first.store.db:
                first.store.db.execute(
                    "INSERT INTO persons(id,name,model_id,consent_at,store_images,created_at) VALUES(?,?,?,?,?,?)",
                    ("one", "Max", "test-model", stamp, 0, stamp),
                )
            out = []
            first.people.emit = lambda *message: out.append(message)
            first.people.greet("one")
            await first.close()
            second = Core(copy.deepcopy(DEFAULT), Path(directory))
            second.people.emit = lambda *message: out.append(message)
            second.people.greet("one")
            self.assertEqual(len(out), 1)
            await second.close()

    async def test_stop_and_privacy_remove_temporary_enrollment(self):
        self.target()
        self.people.request("Max", "A")
        await self.core.execute({"type": "stop"})
        self.assertIsNone(self.people.job)
        await self.core.execute({"type": "privacy.enable"})
        self.assertFalse(self.people.online)
        self.assertEqual(self.people.observations, {})


class ClosestFaceTests(unittest.TestCase):
    def test_largest_face_wins_even_if_other_is_unknown(self):
        selector = TargetSelector()
        far = Face(1, 0.2, 0.5, 0.1, 0.1, "UNKNOWN")
        near = Face(2, 0.5, 0.5, 0.4, 0.4, "KNOWN")
        self.assertEqual(selector.choose([far], 0).track_id, 1)
        self.assertEqual(selector.choose([far, near], 0.1).track_id, 2)
        self.assertIsNone(selector.choose([], 0.2))


if __name__ == "__main__":
    unittest.main()
