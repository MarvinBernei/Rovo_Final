"""WLAN-Entscheidungen mit Mocks: kein Hotspot, keine echten Zugangsdaten."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rovo.network_setup import (
    DEFAULT,
    FallbackGate,
    load_config,
    portal_command,
    wifi_connected,
)


class NetworkSetupTests(unittest.TestCase):
    def test_wait_before_fallback(self):
        gate = FallbackGate(60)
        self.assertFalse(gate.ready(False, 0))
        self.assertFalse(gate.ready(False, 59))
        self.assertTrue(gate.ready(False, 60))

    def test_connected_and_unknown_reset_timer(self):
        for state in (True, None):
            gate = FallbackGate(60)
            gate.ready(False, 0)
            self.assertFalse(gate.ready(state, 60))
            self.assertFalse(gate.ready(False, 61))
            self.assertTrue(gate.ready(False, 121))

    def test_wifi_connected_without_internet_probe(self):
        with patch(
            "rovo.network_setup.read_nm",
            side_effect=[
                "100 (connected)",
                "123:802-11-wireless:wlan0",
                "infrastructure",
            ],
        ) as read:
            self.assertIs(wifi_connected(DEFAULT), True)
            self.assertEqual(read.call_count, 3)

    def test_foreign_ap_and_unmanaged_not_taken_over(self):
        with patch(
            "rovo.network_setup.read_nm",
            side_effect=["100 (connected)", "123:802-11-wireless:wlan0", "ap"],
        ):
            self.assertIsNone(wifi_connected(DEFAULT))
        with patch("rovo.network_setup.read_nm", return_value="10 (unmanaged)"):
            self.assertIsNone(wifi_connected(DEFAULT))

    def test_disconnected_and_error(self):
        with patch("rovo.network_setup.read_nm", return_value="30 (disconnected)"):
            self.assertIs(wifi_connected(DEFAULT), False)
        with patch("rovo.network_setup.read_nm", side_effect=OSError("kein nmcli")):
            self.assertIsNone(wifi_connected(DEFAULT))

    def test_configuration_defaults_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "network.json"
            path.write_text("{}", encoding="utf-8")
            self.assertFalse(load_config(path)["enabled"])
            for value in (
                {"enabled": "yes"},
                {"interface": "wlan0; reboot"},
                {"grace_seconds": 0},
                {"password": "nicht-erlaubt"},
                {"wifi_connect": "relative"},
                {"ssid": "x" * 33},
            ):
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_config(path)

    def test_portal_args_no_credentials(self):
        command = portal_command(DEFAULT)
        self.assertIn("192.168.42.1", command)
        self.assertIn("wlan0", command)
        self.assertNotIn("--portal-passphrase", command)
        self.assertIn("600", command)

    def test_dry_run_never_queries_network(self):
        from rovo.network_setup import main

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"enabled":true}', encoding="utf-8")
            with (
                patch("sys.argv", ["network_setup", "--config", str(path)]),
                patch("rovo.network_setup.supervise") as supervise,
                patch("rovo.network_setup.read_nm") as read,
                patch("builtins.print"),
            ):
                main()
                supervise.assert_not_called()
                read.assert_not_called()
