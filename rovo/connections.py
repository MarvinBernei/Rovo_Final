"""Dashboard-Einrichtung; private Datei, öffentliche Projektion, keine Secret-Echos."""

from __future__ import annotations

import asyncio
import copy
import json
import math
import os
import re
import tempfile
from pathlib import Path

from .cloud_providers import PROVIDERS, profiles_for


def field(value, limit=4096, empty=False):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or (not empty and not value.strip())
    ):
        raise ValueError("Pflichtfeld fehlt oder Eingabe ist zu lang.")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Steuerzeichen sind nicht erlaubt.")
    return value.strip()


def validate_credentials(values):
    if not isinstance(values, dict) or set(values) != {"llm", "spotify"}:
        raise ValueError("Ungültige Verbindungsdatei.")
    llm, spotify = values["llm"], values["spotify"]
    if not isinstance(llm, dict) or not isinstance(spotify, dict):
        raise ValueError("Ungültige Verbindungsdatei.")
    if llm:
        active_keys = {"provider", "model", "api_key", "enabled", "allow_cloud"}
        if set(llm) != {"profiles"} and (
            set(llm) - {"profiles"} != active_keys
            or llm.get("provider") not in PROVIDERS
            or type(llm["enabled"]) is not bool
            or type(llm["allow_cloud"]) is not bool
        ):
            raise ValueError("Ungültige LLM-Konfiguration.")
        if "provider" in llm:
            field(llm["api_key"], 512)
            model_id(llm["model"])
        profiles = llm.get("profiles", {})
        if not isinstance(profiles, dict) or set(profiles) - PROVIDERS.keys():
            raise ValueError("Ungültige Anbieterprofile.")
        for profile in profiles.values():
            if not isinstance(profile, dict) or set(profile) != {
                "model",
                "api_key",
                "models",
            }:
                raise ValueError("Ungültiges Anbieterprofil.")
            if profile["api_key"] is not None:
                field(profile["api_key"], 512)
            if profile["model"] is not None:
                model_id(profile["model"])
            models = profile["models"]
            if not isinstance(models, list) or len(models) > 50:
                raise ValueError("Höchstens 50 eigene Modelle je Anbieter speichern.")
            for model in models:
                model_id(model)
            if len(set(models)) != len(models):
                raise ValueError("Doppelte Modell-IDs.")
    if set(spotify) - {
        "client_id",
        "redirect_uri",
        "device_id",
        "access_token",
        "refresh_token",
        "expires_at",
        "disabled",
    }:
        raise ValueError("Ungültige Spotify-Konfiguration.")
    for key in set(spotify) - {"expires_at", "disabled"}:
        field(spotify[key], 8192)
    if "disabled" in spotify and spotify != {"disabled": True}:
        raise ValueError("Ungültige Spotify-Konfiguration.")
    if "expires_at" in spotify and (
        type(spotify["expires_at"]) not in (int, float)
        or not math.isfinite(spotify["expires_at"])
    ):
        raise ValueError("Ungültige Tokenfrist.")
    if "refresh_token" in spotify and not {
        "client_id",
        "redirect_uri",
        "access_token",
        "expires_at",
    }.issubset(spotify):
        raise ValueError("Unvollständige Spotify-Konfiguration.")
    return values


def model_id(value):
    value = field(value, 120)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}", value) or ".." in value:
        raise ValueError("Ungültige Modell-ID.")
    return value


class Credentials:
    def __init__(self, data: Path | None):
        self.path = data / "private" / "connections.json" if data else None
        self.values = {"llm": {}, "spotify": {}}
        self.revision = {"llm": 0, "spotify": 0}
        self.error = None
        if self.path and self.path.exists():
            try:
                if self.path.is_symlink() or self.path.parent.is_symlink():
                    raise ValueError()
                if os.name == "posix" and (
                    self.path.stat().st_mode & 0o077
                    or self.path.parent.stat().st_mode & 0o077
                ):
                    raise ValueError()
                if self.path.stat().st_size > 32768:
                    raise ValueError()
                values = json.loads(self.path.read_text(encoding="utf-8"))
                self.values = validate_credentials(values)
            except (ValueError, OSError, TypeError):
                self.error = "Private Verbindungsdatei ungültig oder ungeschützt. Datei und Rechte lokal prüfen."

    def get(self, section):
        return copy.deepcopy(self.values[section])

    def save(self, section, value):
        if not self.path:
            raise ValueError("Speichern benötigt den Datenordner des Core (--data).")
        if self.error:
            raise ValueError(self.error)
        parent = self.path.parent
        if parent.is_symlink() or self.path.is_symlink():
            raise ValueError(
                "Private Verbindungsdatei darf kein symbolischer Link sein."
            )
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(parent, 0o700)
        values = copy.deepcopy(self.values)
        values[section] = copy.deepcopy(value)
        validate_credentials(values)
        encoded = json.dumps(values, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > 32768:
            raise ValueError("Verbindungsdaten sind zu groß.")
        fd, name = tempfile.mkstemp(prefix=".connections-", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.values = values
        self.revision[section] += 1


class Connections:
    ACTIONS = frozenset(
        {
            "llm.save",
            "llm.test",
            "llm.forget",
            "llm.models",
            "spotify.save",
            "spotify.login",
            "spotify.complete",
            "spotify.cancel",
            "spotify.test",
            "spotify.devices",
            "spotify.select",
            "spotify.disconnect",
        }
    )

    def __init__(self, core, credentials):
        self.core = core
        self.credentials = credentials
        self.lock = asyncio.Lock()

    async def execute(self, action, data, session):
        if action == "spotify.cancel":
            if data:
                raise ValueError("Abbrechen erwartet keine Eingabefelder.")
            self.core.audio.spotify.cancel_login()
            return {}, "Spotify-Anmeldung abgebrochen."
        async with self.lock:
            return await self._execute(action, data, session)

    async def _execute(self, action, data, session):
        core, store = self.core, self.credentials
        spotify = core.audio.spotify
        if action == "llm.models":
            if (
                set(data) not in ({"provider"}, {"provider", "apiKey"})
                or data["provider"] not in PROVIDERS
            ):
                raise ValueError("Anbieter auswählen.")
            key = field(data.get("apiKey", ""), 512, empty=True)
            models = await core.llm.models(data["provider"], key)
            if key:
                value = store.get("llm")
                profiles = profiles_for(value)
                profile = profiles.setdefault(
                    data["provider"], {"model": None, "api_key": None, "models": []}
                )
                profile["api_key"] = key
                value["profiles"] = profiles
                if value.get("provider") == data["provider"]:
                    value["api_key"] = key
                    core.llm.verified_at = None
                store.save("llm", value)
            return (
                {"provider": data["provider"], "models": models},
                "Modellliste geladen. Ein neu eingegebener Key ist gespeichert. Der Modelltest prüft die Eignung für ROVO.",
            )
        if (
            action in {"spotify.save", "spotify.select", "spotify.disconnect"}
            and spotify.active
        ):
            raise ValueError(
                "Vor dem Ändern oder Entfernen des Spotify-Zugangs bitte die Musik stoppen."
            )
        if action in {"llm.forget", "spotify.disconnect"}:
            if set(data) != {"confirm"} or data["confirm"] is not True:
                raise ValueError("Zum Entfernen bitte die Bestätigung aktivieren.")
            section = "llm" if action == "llm.forget" else "spotify"
            if section == "llm":
                value = store.get("llm")
                profiles = profiles_for(value)
                profiles.pop(value.get("provider"), None)
                store.save(section, {"profiles": profiles} if profiles else {})
            else:
                store.save(section, {"disabled": True})
            if section == "llm":
                core.llm.verified_at = None
                core.config["llm"].update(enabled=False, allow_cloud=False, model=None)
            else:
                spotify.cancel_login()
                spotify.verified_at = None
                spotify.active = False
            return (
                {},
                "Verbindung lokal entfernt. Beim Anbieter erteilte Freigaben bei Bedarf dort widerrufen.",
            )
        if action == "llm.save":
            if set(data) != {"provider", "model", "apiKey", "allowCloud", "enabled"}:
                raise ValueError("Ungültige LLM-Felder.")
            if (
                not isinstance(data["provider"], str)
                or data["provider"] not in PROVIDERS
                or type(data["enabled"]) is not bool
                or data["allowCloud"] is not True
            ):
                raise ValueError(
                    "Cloudanbieter auswählen und Übermittlung freier Texte ausdrücklich erlauben."
                )
            model = model_id(data["model"])
            profiles = profiles_for(store.get("llm"))
            profile = profiles.get(
                data["provider"], {"api_key": None, "model": None, "models": []}
            )
            key = field(data["apiKey"], 512, empty=True) or profile["api_key"]
            if not key:
                raise ValueError(
                    "API-Key erforderlich. Leeres Feld behält einen bereits gespeicherten Key."
                )
            profile.update(api_key=key, model=model)
            profiles[data["provider"]] = profile
            store.save(
                "llm",
                {
                    "provider": data["provider"],
                    "model": model,
                    "api_key": key,
                    "enabled": data["enabled"],
                    "allow_cloud": True,
                    "profiles": profiles,
                },
            )
            core.config["llm"].update(
                enabled=data["enabled"], allow_cloud=True, model=model
            )
            core.llm.verified_at = None
            return (
                {},
                "LLM gespeichert. Verbindung mit Modelltest prüfen; dieser kann API-Kosten verursachen.",
            )
        if action == "spotify.save":
            if set(data) != {"clientId", "redirectUri"}:
                raise ValueError("Ungültige Spotify-Felder.")
            await spotify.configure(
                field(data["clientId"], 128), field(data["redirectUri"], 1000)
            )
            return {}, "Spotify-App gespeichert. Jetzt Anmeldung starten."
        if action == "spotify.complete":
            if set(data) != {"callbackUrl"}:
                raise ValueError("Rückleitungsadresse erforderlich.")
            if core.privacy:
                raise ValueError(
                    "Privatsphäre ist aktiv. Keine externe Anmeldung ausgeführt."
                )
            await spotify.complete(field(data["callbackUrl"], 4096), session)
            return {}, "Spotify angemeldet. Geräte laden und Zielgerät auswählen."
        if action == "spotify.select":
            if set(data) != {"deviceId"}:
                raise ValueError("Geräte-ID erforderlich.")
            spotify.select(field(data["deviceId"], 256))
            return {}, "Spotify-Zielgerät gespeichert. Keine Wiedergabe gestartet."
        if data:
            raise ValueError("Diese Aktion erwartet keine Eingabefelder.")
        if action == "spotify.cancel":
            spotify.cancel_login()
            return {}, "Spotify-Anmeldung abgebrochen."
        if core.privacy:
            raise ValueError(
                "Privatsphäre ist aktiv. Keine Anbieteranfrage ausgeführt."
            )
        if action == "spotify.login":
            return (
                {"auth_url": spotify.login(session)},
                "Link öffnen, anmelden und anschließend die vollständige Rückleitungsadresse hier einfügen.",
            )
        if action in {"spotify.devices", "spotify.test"}:
            devices = await spotify.devices()
            return {
                "devices": devices
            }, "Spotify erreichbar. Geräte aktualisiert; keine Wiedergabe gestartet."
        if action == "llm.test":
            await core.llm.respond("Antworte kurz mit: Verbindung funktioniert.")
            return {}, "LLM-Modelltest erfolgreich."
        raise ValueError("Unbekannte Verbindungsaktion.")
