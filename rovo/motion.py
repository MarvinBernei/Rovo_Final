"""Alle Bewegungsquellen passieren dieselben Limits und Abbruchgenerationen."""

from __future__ import annotations

import asyncio
import time

from .config import number


class Motion:
    def __init__(self, config: dict, esp, live_authorized: bool = False) -> None:
        self.config, self.esp = config, esp
        self.live_authorized = live_authorized
        self.pan: float | None = None
        self.tilt: float | None = None
        self.generation = 0
        self.stopped = False
        self.tracking = False
        self.manual_until = 0.0
        self.return_pending = False
        self.speed = 20.0
        self.acceleration = 40.0
        self.social_until = 0.0
        self.sequence_until = 0.0
        self.sequence_task = None
        self.lock = asyncio.Lock()
        self.profile_pending = False

    def check(self) -> None:
        if not self.esp.connected:
            raise ConnectionError("ESP32 nicht verbunden.")
        if not self.config["motion"]["calibrated"]:
            raise ValueError("Bewegung gesperrt: keine bestätigte Kalibrierung.")
        if not self.esp.simulated and (
            self.config["safe_mode"] or not self.live_authorized
        ):
            raise ValueError(
                "Reale Bewegung gesperrt: Safe Mode oder fehlende Startfreigabe."
            )
        if (
            not self.esp.simulated
            and self.esp.calibration_id != self.config["motion"]["calibration_id"]
        ):
            raise ValueError(
                "Bewegung gesperrt: Kalibrierungs-ID von Pi und Nano stimmt nicht überein."
            )

    async def move(
        self,
        pan: float,
        tilt: float,
        source: str = "manual",
        observed: float | None = None,
    ) -> dict:
        if source == "manual":
            self.interrupt_sequence()
        generation = self.generation
        async with self.lock:
            self.check()
            if generation != self.generation:
                raise ValueError("Bewegung wurde durch Stopp verworfen.")
            if source in {"tracking", "social"}:
                if (
                    self.stopped
                    or (source == "tracking" and not self.tracking)
                    or (
                        source == "social"
                        and (self.tracking or time.monotonic() > self.social_until)
                    )
                    or time.monotonic() < max(self.manual_until, self.sequence_until)
                ):
                    raise ValueError("Tracking pausiert.")
                if observed is None or not 0 <= time.monotonic() - observed <= 0.25:
                    raise ValueError("Veraltete Kamerabeobachtung verworfen.")
            elif source == "manual":
                pass
            elif source == "sequence":
                if self.stopped or self.sequence_task is not asyncio.current_task():
                    raise ValueError("Bewegungssequenz abgebrochen.")
            else:
                raise ValueError("Nicht registrierte Bewegungsquelle.")
            for axis, value in (("pan", pan), ("tilt", tilt)):
                limits = self.config["motion"][axis]
                number(value, limits["min"], limits["max"])
            if self.profile_pending:
                await self.esp.command("PROFILE", self.speed, self.acceleration)
                self.profile_pending = False
            await self.esp.command("MOVE", round(pan, 2), round(tilt, 2))
            if generation != self.generation:
                raise ValueError("Ziel wurde zwischenzeitlich gestoppt.")
            self.pan, self.tilt = pan, tilt
            if source == "manual":
                self.stopped = False
                self.manual_until = time.monotonic() + 5
                self.return_pending = self.tracking
            measured = (
                await self.esp.position() if hasattr(self.esp, "position") else None
            )
            return {
                "pan_target_deg": pan,
                "tilt_target_deg": tilt,
                "measured_position": measured,
                "simulated": self.esp.simulated,
            }

    async def home(self) -> dict:
        self.check()
        return await self.move(
            self.config["motion"]["pan"]["home"], self.config["motion"]["tilt"]["home"]
        )

    async def relative(self, axis: str, delta: float) -> dict:
        self.check()
        if axis not in ("pan", "tilt"):
            raise ValueError("Unbekannte Achse.")
        if self.pan is None or self.tilt is None:
            raise ValueError(
                "Noch keine Sollposition bekannt. Zuerst bewusst Home anfordern."
            )
        delta = number(delta, -180, 180) * self.config["motion"][axis]["direction"]
        limits = self.config["motion"][axis]
        value = (self.pan if axis == "pan" else self.tilt) + delta
        target = max(limits["min"], min(limits["max"], value))
        result = await self.move(
            target if axis == "pan" else self.pan,
            target if axis == "tilt" else self.tilt,
        )
        result["limited"] = target != value
        return result

    async def configure(self, speed: float, acceleration: float) -> dict:
        self.check()
        speed = number(speed, 2, 20)
        acceleration = number(acceleration, 4, 40)
        async with self.lock:
            await self.esp.command("PROFILE", speed, acceleration)
            self.speed, self.acceleration = speed, acceleration
        return {"speed_limit_deg_s": speed, "acceleration_limit_deg_s2": acceleration}

    async def profile(
        self, speed_factor: float = 1, acceleration_factor: float = 1
    ) -> dict:
        self.check()
        number(speed_factor, 0.25, 2)
        number(acceleration_factor, 0.25, 2)
        speed = max(2.0, min(20.0, self.speed * speed_factor))
        acceleration = max(4.0, min(40.0, self.acceleration * acceleration_factor))
        await self.esp.command("PROFILE", speed, acceleration)
        self.speed, self.acceleration = speed, acceleration
        return {"speed_limit_deg_s": speed, "acceleration_limit_deg_s2": acceleration}

    async def tick(self) -> None:
        if not self.return_pending or time.monotonic() < self.manual_until:
            return
        if not self.tracking or self.stopped:
            self.return_pending = False
            return
        # Home ist ein Sollwert; keine Behauptung einer gemessenen Ankunft.
        await self.home()
        self.return_pending = False
        # Konservative Wartezeit für das begrenzte Firmwareprofil, dann frische Frames.
        self.manual_until = (
            time.monotonic()
            + 180 / self.speed
            + 2 * self.speed / self.acceleration
            + 0.5
        )

    async def sequence(self, name: str) -> dict:
        self.check()
        if name not in {"nod", "shake", "look"}:
            raise ValueError("Unbekannte Bewegungssequenz.")
        if self.pan is None or self.tilt is None:
            raise ValueError("Zuerst Home anfordern.")
        if self.sequence_task and not self.sequence_task.done():
            raise ValueError("Eine Bewegungssequenz läuft bereits.")
        base_pan, base_tilt, generation = self.pan, self.tilt, self.generation
        steps = {
            "nod": [(0, 5), (0, -5), (0, 5), (0, 0)],
            "shake": [(-7, 0), (7, 0), (-7, 0), (0, 0)],
            "look": [(-12, 0), (12, 0), (0, -6), (0, 0)],
        }[name]
        self.stopped = False
        self.return_pending = False
        self.social_until = 0
        self.sequence_until = float("inf")

        async def run():
            try:
                for dp, dt in steps:
                    if generation != self.generation:
                        return
                    p, t = self.config["motion"]["pan"], self.config["motion"]["tilt"]
                    pan = max(p["min"], min(p["max"], base_pan + dp * p["direction"]))
                    tilt = max(t["min"], min(t["max"], base_tilt + dt * t["direction"]))
                    distance = max(abs(pan - self.pan), abs(tilt - self.tilt))
                    await self.move(pan, tilt, "sequence")
                    await asyncio.sleep(
                        distance / self.speed + 2 * self.speed / self.acceleration + 0.3
                    )
            except (OSError, TimeoutError, ValueError):
                await self.stop()
            finally:
                self.sequence_until = 0

        self.sequence_task = asyncio.create_task(run())
        return {"sequence": name, "state": "started", "measured_position": None}

    def interrupt_sequence(self):
        if self.sequence_task and self.sequence_task is not asyncio.current_task():
            self.sequence_task.cancel()
        self.sequence_until = 0

    async def stop(self) -> dict:
        self.generation += 1
        self.interrupt_sequence()
        self.social_until = 0
        self.stopped = True
        self.tracking = False
        self.return_pending = False
        self.pan = self.tilt = None  # Interpolierter Stand ist ohne Sensor unbekannt.
        if not self.esp.connected:
            return {"local_cancelled": True, "hardware_acknowledged": False}
        try:
            await self.esp.command("STOP")
            return {"local_cancelled": True, "hardware_acknowledged": True}
        except (ValueError, OSError, TimeoutError):
            return {"local_cancelled": True, "hardware_acknowledged": False}
