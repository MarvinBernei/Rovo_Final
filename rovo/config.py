"""Strikte Konfiguration; Kalibrierung niemals aus UI-Presets ableiten."""

from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT = {
    "schema_version": 1,
    "mqtt": {"enabled": False, "host": "127.0.0.1", "port": 1883, "prefix": "rovo/v1"},
    "timezone": "Europe/Berlin",
    "safe_mode": True,
    "simulation": True,
    "serial_port": None,
    "motion": {
        "calibrated": False,
        "calibration_id": None,
        **{
            axis: {"min": None, "max": None, "home": None, "direction": None}
            for axis in ("pan", "tilt")
        },
    },
    "audio": {
        "enabled": False,
        "piper": "piper",
        "voice": None,
        "output_device": "default",
    },
    "llm": {"enabled": False, "endpoint": None, "model": None, "allow_cloud": False},
    "camera": {
        "enabled": False,
        "backend": "opencv",
        "index": 0,
        "width": 640,
        "height": 480,
        "deadzone": 0.1,
        "gain": 2.0,
    },
    "behavior": {"social_gaze": False, "gaze_seconds": 1.5, "gaze_interval_seconds": 8},
    "weather": {
        "enabled": False,
        "latitude": None,
        "longitude": None,
        "label": "lokaler Standort",
    },
    "power": {"supply": None, "driver": "sysfs", "i2c_bus": 1, "i2c_address": 45},
    "people": {
        "enabled": False,
        "detector_model": None,
        "recognizer_model": None,
        "recognition_verified": False,
        "known_threshold": 0.55,
        "unknown_threshold": 0.30,
        "match_margin": 0.08,
        "samples_per_pose": 40,
        "store_images": False,
        "offer_enrollment": True,
        "greet_daily": True,
        "liveness_required": False,
        "liveness_timeout_seconds": 20,
    },
    "api": {"host": "127.0.0.1", "port": 1891},
}


def number(value: object, low: float, high: float) -> float:
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"Zahl zwischen {low} und {high} erforderlich.")
    return float(value)


def load(path: Path | None = None) -> dict:
    config = copy.deepcopy(DEFAULT)
    if path is not None:
        supplied = json.loads(path.read_text(encoding="utf-8-sig"))

        def merge(target: dict, source: dict) -> None:
            if not isinstance(source, dict):
                raise ValueError("Konfigurationsobjekt erforderlich.")
            for key, value in source.items():
                if key not in target:
                    raise ValueError(f"Unbekannter Konfigurationsschlüssel: {key}")
                if isinstance(target[key], dict):
                    merge(target[key], value)
                else:
                    target[key] = value

        merge(config, supplied)
    validate(config)
    return config


def validate(config: dict) -> None:
    if type(config["mqtt"]["enabled"]) is not bool or config["mqtt"]["host"] not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError("MQTT benötigt einen lokalen Broker und boolesche Freigabe.")
    if (
        type(config["mqtt"]["port"]) is not int
        or not 1 <= config["mqtt"]["port"] <= 65535
    ):
        raise ValueError("Ungültiger MQTT-Port.")
    if config["mqtt"]["prefix"] != "rovo/v1":
        raise ValueError("Dieser Flow verwendet das feste MQTT-Präfix rovo/v1.")
    if config["power"]["driver"] not in {"sysfs", "waveshare-ups-hat-e"}:
        raise ValueError("Unbekannter Akkutreiber.")
    for key, low, high in (("i2c_bus", 0, 16), ("i2c_address", 8, 119)):
        if (
            type(config["power"][key]) is not int
            or not low <= config["power"][key] <= high
        ):
            raise ValueError("Ungültige I2C-Konfiguration.")
    if type(config["behavior"]["social_gaze"]) is not bool:
        raise ValueError("social_gaze muss boolesch sein.")
    number(config["behavior"]["gaze_seconds"], 0.3, 3)
    number(config["behavior"]["gaze_interval_seconds"], 5, 60)
    if type(config["weather"]["enabled"]) is not bool:
        raise ValueError("Wetterfreigabe muss boolesch sein.")
    if config["weather"]["enabled"]:
        number(config["weather"]["latitude"], -90, 90)
        number(config["weather"]["longitude"], -180, 180)
    if (
        not isinstance(config["weather"]["label"], str)
        or len(config["weather"]["label"]) > 80
    ):
        raise ValueError("Ungültige Wetter-Ortsbezeichnung.")
    supply = config["power"]["supply"]
    if supply is not None and (
        not isinstance(supply, str)
        or not supply
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in supply
        )
    ):
        raise ValueError("Ungültiger power_supply-Name.")
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("Unbekannte Schemaversion.")
    for value in (
        config["safe_mode"],
        config["simulation"],
        config["motion"]["calibrated"],
        config["audio"]["enabled"],
        config["llm"]["enabled"],
        config["llm"]["allow_cloud"],
        config["camera"]["enabled"],
    ):
        if type(value) is not bool:
            raise ValueError("Boolescher Konfigurationswert erforderlich.")
    for key in (
        "enabled",
        "recognition_verified",
        "store_images",
        "offer_enrollment",
        "greet_daily",
        "liveness_required",
    ):
        if type(config["people"][key]) is not bool:
            raise ValueError("Boolescher Personen-Konfigurationswert erforderlich.")
    number(config["people"]["known_threshold"], 0.3, 0.95)
    number(config["people"]["unknown_threshold"], 0, 0.5)
    number(config["people"]["match_margin"], 0.01, 0.3)
    if config["people"]["unknown_threshold"] >= config["people"]["known_threshold"]:
        raise ValueError("Unknown-Schwelle muss kleiner als Known-Schwelle sein.")
    number(config["people"]["samples_per_pose"], 5, 100)
    number(config["people"]["liveness_timeout_seconds"], 10, 60)
    if type(config["people"]["samples_per_pose"]) is not int:
        raise ValueError("Pro Pose eine ganzzahlige Samplezahl konfigurieren.")
    try:
        ZoneInfo(config["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError(
            "Zeitzonendaten fehlen. Unter Windows: pip install tzdata."
        ) from exc
    if config["api"]["host"] != "127.0.0.1":
        raise ValueError("API ausschließlich lokal; für LAN einen TLS-Proxy verwenden.")
    number(config["api"]["port"], 1024, 65535)
    if type(config["api"]["port"]) is not int:
        raise ValueError("Port muss ganzzahlig sein.")
    number(config["camera"]["deadzone"], 0, 0.5)
    number(config["camera"]["gain"], 0, 5)
    if config["camera"]["backend"] not in {"opencv", "picamera2"}:
        raise ValueError("Kamera-Backend muss opencv oder picamera2 sein.")
    for key in ("width", "height"):
        if (
            type(config["camera"][key]) is not int
            or not 160 <= config["camera"][key] <= 4096
        ):
            raise ValueError("Ungültige Kameraauflösung.")
    if config["motion"]["calibrated"]:
        calibration_id = config["motion"]["calibration_id"]
        if not config["simulation"] and (
            not isinstance(calibration_id, str)
            or not 8 <= len(calibration_id) <= 64
            or any(
                c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for c in calibration_id
            )
        ):
            raise ValueError(
                "Bestätigte Kalibrierung benötigt eine sichere calibration_id."
            )
        for axis in ("pan", "tilt"):
            limits = config["motion"][axis]
            lo, hi, home = [number(limits[k], 0, 180) for k in ("min", "max", "home")]
            if (
                not lo < hi
                or not lo <= home <= hi
                or type(limits["direction"]) is not int
                or limits["direction"] not in (-1, 1)
            ):
                raise ValueError("Ungültige Kalibrierung.")


def save(path: Path, config: dict) -> None:
    validate(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(temporary, path)
