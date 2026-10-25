"""Versionierte Laufzeiteinstellungen ohne Zugangsdaten oder Hardwarefreigaben."""

import copy
import json
import os
from pathlib import Path

from .config import number
from .esp import FACES


def validate_settings(value):
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "audio", "camera", "behavior", "motion", "display"}
        or value["schema"] != 1
    ):
        raise ValueError("Ungültiges Einstellungsformat.")
    expected = {
        "audio": {"speech_volume", "speech_rate", "music_volume"},
        "camera": {"deadzone", "gain"},
        "behavior": {"social_gaze"},
        "motion": {"speed", "acceleration"},
        "display": {"brightness", "mode", "face"},
    }
    for section, keys in expected.items():
        if not isinstance(value[section], dict) or set(value[section]) != keys:
            raise ValueError("Unbekannte Einstellungsfelder.")
    for section, key, low, high in (
        ("audio", "speech_volume", 0, 100),
        ("audio", "music_volume", 0, 100),
        ("audio", "speech_rate", 0.5, 1.5),
        ("camera", "deadzone", 0, 0.4),
        ("camera", "gain", 0.1, 5),
        ("motion", "speed", 2, 20),
        ("motion", "acceleration", 4, 40),
        ("display", "brightness", 0, 100),
    ):
        number(value[section][key], low, high)
    if (
        type(value["audio"]["speech_volume"]) is not int
        or type(value["audio"]["music_volume"]) is not int
        or type(value["display"]["brightness"]) is not int
    ):
        raise ValueError("Ganzzahlige Lautstärke/Helligkeit erforderlich.")
    if (
        type(value["behavior"]["social_gaze"]) is not bool
        or value["display"]["mode"] not in {"automatic", "manual", "off"}
        or value["display"]["face"] not in FACES
    ):
        raise ValueError("Ungültiger Verhaltens-/Displaymodus.")
    return value


class Settings:
    def __init__(self, data: Path | None):
        self.path = data / "settings.json" if data else None
        self.error = None

    def read(self, source="saved"):
        if source not in {"saved", "previous"} or not self.path:
            raise ValueError("Keine gespeicherte Konfiguration verfügbar.")
        path = (
            self.path
            if source == "saved"
            else self.path.with_name("settings.previous.json")
        )
        return validate_settings(json.loads(path.read_text(encoding="utf-8")))

    def write(self, value):
        validate_settings(value)
        if not self.path:
            raise ValueError("Dauerhaftes Speichern benötigt einen Datenordner.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                previous = self.read()
                self.atomic(self.path.with_name("settings.previous.json"), previous)
            except (ValueError, OSError, TypeError):
                pass
        self.atomic(self.path, value)
        self.error = None

    @staticmethod
    def atomic(path, value):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, path)

    @staticmethod
    def capture(core):
        return {
            "schema": 1,
            "audio": {
                "speech_volume": core.audio.speech_volume,
                "speech_rate": core.audio.speech_rate,
                "music_volume": core.audio.volume,
            },
            "camera": {k: core.config["camera"][k] for k in ("deadzone", "gain")},
            "behavior": {"social_gaze": core.config["behavior"]["social_gaze"]},
            "motion": {
                "speed": core.motion.speed,
                "acceleration": core.motion.acceleration,
            },
            "display": {
                "brightness": core.expressions.brightness,
                "mode": core.expressions.mode,
                "face": core.expressions.manual_face,
            },
        }

    @staticmethod
    def apply(core, value):
        value = validate_settings(copy.deepcopy(value))
        core.audio.speech_volume = value["audio"]["speech_volume"]
        core.audio.speech_rate = value["audio"]["speech_rate"]
        core.audio.volume = value["audio"]["music_volume"]
        core.config["camera"].update(value["camera"])
        core.config["behavior"].update(value["behavior"])
        core.motion.speed = value["motion"]["speed"]
        core.motion.acceleration = value["motion"]["acceleration"]
        core.motion.profile_pending = True
        core.expressions.brightness = value["display"]["brightness"]
        core.expressions.mode = value["display"]["mode"]
        core.expressions.manual_face = value["display"]["face"]
        core.expressions.states.clear()
        core.expressions.last = None
