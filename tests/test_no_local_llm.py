"""Alte lokale Modellkonfiguration darf keinen Modellzugriff reaktivieren."""

import unittest

from rovo.llm import TextLLM


class RemovedLocalModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_old_enabled_endpoint_cannot_enable_local_model(self):
        model = TextLLM(
            {"enabled": True, "endpoint": "http://127.0.0.1:11434", "model": "old"}
        )
        self.assertFalse(model.available())
        with self.assertRaises(ValueError):
            await model.respond("Eine freie Frage")
        self.assertEqual(model.calls, 0)
