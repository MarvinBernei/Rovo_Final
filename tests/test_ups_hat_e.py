import unittest
from unittest.mock import Mock, patch

from rovo.ups_hat_e import PowerMonitor, read_measurements


def fake_bus(flags=3):
    bus = Mock(spec=["read_byte_data", "read_i2c_block_data"])
    bus.read_byte_data.side_effect = lambda address, register: {
        0: 10,
        2: 0xA0,
        3: flags,
    }[register]
    words = {0x20: 15000, 0x22: 65536 - 500, 0x24: 65, 0x10: 9000, 0x12: 1000}
    bus.read_i2c_block_data.side_effect = lambda address, register, length: [
        words[register] & 255,
        words[register] >> 8,
    ]
    return bus


class UPSTests(unittest.IsolatedAsyncioTestCase):
    def test_signed_current_and_direct_percentage(self):
        result = read_measurements(fake_bus())
        self.assertEqual(result["voltage"], 15)
        self.assertEqual(result["current"], -0.5)
        self.assertEqual(result["battery_percent"], 65)
        self.assertTrue(result["charging"])

    def test_chip_error_keeps_battery_unknown(self):
        result = read_measurements(fake_bus(1))
        self.assertIsNone(result["battery_percent"])
        self.assertIsNone(result["voltage"])
        with self.assertRaises(ValueError):
            read_measurements(fake_bus(0))

    def test_wrong_identity_rejected(self):
        bus = fake_bus()
        bus.read_byte_data.side_effect = None
        bus.read_byte_data.return_value = 0
        with self.assertRaises(ValueError):
            read_measurements(bus)

    async def test_simulation_never_opens_bus_and_stale_is_unknown(self):
        config = {"driver": "waveshare-ups-hat-e", "i2c_bus": 1, "i2c_address": 45}
        monitor = PowerMonitor(config, True)
        with patch("rovo.ups_hat_e.read_device") as read:
            await monitor.poll()
            read.assert_not_called()
        monitor.simulation = False
        monitor.cached = {
            **monitor.cached,
            "measured_at_unix": 1,
            "battery_percent": 65,
        }
        self.assertIsNone(monitor.snapshot()["battery_percent"])
