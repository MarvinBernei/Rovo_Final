"""Gemeinsames, typgeprüftes Gateway für CLI, Voice und Node-RED."""

from __future__ import annotations

import asyncio
import datetime as dt
import time
import uuid
from pathlib import Path

from .activities import Activities
from .application.actions import dispatch_action
from .application.contracts import COMMAND_ARGUMENTS
from .application.dialogue import handle_text
from .audio import Audio
from .connections import Connections, Credentials
from .esp import FakeESP32
from .expressions import EMOTIONS, Expressions, emotion_for
from .llm import TextLLM
from .motion import Motion
from .people import People
from .settings import Settings
from .storage import Store
from .ups_hat_e import PowerMonitor
from .vision import Camera
from .weather import Weather


class Core:
    def __init__(
        self,
        config: dict,
        data: Path | None = None,
        esp=None,
        live_authorized: bool = False,
        power_authorized: bool = False,
    ) -> None:

        self.config = config

        self.power = PowerMonitor(config["power"], config["simulation"])

        self.esp = esp or FakeESP32()

        self.motion = Motion(config, self.esp, live_authorized)

        self.audio = Audio(config["audio"])

        self.credentials = Credentials(data)
        self.audio.spotify.credentials = self.credentials
        self.audio.spotify.guard = lambda: (self.cancel_epoch, self.privacy)

        self.expressions = Expressions(self.esp)

        self.llm = TextLLM(config["llm"], self.credentials)
        self.llm.guard = lambda: (self.cancel_epoch, self.privacy)
        saved_llm = self.credentials.get("llm")
        if saved_llm.get("provider"):
            config["llm"].update(
                enabled=saved_llm.get("enabled") is True,
                allow_cloud=saved_llm.get("allow_cloud") is True,
                model=saved_llm.get("model"),
            )
        self.connections = Connections(self, self.credentials)

        self.store = Store(data / "rovo.sqlite3" if data else ":memory:")

        self.activities = Activities(self.store, config["timezone"])

        self.people = People(
            self.store,
            config["people"],
            config["timezone"],
            self.notify,
            lambda: setattr(self.motion, "tracking", False),
        )

        self.camera = Camera(config["camera"], self.motion, self.people)
        self.weather = Weather(config["weather"])

        self.settings = Settings(data)

        self.default_settings = Settings.capture(self)

        self.hardware_limits = {
            axis: dict(config["motion"][axis]) for axis in ("pan", "tilt")
        }

        limits_path = data / "safe_limits.json" if data else None

        if limits_path and limits_path.exists():
            try:
                import json

                from .calibration import validate_limits

                config["motion"].update(
                    validate_limits(
                        json.loads(limits_path.read_text(encoding="utf-8")),
                        self.hardware_limits,
                    )
                )

            except (ValueError, OSError, TypeError, KeyError):
                self.settings.error = "Gespeicherte Softwaregrenzen ungültig; bestätigte Ausgangsgrenzen verwendet."

        if self.settings.path and self.settings.path.exists():
            try:
                Settings.apply(self, self.settings.read())

            except (ValueError, OSError, TypeError, KeyError):
                self.settings.error = (
                    "Gespeicherte Einstellungen ungültig; Startwerte verwendet."
                )

        self.media_root = (data or Path("data")) / "music"

        self.started = time.monotonic()

        self.privacy = False

        self.followups: dict[str, tuple[float, str, dict]] = {}

        self.pending: dict[str, tuple[float, str, str]] = {}

        self.event_queue: list[dict] = []

        self.workers: set[asyncio.Task] = set()

        self.closed = False

        self.cancel_epoch = 0

        self.power_authorized = power_authorized

        self.power_pending: dict[str, tuple[float, str]] = {}

        self.last_gaze = -float("inf")

        self.wakeword_online = False

        self.last_alarm_at = 0.0

    def result(
        self,
        request_id: str,
        reply: str,
        *,
        ok: bool = True,
        data: dict | None = None,
        intent: str = "unknown",
        status: str = "completed",
        code: str | None = None,
    ) -> dict:

        data = dict(data or {})

        emotion = data.get("emotion", emotion_for(intent, ok))

        if not isinstance(emotion, str) or emotion not in EMOTIONS:
            emotion = "NEUTRAL"

        if intent != "status":
            self.expressions.set("answer", emotion)

        if not ok:
            self.expressions.set("error", "ERROR", 90, 3)

        data["emotion"] = emotion

        return {
            "schema": "rovo.result.v1",
            "request_id": request_id,
            "ok": ok,
            "status": status,
            "intent": intent,
            "spoken_reply": reply,
            "error_code": code,
            "data": data or {},
            "simulated": self.esp.simulated,
        }

    def status(self) -> dict:

        from .telemetry import system_status

        return {
            "schema": "rovo.status.v1",
            "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "simulation": self.esp.simulated,
            "safe_mode": self.config["safe_mode"],
            "privacy": self.privacy,
            "system": system_status(self.started),
            "esp32": {
                "connected": self.esp.connected,
                "simulated": self.esp.simulated,
                "protocol": 1,
            },
            "vision": self.camera.status(),
            "people": self.people.status(),
            "motion": {
                "calibrated": self.config["motion"]["calibrated"],
                "pan_target_deg": self.motion.pan,
                "tilt_target_deg": self.motion.tilt,
                "measured_position": self.esp.measured_position,
                "position_feedback_available": self.esp.feedback_supported,
                "calibration_match": self.esp.simulated
                or self.esp.calibration_id == self.config["motion"]["calibration_id"],
                "speed_limit_deg_s": self.motion.speed,
                "acceleration_limit_deg_s2": self.motion.acceleration,
                "manual_return_pending": self.motion.return_pending,
            },
            "audio": {
                "tts_online": self.audio.available,
                "wakeword_online": self.wakeword_online,
                "music_state": self.audio.music_state,
                "music_volume_percent": self.audio.volume,
                "speech_volume_percent": self.audio.speech_volume,
                "speech_rate": self.audio.speech_rate,
                "music_source": "spotify" if self.audio.spotify.active else "local",
            },
            "power": self.power.snapshot(),
            "llm": self.llm.public(),
            "capabilities": self.capabilities(),
        }

    def capabilities(self) -> dict:

        try:
            self.motion.check()

            motion, reason = True, None

        except (ValueError, OSError) as exc:
            motion, reason = False, str(exc)

        return {
            "local_text": {"available": True},
            "math": {"available": True},
            "notes": {"available": True},
            "timers": {"available": True},
            "games": {"available": True},
            "stopwatch": {"available": True},
            "alarms": {"available": True},
            "motion": {
                "available": motion,
                "reason": reason,
                "simulated": self.esp.simulated,
            },
            "camera": {"available": self.camera.online},
            "tts": {"available": self.audio.available},
            "wakeword": {
                "available": self.wakeword_online,
                "reason": None
                if self.wakeword_online
                else "Freihändigen Modus mit lokalem Anrede-Modell starten.",
            },
            "face_identification": {
                "available": self.people.online
                and self.config["people"]["recognition_verified"],
                "reason": None
                if self.people.online and self.config["people"]["recognition_verified"]
                else "Lokale Modelle laden und Wiedererkennung am Gerät validieren.",
            },
            "face_enrollment": {"available": self.people.online},
            "spotify": {
                "available": self.audio.spotify.configured,
                "probe": "last_success"
                if self.audio.spotify.verified_at
                else "not_verified",
            },
            "ups": {"available": self.power.snapshot()["source"] is not None},
            "llm": {
                "available": self.llm.available(),
                "probe": "last_success" if self.llm.verified_at else "not_verified",
            },
        }

    async def execute(self, command: dict, session: str = "local") -> dict:

        request_id = uuid.uuid4().hex

        intent = "invalid"

        try:
            if not isinstance(command, dict) or set(command) - {
                "schema",
                "type",
                "args",
                "request_id",
            }:
                raise ValueError("Ungültiges Befehlspaket.")

            if command.get("schema", "rovo.command.v1") != "rovo.command.v1":
                raise ValueError("Nicht unterstützte Schemaversion.")

            supplied_id = command.get("request_id")

            if supplied_id is not None:
                if not isinstance(supplied_id, str) or not 1 <= len(supplied_id) <= 80:
                    raise ValueError("Ungültige Auftrags-ID.")

                request_id = supplied_id

            intent, args = command.get("type"), command.get("args", {})

            if not isinstance(intent, str) or not isinstance(args, dict):
                raise ValueError("Typ und Argumentobjekt erforderlich.")

            schemas = COMMAND_ARGUMENTS

            if intent not in schemas or set(args) != schemas[intent]:
                raise ValueError("Unbekannter Befehl oder ungültige Argumente.")

            if intent == "text":
                text = args["text"]

                if not isinstance(text, str) or not 1 <= len(text) <= 2000:
                    raise ValueError("Text muss 1 bis 2000 Zeichen enthalten.")

                return await self.text(text, session, request_id)

            if intent == "status":
                return self.result(
                    request_id, "Status abgerufen.", data=self.status(), intent=intent
                )

            data, reply, status = await self.action(intent, args, session)

            return self.result(
                request_id, reply, data=data, intent=intent, status=status
            )

        except (ValueError, KeyError, TypeError) as exc:
            return self.result(
                request_id,
                str(exc) if isinstance(exc, ValueError) else "Ungültige Argumente.",
                ok=False,
                intent=intent or "invalid",
                status="error",
                code="REJECTED",
            )

        except (OSError, TimeoutError, ImportError):
            return self.result(
                request_id,
                "Die benötigte Verbindung oder lokale Komponente ist nicht verfügbar.",
                ok=False,
                intent=intent or "invalid",
                status="error",
                code="UNAVAILABLE",
            )

    async def action(
        self, intent: str, args: dict, session: str
    ) -> tuple[dict, str, str]:

        return await dispatch_action(self, intent, args, session)

    async def text(self, text: str, session: str, request_id: str) -> dict:

        return await handle_text(self, text, session, request_id)

    def attend(self):

        now = time.monotonic()

        behavior = self.config["behavior"]

        if (
            behavior["social_gaze"]
            and not self.privacy
            and self.camera.online
            and not self.people.job
            and not self.motion.stopped
            and now >= self.motion.manual_until
            and now - self.last_gaze >= behavior["gaze_interval_seconds"]
        ):
            self.motion.social_until = now + behavior["gaze_seconds"]

            self.last_gaze = now

    def notify(self, text: str, event_type: str) -> None:

        face = "HAPPY" if "greet" in event_type else "CURIOUS"

        self.expressions.set("event", face, 20, 8)

        self.event_queue.append(
            {
                "type": event_type,
                "text": text,
                "details": text,
                "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
        )

        self.event_queue = self.event_queue[-100:]

        self.background_speech(text, face)

    def background_speech(self, reply: str, emotion: str | None = None) -> None:

        if len(self.workers) >= 2:
            return

        async def speak() -> None:

            try:
                face = (
                    emotion
                    or self.expressions.states.get("answer", (0, 0, "NEUTRAL"))[2]
                )

                self.expressions.set(
                    "speech", "TALKING" if face == "NEUTRAL" else face, 40, 120
                )

                await self.audio.speak(reply)

            except (OSError, TimeoutError, ValueError):
                self.event_queue.append(
                    {"type": "audio.error", "message": "Lokale TTS fehlgeschlagen."}
                )

            finally:
                self.expressions.clear("speech")

        task = asyncio.create_task(speak())

        self.workers.add(task)

        task.add_done_callback(self.workers.discard)

    async def tick(self) -> None:

        while not self.closed:
            await self.power.poll()

            try:
                await self.expressions.tick()

            except (OSError, TimeoutError, ValueError):
                pass

            for alarm in self.activities.due():
                self.last_alarm_at = time.monotonic()

                self.notify(
                    f"Dein Wecker für {alarm['hour']:02d}:{alarm['minute']:02d} klingelt.",
                    "alarm.fired",
                )

            for reminder in self.activities.reminders_due():
                self.notify("Erinnerung: " + reminder["text"], "reminder.fired")

            try:
                await self.motion.tick()

            except (ValueError, OSError, TimeoutError):
                self.motion.return_pending = False

                self.motion.tracking = False

                self.notify(
                    "Die Rückkehr zur Startposition ist fehlgeschlagen; Tracking bleibt aus.",
                    "motion.error",
                )

            for timer in self.store.due():
                if timer["label"] == "Wecker-Schlummern":
                    self.last_alarm_at = time.monotonic()

                    self.notify("Dein verschobener Wecker klingelt.", "alarm.fired")

                    continue

                self.event_queue.append(
                    {
                        "type": "timer.fired",
                        "id": timer["id"],
                        "text": "Dein Timer ist abgelaufen.",
                    }
                )

                self.background_speech("Dein Timer ist abgelaufen.")

            self.event_queue = self.event_queue[-100:]

            await asyncio.sleep(0.2)

    async def close(self) -> None:

        self.closed = True
        self.cancel_epoch += 1
        self.audio.spotify.cancel_login()

        await self.motion.stop()

        await self.camera.stop()

        for task in list(self.workers):
            task.cancel()

        await asyncio.gather(*self.workers, return_exceptions=True)

        try:
            await self.audio.close()

        finally:
            await self.esp.close()

            self.store.close()
