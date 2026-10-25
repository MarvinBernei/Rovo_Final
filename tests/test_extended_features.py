import datetime as dt
import unittest
from unittest.mock import AsyncMock, Mock, patch
from zoneinfo import ZoneInfo

from rovo.activities import Activities
from rovo.camera_source import open_camera
from rovo.config import load
from rovo.spotify import Spotify
from rovo.storage import Store
from rovo.units_de import convert


class UnitConversionTests(unittest.TestCase):
    def test_dimensions_and_temperature(self):
        self.assertAlmostEqual(convert(1, "km", "m")[0], 1000)
        self.assertAlmostEqual(convert(32, "fahrenheit", "celsius")[0], 0)
        with self.assertRaises(ValueError):
            convert(1, "kg", "meter")


class ReminderTests(unittest.TestCase):
    def test_recurring_reminder_fires_once_per_local_day(self):
        store = Store(":memory:")
        activities = Activities(store, "Europe/Berlin")
        activities.reminder_add("Medikament", 7, 30, list(range(7)))
        now = dt.datetime(2026, 10, 25, 7, 30, tzinfo=ZoneInfo("Europe/Berlin"))
        self.assertEqual(len(activities.reminders_due(now)), 1)
        self.assertEqual(activities.reminders_due(now), [])
        self.assertEqual(len(activities.reminders_due(now + dt.timedelta(days=1))), 1)


class CameraSourceTests(unittest.TestCase):
    def test_picamera_backend_is_selected_without_opening_real_camera(self):
        config = load()["camera"]
        config["backend"] = "picamera2"
        with patch("rovo.camera_source.Picamera2Source", return_value=Mock()) as source:
            open_camera(config)
        source.assert_called_once_with(config)


class SpotifyExtendedTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_select_queue_and_shuffle(self):
        spotify = Spotify()
        spotify.request = AsyncMock(
            return_value={
                "tracks": {
                    "items": [
                        {
                            "uri": "spotify:track:abc123",
                            "name": "Titel",
                            "artists": [{"name": "Interpret"}],
                        }
                    ]
                }
            }
        )
        items = await spotify.search("Titel")
        self.assertEqual(items[0]["subtitle"], "Interpret")
        spotify.request.return_value = {}
        await spotify.play_uri(items[0]["uri"])
        await spotify.enqueue(items[0]["uri"])
        await spotify.shuffle(True)
        self.assertEqual(spotify.request.await_count, 4)


if __name__ == "__main__":
    unittest.main()
