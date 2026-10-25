"""Regressionen: eine Quelle für Formulierungen, getrennte Parameterlogik."""

import copy
import unittest
from unittest.mock import patch

from rovo import catalog
from rovo.config import DEFAULT
from rovo.core import Core
from rovo.intents import parse


class CatalogRoutingTests(unittest.TestCase):
    def test_new_phrase_only_needs_catalog_entry(self):
        entry = {
            "intent": "greeting",
            "phrases": ["servus kleiner roboter"],
            "args": {},
            "negation_safe": False,
        }
        with patch("rovo.catalog.entries", return_value=[entry]):
            self.assertEqual(parse("Servus kleiner Roboter!").name, "greeting")
            self.assertEqual(parse("Hallo").name, "unknown")
            self.assertEqual(parse("Schau nach links").name, "unsupported_action")

    def test_single_lookup_and_safety_priority(self):
        with patch("rovo.intents.catalog_match", wraps=catalog.match) as lookup:
            self.assertEqual(parse("Schau mich an").name, "tracking.enable")
            self.assertEqual(lookup.call_count, 1)
        self.assertEqual(parse("Schau nicht nach links").name, "negated")
        self.assertEqual(parse("Verfolge mich nicht mehr").name, "tracking.disable")
        self.assertEqual(parse("Ja").name, "confirmation")

    def test_variable_slots_and_decimal_comma(self):
        self.assertEqual(
            parse("Dreh deinen Kopf fünf Grad nach links").args,
            {"axis": "pan", "delta": -5.0},
        )
        self.assertEqual(
            parse("Stell Pan auf 90 Grad").args, {"axis": "pan", "value": 90.0}
        )
        self.assertEqual(parse("Timer auf 1,5 Minuten").args["seconds"], 90.0)
        self.assertEqual(parse("Zehn Sekunden Timer").args["seconds"], 10.0)
        self.assertEqual(
            parse("Wie lange läuft mein Timer nach fünf Minuten").name, "clarify"
        )
        self.assertEqual(
            parse("Rovo, notiere Ich trinke 1,5 Liter").args["text"],
            "Ich trinke 1,5 Liter",
        )
        self.assertEqual(
            parse("Was ist 1,5 mal zwei?").args["expression"], "was ist 1,5 mal zwei"
        )


class CatalogAnswerTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_answer_comes_from_catalog(self):
        core = Core(copy.deepcopy(DEFAULT))
        try:
            entry = {
                "intent": "local.answer",
                "phrases": ["was ist python"],
                "args": {"reply": "Antwort aus dem Katalog."},
                "negation_safe": False,
            }
            with patch("rovo.catalog.entries", return_value=[entry]):
                result = await core.execute(
                    {"type": "text", "args": {"text": "Was ist Python?"}}
                )
                self.assertEqual(result["spoken_reply"], "Antwort aus dem Katalog.")
                self.assertEqual(core.llm.calls, 0)
        finally:
            await core.close()
