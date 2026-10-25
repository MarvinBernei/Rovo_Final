"""Begrenzte Dashboard-Kompatibilität: alter UI-Vertrag, derselbe sichere Core.

Keine zweite Hardwaresteuerung und keine Übernahme von
Dashboard-Testwinkeln als Kalibrierung. Nicht unterstützte Speicheraktionen scheitern klar.
"""

from __future__ import annotations

from .esp import FACES

RUNTIME_ACTIONS = frozenset(
    {
        "audio.configure",
        "display.configure",
        "settings.save",
        "settings.restore",
        "calibration.apply",
        "music.spotify",
        "music.spotify.search",
        "music.spotify.play_uri",
        "music.spotify.queue",
        "music.spotify.shuffle",
        "music.pause",
        "music.resume",
        "music.stop",
        "music.volume",
        "motion.configure",
        "motion.relative",
        "motion.sequence",
        "camera.configure",
        "behavior.gaze",
        "alarm.add",
        "alarm.list",
        "alarm.change",
        "alarm.snooze",
        "timer.start",
        "timer.status",
        "timer.action",
        "notes.list",
        "notes.add",
        "stopwatch.action",
        "game.start",
        "game.cancel",
    }
)


def projection(core) -> dict:
    """Nur für Dashboard benötigte öffentliche Zustandswerte; keine Endpunkte/Secrets."""
    snapshot = core.status()
    motion = core.config["motion"]
    available = snapshot["capabilities"]["motion"]["available"]
    simulated = snapshot["simulation"]
    tele = {
        "system": {
            "cpuTemp": snapshot["system"]["cpu_temp_c"],
            "load1": snapshot["system"]["load_1m"],
            "ramUsage": snapshot["system"]["ram_usage_percent"],
            "uptimeSeconds": snapshot["system"]["process_uptime_s"],
            "hostname": snapshot["system"]["hostname"],
            "platform": snapshot["system"]["os"],
        },
        "battery": {
            "percent": snapshot["power"]["battery_percent"],
            "voltage": snapshot["power"]["voltage"],
            "current": snapshot["power"]["current"],
            "charging": snapshot["power"]["charging"],
        },
        # Ein FakeESP32 ist kein angeschlossener Nano.
        "esp32": {"connected": None if simulated else snapshot["esp32"]["connected"]},
        "camera": {
            "connected": snapshot["vision"]["camera_online"],
            "tracking": snapshot["vision"]["tracking"],
            "faceDetected": (snapshot["vision"]["face_count"] > 0)
            if snapshot["vision"]["face_count"] is not None
            else None,
        },
        "ai": {
            "state": "Cloud-Textmodell eingerichtet"
            if snapshot["llm"]["configured"]
            else "lokaler Textdialog"
        },
        "audio": {"microphone": None, "speaker": None, **snapshot["audio"]},
        "motion": snapshot["motion"],
        "display": {"emotion": (core.expressions.last or "NEUTRAL").lower()},
    }
    config = {
        "motion": {
            "enabled": available,
            "homePan": motion["pan"]["home"],
            "homeTilt": motion["tilt"]["home"],
            "panMin": motion["pan"]["min"],
            "panMax": motion["pan"]["max"],
            "tiltMin": motion["tilt"]["min"],
            "tiltMax": motion["tilt"]["max"],
            "speed": None,
            "smoothing": None,
            "allowExtendedRange": False,
        },
        "camera": {
            "enabled": snapshot["vision"]["camera_online"],
            "autoTracking": snapshot["vision"]["tracking"],
            "trackingSensitivity": None,
        },
        "display": {
            "enabled": snapshot["esp32"]["connected"],
            "emotion": (core.expressions.last or "NEUTRAL").lower(),
            "brightness": core.expressions.brightness,
            "mode": core.expressions.mode,
        },
        "audio": {
            "enabled": snapshot["audio"]["tts_online"],
            "volume": None,
            "autoSpeak": False,
            "continuous": False,
        },
    }
    bridge = {
        "online": True,
        "simulation": simulated,
        "safe_mode": snapshot["safe_mode"],
        "calibrated": motion["calibrated"],
        "motion_available": available,
        "updated_at_utc": snapshot["updated_at_utc"],
        "privacy": snapshot["privacy"],
        "camera_online": snapshot["vision"]["camera_online"],
        "tracking": snapshot["vision"]["tracking"],
        "tts_configured": snapshot["audio"]["tts_online"],
        "display_available": snapshot["esp32"]["connected"],
        "people": snapshot["people"],
        "reason": snapshot["capabilities"]["motion"].get("reason"),
    }
    spotify = {
        **core.audio.spotify.public(),
        "state": core.audio.music_state,
        "source": snapshot["audio"]["music_source"],
    }
    runtime = {
        "motion": snapshot["motion"],
        "audio": snapshot["audio"],
        "display": {"emotion": (core.expressions.last or "NEUTRAL").lower()},
        "camera": {
            **snapshot["vision"],
            "deadzone": core.config["camera"]["deadzone"],
            "gain": core.config["camera"]["gain"],
        },
        "behavior": dict(core.config["behavior"]),
        "spotify": spotify,
        "llm": snapshot["llm"],
        "connections": {"error": core.credentials.error},
        "power": snapshot["power"],
    }
    config["audio"].update(
        volume=core.audio.speech_volume,
        speechRate=core.audio.speech_rate,
        musicVolume=core.audio.volume,
        continuous=core.wakeword_online,
    )
    runtime["display"].update(
        brightness=core.expressions.brightness,
        applied_brightness=core.expressions.applied_brightness,
        mode=core.expressions.mode,
        face=core.expressions.manual_face,
    )
    runtime["settings"] = {
        "available": core.settings.path is not None,
        "saved": bool(core.settings.path and core.settings.path.exists()),
        "error": core.settings.error,
    }
    runtime["limits"] = {
        "pan": dict(core.config["motion"]["pan"]),
        "tilt": dict(core.config["motion"]["tilt"]),
    }
    return {
        "config": config,
        "snapshot": {
            "kind": "snapshot",
            "tele": tele,
            "events": core.event_queue[-30:],
            "bridge": bridge,
            "runtime": runtime,
            "config": config,
        },
        "status": {
            "llm": snapshot["llm"],
            "spotify": spotify,
            "bridge": bridge,
        },
    }


async def execute(core, packet: dict, session: str) -> dict:
    action = "invalid"
    try:
        if not isinstance(packet, dict) or set(packet) - {"action", "data"}:
            raise ValueError("Ungültiges Dashboard-Paket.")
        action, data = packet.get("action"), packet.get("data", {})
        if (
            not isinstance(action, str)
            or len(action) > 80
            or not isinstance(data, dict)
        ):
            raise ValueError("Dashboard-Aktion und Argumentobjekt erforderlich.")
        if action in {"status", "ui.sync", "config.read"}:
            if data:
                raise ValueError("Diese Leseaktion erwartet keine Argumente.")
            public = projection(core)
            return {
                "ok": True,
                "ready": True,
                "message": "Core-Status gelesen. Laufzeitregler und geschützte Konfiguration sind getrennt.",
                **public,
            }
        if action in core.connections.ACTIONS:
            try:
                output, message = await core.connections.execute(action, data, session)
                return {
                    "ok": True,
                    "ready": True,
                    "message": message,
                    "connection_data": output,
                    **projection(core),
                }
            except ValueError as error:
                return {
                    "ok": False,
                    "ready": True,
                    "message": str(error),
                    "error_code": "CONNECTION_REJECTED",
                    **projection(core),
                }
            except (OSError, TimeoutError, TypeError, KeyError, AttributeError):
                return {
                    "ok": False,
                    "ready": True,
                    "message": "Verbindung oder Speicherung fehlgeschlagen. Lokale Dateirechte, Anbieter und Netzwerk prüfen.",
                    "error_code": "CONNECTION_UNAVAILABLE",
                    **projection(core),
                }
        if action.startswith(("config.", "llm.", "spotify.")):
            raise ValueError(
                "Diese Dashboard-Verwaltungsfunktion ist im neuen Core noch nicht eingerichtet. Nichts gespeichert oder gelöscht."
            )
        mapping = {
            "motion.home": "motion.home",
            "motion.set": "motion.set",
            "motion.stop": "stop",
            "tracking.start": "tracking.enable",
            "tracking.stop": "tracking.disable",
            "camera.enable": "camera.enable",
            "camera.disable": "camera.disable",
            "audio.stop": "audio.stop",
            "audio.test": "audio.test",
            "privacy.enable": "privacy.enable",
            "privacy.disable": "privacy.disable",
        }
        mapping.update(
            {
                name: name
                for name in (
                    "people.list",
                    "people.status",
                    "people.enroll.request",
                    "people.enroll.confirm",
                    "people.enroll.cancel",
                    "people.delete",
                    "people.fact.add",
                    "people.facts",
                )
            }
        )
        if action == "chat.send":
            command = {"type": "text", "args": data}
        elif action == "people.save":
            command = {"type": "people.update", "args": data}
        elif action == "display.emotion":
            if (
                set(data) != {"emotion"}
                or not isinstance(data["emotion"], str)
                or data["emotion"].upper() not in FACES
            ):
                raise ValueError("Nicht unterstützter Gesichtsausdruck.")
            command = {
                "type": "display.face",
                "args": {"face": data["emotion"].upper()},
            }
        elif action in RUNTIME_ACTIONS:
            command = {"type": action, "args": data}
        elif action in mapping:
            command = {"type": mapping[action], "args": data}
        else:
            raise ValueError(
                "Diese Dashboard-Aktion ist nicht eingerichtet. Keine Aktion ausgeführt."
            )
        result = await core.execute(command, session=session)
        if (
            action == "chat.send"
            and result["ok"]
            and result["intent"] not in {"stop", "audio.stop", "privacy.enable"}
        ):
            core.background_speech(result["spoken_reply"])
        return {
            "ok": result["ok"],
            "ready": True,
            "message": result["spoken_reply"],
            "reply": result["spoken_reply"] if action == "chat.send" else None,
            "people": result["data"].get("people"),
            "facts": result["data"].get("facts"),
            "enrollment": result["data"]
            if action.startswith("people.enroll.")
            else None,
            "result": result,
            **projection(core),
        }
    except (ValueError, TypeError):
        # Keine Eingabedaten, Credential-Felder oder ungeprüften Fehlertexte zurückgeben.
        message = (
            "Diese Dashboard-Verwaltungsfunktion ist noch nicht eingerichtet. Nichts gespeichert oder gelöscht."
            if isinstance(action, str)
            and action.startswith(("config.", "llm.", "spotify.", "people."))
            else "Ungültige oder nicht unterstützte Dashboard-Aktion. Keine Aktion ausgeführt."
        )
        return {
            "ok": False,
            "ready": True,
            "message": message,
            "error_code": "Dashboard_UNSUPPORTED_OR_INVALID",
        }
