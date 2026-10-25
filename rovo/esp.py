"""Einziger Serial-Besitzer, versioniertes Protokoll und ehrlicher Simulator."""

from __future__ import annotations

import asyncio
import time

FACES = frozenset(
    "NEUTRAL LISTENING THINKING TALKING HAPPY CURIOUS SLEEPY SURPRISED ERROR SAD ANGRY CONFUSED LAUGHING WINK BLINK LOVE".split()
)


class FakeESP32:
    simulated = True

    def __init__(self) -> None:
        self.connected = True
        self.commands: list[tuple[str, tuple]] = []
        self.failure: str | None = None
        self.calibration_id = None
        self.feedback_supported = False
        self.measured_position = None

    async def command(self, name: str, *args: object) -> str:
        if not self.connected:
            raise ConnectionError("ESP32 nicht verbunden.")
        if self.failure == "timeout":
            raise TimeoutError("Simulierter ACK-Timeout.")
        if self.failure:
            raise ConnectionError("Simulierter Serial-Fehler.")
        self.commands.append((name, args))
        self.commands = self.commands[-100:]
        return "acknowledged"

    async def close(self) -> None:
        self.connected = False


class SerialESP32:
    """Öffnet den Port nur durch explizites CLI --connect-serial.

    Kein automatisches Reconnect/Replay. ACK bestätigt Annahme, nicht Istposition.
    Befehle haben eine begrenzte Leitungslänge und laufen seriell unter einem Lock.
    """

    simulated = False

    def __init__(self, port: str) -> None:
        self.port = port
        self.serial = None
        self.connected = False
        self.sequence = 0
        self.lock = asyncio.Lock()
        self.calibration_id: str | None = None
        self.feedback_supported = False
        self.measured_position: dict | None = None

    async def connect(self) -> None:
        import serial

        self.serial = await asyncio.to_thread(
            serial.Serial, self.port, 115200, timeout=0.05, write_timeout=0.2
        )
        try:
            await asyncio.sleep(2)  # Portöffnung kann das Board zurücksetzen.
            self.serial.reset_input_buffer()
            self.serial.write(b"HELLO 1\n")
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                line = (
                    (await asyncio.to_thread(self.serial.readline))
                    .decode("ascii", "replace")
                    .strip()
                )
                if line == "HELLO 1 ROVO_ESP":
                    self.connected = True
                    await self._read_info()
                    return
            raise ConnectionError("Keine kompatible ROVO-Protokollversion 1.")
        except BaseException:
            await self.close()
            raise

    async def _read_info(self) -> None:
        """Capability-Abfrage; alte Firmware bleibt verbunden, aber ohne Freigaben."""
        self.sequence += 1
        ident = str(self.sequence)
        await self._io(self.serial.write, f"CMD {ident} INFO\n".encode("ascii"))
        deadline = time.monotonic() + 0.4
        while time.monotonic() < deadline:
            line = (
                (await self._io(self.serial.readline))
                .decode("ascii", "replace")
                .strip()
            )
            if line.startswith(f"INFO {ident} "):
                parts = line.split()
                if len(parts) == 6 and parts[2] == "CALIB" and parts[4] == "FEEDBACK":
                    self.calibration_id = None if parts[3] == "NONE" else parts[3]
                    self.feedback_supported = parts[5] == "1"
            elif line in {f"ACK {ident}", f"ERR {ident} UNSUPPORTED"}:
                return

    async def position(self) -> dict | None:
        if not self.feedback_supported:
            return None
        async with self.lock:
            self.sequence += 1
            ident = str(self.sequence)
            await self._io(self.serial.write, f"CMD {ident} POSITION\n".encode("ascii"))
            deadline = time.monotonic() + 0.4
            value = None
            while time.monotonic() < deadline:
                line = (
                    (await self._io(self.serial.readline))
                    .decode("ascii", "replace")
                    .strip()
                )
                if line.startswith(f"POS {ident} "):
                    fields = line.split()
                    if len(fields) == 4:
                        value = {
                            "pan_deg": float(fields[2]),
                            "tilt_deg": float(fields[3]),
                        }
                elif line == f"ACK {ident}":
                    self.measured_position = value
                    return value
                elif line.startswith(f"ERR {ident} "):
                    raise ValueError("ESP32-Positionsabfrage fehlgeschlagen.")
            raise TimeoutError("ESP32-Positionsabfrage ohne Antwort.")

    @staticmethod
    async def _io(function, *args):
        # Abbruch eines Sequenz-Tasks darf keinen laufenden Serial-Thread freigeben.
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            except Exception:
                pass
            raise

    async def command(self, name: str, *args: object) -> str:
        if name not in {"MOVE", "STOP", "FACE", "PING", "PROFILE", "BRIGHTNESS"}:
            raise ValueError("Unbekannter Serial-Befehl.")
        async with self.lock:
            if not self.connected or self.serial is None:
                raise ConnectionError("ESP32 nicht verbunden.")
            self.sequence += 1
            ident = str(self.sequence)
            line = " ".join(("CMD", ident, name, *(str(arg) for arg in args)))
            if len(line) > 120 or "\n" in line or "\r" in line:
                raise ValueError("Ungültige Serial-Nachricht.")
            try:
                await self._io(self.serial.write, (line + "\n").encode("ascii"))
                deadline = time.monotonic() + 0.4
                while time.monotonic() < deadline:
                    answer = (
                        (await self._io(self.serial.readline))
                        .decode("ascii", "replace")
                        .strip()
                    )
                    if answer == "ACK " + ident:
                        return "acknowledged"
                    if answer.startswith("ERR " + ident + " "):
                        raise ValueError(
                            "ESP32 hat den Befehl abgewiesen: "
                            + answer.split(" ", 2)[2]
                        )
                raise TimeoutError(
                    "ESP32-Bestätigung fehlt; keine erneute Bewegung gesendet."
                )
            except (OSError, TimeoutError):
                self.connected = False
                raise

    async def close(self) -> None:
        self.connected = False
        if self.serial is not None:
            await asyncio.to_thread(self.serial.close)
            self.serial = None
