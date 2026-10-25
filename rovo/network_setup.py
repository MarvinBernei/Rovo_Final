"""Optionaler Linux-WLAN-Wächter. Ohne --apply ausschließlich Simulation.

Portal, DNS, DHCP und Zugangsdaten gehören WiFi Connect/NetworkManager.
Dieser Prozess berührt weder Kamera noch Core-API oder Aktuatoren.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT = {
    "enabled": False,
    "interface": "wlan0",
    "ssid": "ROVO-Einrichtung",
    "grace_seconds": 60,
    "poll_seconds": 5,
    "activity_timeout_seconds": 600,
    "retry_seconds": 60,
    "wifi_connect": "/usr/local/sbin/wifi-connect",
    "nmcli": "/usr/bin/nmcli",
    "ui_directory": "/usr/local/share/wifi-connect/ui",
    "passphrase_file": "/etc/rovo/network-passphrase",
}


def load_config(path: Path) -> dict:
    supplied = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(supplied, dict) or set(supplied) - set(DEFAULT):
        raise ValueError("Unbekannte WLAN-Konfiguration.")
    config = {**DEFAULT, **supplied}
    if type(config["enabled"]) is not bool:
        raise ValueError("enabled muss boolesch sein.")
    if not isinstance(config["interface"], str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,15}", config["interface"]
    ):
        raise ValueError("Ungültiger WLAN-Interfacename.")
    if (
        not isinstance(config["ssid"], str)
        or not 1 <= len(config["ssid"].encode()) <= 32
        or any(ord(c) < 32 for c in config["ssid"])
    ):
        raise ValueError("Ungültiger Einrichtungsnetzname.")
    for key, low, high in (
        ("grace_seconds", 30, 600),
        ("poll_seconds", 2, 30),
        ("activity_timeout_seconds", 60, 3600),
        ("retry_seconds", 30, 600),
    ):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise ValueError("Ungültiges Zeitintervall: " + key)
    for key in ("wifi_connect", "nmcli", "ui_directory", "passphrase_file"):
        if (
            not isinstance(config[key], str)
            or not PurePosixPath(config[key]).is_absolute()
        ):
            raise ValueError("Absoluter Pfad erforderlich: " + key)
    return config


@dataclass
class FallbackGate:
    grace: int = 60
    offline_since: float | None = None

    def ready(self, connected: bool | None, now: float) -> bool:
        # Unbekannt, rfkill, Fehler oder fremder AP: keine Netzübernahme.
        if connected is not False:
            self.offline_since = None
            return False
        if self.offline_since is None:
            self.offline_since = now
        return now - self.offline_since >= self.grace


def read_nm(config: dict, *args: str) -> str:
    result = subprocess.run(
        [config["nmcli"], "--wait", "8", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=12,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    return result.stdout.strip()


def wifi_connected(config: dict) -> bool | None:
    try:
        state = read_nm(
            config, "-g", "GENERAL.STATE", "device", "show", config["interface"]
        )
        code = int(state.split()[0])
        if code in {30, 40, 50, 60, 70, 80, 90, 120}:
            return False
        if code != 100:
            return None
        active = read_nm(
            config, "-t", "-f", "UUID,TYPE,DEVICE", "connection", "show", "--active"
        )
        for line in active.splitlines():
            uuid, kind, interface = line.split(":", 2)
            if interface == config["interface"] and kind in {"802-11-wireless", "wifi"}:
                mode = read_nm(
                    config,
                    "-g",
                    "802-11-wireless.mode",
                    "connection",
                    "show",
                    "uuid",
                    uuid,
                )
                return True if mode == "infrastructure" else None
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def portal_environment(config: dict) -> dict:
    path = Path(config["passphrase_file"])
    metadata = path.stat()
    if metadata.st_uid != 0 or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError(
            "Hotspot-Passwortdatei muss root gehören und Modus 0600 haben."
        )
    password = path.read_text(encoding="utf-8").rstrip("\r\n")
    if (
        not 8 <= len(password) <= 63
        or not password.isascii()
        or not all(32 <= ord(c) <= 126 for c in password)
    ):
        raise ValueError("Hotspot-Passwort muss 8–63 druckbare ASCII-Zeichen haben.")
    # Keine Spotify-/LLM-Tokens und kein Passwort in Prozessargumenten/Logs.
    return {
        "PATH": "/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LC_ALL": "C",
        "PORTAL_PASSPHRASE": password,
        "RUST_LOG": "off",
    }


def portal_command(config: dict) -> list[str]:
    return [
        config["wifi_connect"],
        "--portal-interface",
        config["interface"],
        "--portal-ssid",
        config["ssid"],
        "--portal-gateway",
        "192.168.42.1",
        "--portal-dhcp-range",
        "192.168.42.2,192.168.42.254",
        "--portal-listening-port",
        "80",
        "--ui-directory",
        config["ui_directory"],
        "--activity-timeout",
        str(config["activity_timeout_seconds"]),
    ]


def supervise(config: dict) -> None:
    import fcntl

    # Ein Wächter pro Host, unabhängig von einer Core-Instanz.
    with open("/run/rovo-network.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        gate = FallbackGate(config["grace_seconds"])
        while True:
            if gate.ready(wifi_connected(config), time.monotonic()):
                # Verbindung kann während der Wartezeit hergestellt worden sein.
                if wifi_connected(config) is False:
                    environment = portal_environment(config)
                    print("WLAN-Einrichtungsportal wird gestartet.", flush=True)
                    result = subprocess.run(
                        portal_command(config),
                        env=environment,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    print(
                        "Einrichtungsportal beendet."
                        if result.returncode == 0
                        else "Einrichtungsportal mit Fehler beendet; Voraussetzungen prüfen.",
                        flush=True,
                    )
                    time.sleep(config["retry_seconds"])
                gate.offline_since = None
            time.sleep(config["poll_seconds"])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ROVO-WLAN-Einrichtung, standardmäßig ohne Netzwerkänderung"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aktiviert reale Netzwerkänderungen unter Linux",
    )
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if not config["enabled"] or not args.apply:
            print(
                "Simulation: keine Netzwerkabfrage oder Änderung. Portal-Adresse: http://192.168.42.1"
            )
            return
        if sys.platform != "linux" or os.geteuid() != 0:
            raise ValueError(
                "Realer WLAN-Wächter benötigt Linux und root als separaten Dienst."
            )
        if not Path(config["ui_directory"]).is_dir():
            raise ValueError("WiFi-Connect-Oberfläche fehlt.")
        for key in ("wifi_connect", "nmcli"):
            if not os.access(config[key], os.X_OK):
                raise ValueError("Netzwerkprogramm fehlt: " + key)
        portal_environment(config)
        supervise(config)
    except (ValueError, OSError, subprocess.SubprocessError):
        parser.exit(
            1,
            "WLAN-Einrichtung konnte nicht gestartet werden; Konfiguration, Rechte und Programme prüfen.\n",
        )


if __name__ == "__main__":
    main()
