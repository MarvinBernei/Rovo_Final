"""Spotify Connect mit PKCE, Refresh und bewusst ausgewähltem Zielgerät."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from .cloud_http import CloudError, request_json

SCOPES = {"user-read-playback-state", "user-modify-playback-state"}


class Spotify:
    def __init__(self, credentials=None) -> None:
        self.credentials = credentials
        self.active = False
        self.pending = None
        self.verified_at = None
        self.token_lock = asyncio.Lock()
        self.guard = lambda: (0, False)
        self.login_generation = 0

    def check_guard(self, stamp, allow_private=False):
        if stamp != self.guard() or (stamp[1] and not allow_private):
            raise ValueError(
                "Anbieterauftrag durch Stopp oder Privatsphäre abgebrochen."
            )

    def cancel_login(self):
        self.pending = None
        self.login_generation += 1

    def values(self):
        return self.credentials.get("spotify") if self.credentials else {}

    @property
    def configured(self) -> bool:
        value = self.values()
        return bool(
            (value.get("refresh_token") or value.get("access_token"))
            and value.get("device_id")
        ) or bool(
            not value
            and os.environ.get("ROVO_SPOTIFY_ACCESS_TOKEN")
            and os.environ.get("ROVO_SPOTIFY_DEVICE_ID")
        )

    def public(self):
        value = self.values()
        return {
            "configured": self.configured,
            "available": self.configured,
            "connected": self.active,
            "authorized": bool(value.get("refresh_token")),
            "client_id": value.get("client_id", ""),
            "redirect_uri": value.get("redirect_uri", ""),
            "device_id": value.get("device_id", ""),
            "verified": self.verified_at is not None,
            "verified_at": self.verified_at,
        }

    async def configure(self, client_id, redirect_uri):
        try:
            parts = urlsplit(redirect_uri)
            port = parts.port
        except ValueError:
            raise ValueError("Ungültige Redirect-URI oder Portangabe.") from None
        if not re.fullmatch(r"[A-Za-z0-9]{16,128}", client_id):
            raise ValueError("Spotify-Client-ID ist ungültig.")
        if (
            not parts.hostname
            or port == 0
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or (
                parts.scheme != "https"
                and not (
                    parts.scheme == "http" and parts.hostname in {"127.0.0.1", "::1"}
                )
            )
        ):
            raise ValueError(
                "Redirect-URI benötigt HTTPS oder eine HTTP-Loopback-IP (kein localhost)."
            )
        current = self.values()
        if (
            current.get("client_id") != client_id
            or current.get("redirect_uri") != redirect_uri
        ):
            current = {"client_id": client_id, "redirect_uri": redirect_uri}
        self.credentials.save("spotify", current)
        self.cancel_login()
        self.active = False
        self.verified_at = None

    def login(self, session):
        self.cancel_login()
        value = self.values()
        if not value.get("client_id") or not value.get("redirect_uri"):
            raise ValueError("Zuerst Spotify-Client-ID und Redirect-URI speichern.")
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(32)
        self.pending = {
            "session": session,
            "state": state,
            "verifier": verifier,
            "deadline": time.monotonic() + 600,
            "revision": self.credentials.revision["spotify"],
        }
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        return "https://accounts.spotify.com/authorize?" + urlencode(
            {
                "response_type": "code",
                "client_id": value["client_id"],
                "redirect_uri": value["redirect_uri"],
                "scope": " ".join(sorted(SCOPES)),
                "state": state,
                "code_challenge_method": "S256",
                "code_challenge": challenge,
            }
        )

    async def complete(self, callback_url, session):
        stamp = self.guard()
        self.check_guard(stamp)
        generation = self.login_generation
        job = self.pending
        if not job or job["session"] != session:
            raise ValueError(
                "Keine Anmeldung für diese Dashboard-Sitzung. Anmeldung erneut starten."
            )
        if time.monotonic() > job["deadline"]:
            self.pending = None
            raise ValueError("Spotify-Anmeldung abgelaufen. Erneut starten.")
        value = self.values()
        try:
            parts = urlsplit(callback_url)
            expected = urlsplit(value["redirect_uri"])
        except ValueError:
            raise ValueError("Ungültige Rückleitungsadresse.") from None
        query = parse_qs(parts.query)
        state = query.get("state", [])
        if (
            parts.fragment
            or parts._replace(query="") != expected
            or len(state) != 1
            or not hmac.compare_digest(state[0], job["state"])
        ):
            raise ValueError(
                "Rückleitungsadresse oder Anmeldestatus passt nicht zur gestarteten Anmeldung."
            )
        self.pending = None
        if "error" in query:
            raise ValueError("Spotify-Anmeldung wurde abgelehnt oder abgebrochen.")
        codes = query.get("code", [])
        if len(codes) != 1 or len(codes[0]) > 2048:
            raise ValueError("Spotify-Anmeldecode fehlt oder ist ungültig.")
        result = await request_json(
            "POST",
            "https://accounts.spotify.com/api/token",
            form=True,
            data={
                "grant_type": "authorization_code",
                "code": codes[0],
                "redirect_uri": value["redirect_uri"],
                "client_id": value["client_id"],
                "code_verifier": job["verifier"],
            },
        )
        self.check_guard(stamp)
        if (
            job["revision"] != self.credentials.revision["spotify"]
            or generation != self.login_generation
        ):
            raise ValueError("Anmeldung nach Konfigurationsänderung verworfen.")
        self._save_tokens(value, result, require_refresh=True)

    def _save_tokens(self, value, result, require_refresh=False):
        if (
            not isinstance(result.get("access_token"), str)
            or not result["access_token"]
            or len(result["access_token"]) > 8192
            or result.get("token_type", "").lower() != "bearer"
            or type(result.get("expires_in")) is not int
            or not 30 <= result["expires_in"] <= 86400
            or (require_refresh and not result.get("refresh_token"))
        ):
            raise ValueError("Ungültige Spotify-Tokenantwort.")
        if "scope" in result and not SCOPES.issubset(set(result["scope"].split())):
            raise ValueError(
                "Spotify-Berechtigung zur Playersteuerung oder Geräteabfrage fehlt."
            )
        refresh = result.get("refresh_token", value.get("refresh_token"))
        if not isinstance(refresh, str) or not refresh or len(refresh) > 8192:
            raise ValueError("Ungültiger Spotify-Refresh-Token.")
        value.update(
            access_token=result["access_token"],
            refresh_token=refresh,
            expires_at=time.time() + result["expires_in"],
        )
        self.credentials.save("spotify", value)

    async def token(self, force=False, allow_private=False):
        async with self.token_lock:
            stamp = self.guard()
            self.check_guard(stamp, allow_private)
            value = self.values()
            if not value:
                token = os.environ.get("ROVO_SPOTIFY_ACCESS_TOKEN")
                if token:
                    return token
            if (
                value.get("access_token")
                and not force
                and time.time() < value.get("expires_at", 0) - 30
            ):
                return value["access_token"]
            if not value.get("refresh_token"):
                raise ValueError("Spotify-Anmeldung erforderlich.")
            revision = self.credentials.revision["spotify"]
            try:
                result = await request_json(
                    "POST",
                    "https://accounts.spotify.com/api/token",
                    form=True,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": value["refresh_token"],
                        "client_id": value["client_id"],
                    },
                )
            except CloudError as error:
                self.verified_at = None
                if (
                    error.expired_grant
                    and revision == self.credentials.revision["spotify"]
                ):
                    self.credentials.save(
                        "spotify",
                        {
                            k: v
                            for k, v in value.items()
                            if k not in {"access_token", "refresh_token", "expires_at"}
                        },
                    )
                    raise ValueError(
                        "Spotify-Freigabe abgelaufen oder widerrufen. Bitte neu anmelden."
                    ) from None
                raise
            self.check_guard(stamp, allow_private)
            if revision != self.credentials.revision["spotify"]:
                raise ValueError("Tokenantwort nach Änderung der Verbindung verworfen.")
            self._save_tokens(value, result)
            return result["access_token"]

    async def request(self, method: str, route: str, data=None):
        stamp = self.guard()
        safety_pause = method == "PUT" and route == "me/player/pause"
        self.check_guard(stamp, safety_pause)
        value = self.values()
        device = value.get("device_id") or (
            os.environ.get("ROVO_SPOTIFY_DEVICE_ID") if not value else None
        )
        if route.startswith("me/player") and route != "me/player/devices":
            if not device:
                raise ValueError(
                    "Zuerst ein festes Spotify-Connect-Zielgerät auswählen."
                )
            route += ("&" if "?" in route else "?") + urlencode({"device_id": device})
        token = await self.token(allow_private=safety_pause)
        self.check_guard(stamp, safety_pause)
        revision = self.credentials.revision["spotify"] if self.credentials else 0
        try:
            result = await request_json(
                method, "https://api.spotify.com/v1/" + route, token=token, data=data
            )
            self.check_guard(stamp, safety_pause)
            if self.credentials and revision != self.credentials.revision["spotify"]:
                raise ValueError(
                    "Anbieterantwort nach Konfigurationsänderung verworfen."
                )
            return result
        except CloudError as error:
            self.verified_at = None
            if error.status != 401 or not self.values().get("refresh_token"):
                raise
            token = await self.token(force=True, allow_private=safety_pause)
            self.check_guard(stamp, safety_pause)
            revision = self.credentials.revision["spotify"]
            result = await request_json(
                method, "https://api.spotify.com/v1/" + route, token=token, data=data
            )
            self.check_guard(stamp, safety_pause)
            if revision != self.credentials.revision["spotify"]:
                raise ValueError(
                    "Anbieterantwort nach Konfigurationsänderung verworfen."
                )
            return result

    async def devices(self):
        self.verified_at = None
        result = await self.request("GET", "me/player/devices")
        devices = [
            {
                "id": d["id"],
                "name": d.get("name", "Spotify-Gerät"),
                "type": d.get("type", ""),
                "active": d.get("is_active") is True,
            }
            for d in result.get("devices", [])
            if isinstance(d, dict)
            and isinstance(d.get("id"), str)
            and not d.get("is_restricted")
        ]
        self.verified_at = time.time()
        return devices

    def select(self, device):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", device):
            raise ValueError("Ungültige Spotify-Geräte-ID.")
        value = self.values()
        if not value.get("refresh_token"):
            raise ValueError("Zuerst Spotify anmelden.")
        value["device_id"] = device
        self.credentials.save("spotify", value)
        self.active = False
        self.verified_at = None

    async def play(self, query: str) -> dict:
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 120:
            raise ValueError("Bitte einen kurzen Titel oder Interpreten nennen.")
        result = await self.request(
            "GET", "search?" + urlencode({"q": query, "type": "track", "limit": 1})
        )
        tracks = result.get("tracks", {}).get("items", [])
        if not tracks:
            raise ValueError("Spotify hat keinen passenden Titel gefunden.")
        track = tracks[0]
        await self.request("PUT", "me/player/play", {"uris": [track["uri"]]})
        self.active = True
        return {
            "title": track["name"],
            "artists": [a["name"] for a in track["artists"]],
            "selection": "Erster Spotify-Suchtreffer",
        }

    async def search(self, query: str, kind: str = "track") -> list[dict]:
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 120:
            raise ValueError("Bitte einen kurzen Spotify-Suchtext nennen.")
        if kind not in {"track", "playlist"}:
            raise ValueError("Spotify-Suche unterstützt Titel oder Playlists.")
        result = await self.request(
            "GET", "search?" + urlencode({"q": query, "type": kind, "limit": 10})
        )
        items = result.get(kind + "s", {}).get("items", [])
        output = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("uri"), str):
                continue
            owner = item.get("owner", {}).get("display_name", "")
            artists = [
                artist.get("name", "")
                for artist in item.get("artists", [])
                if isinstance(artist, dict)
            ]
            output.append(
                {
                    "uri": item["uri"],
                    "name": str(item.get("name", "Spotify-Ergebnis"))[:200],
                    "subtitle": ", ".join(filter(None, artists)) or str(owner)[:200],
                    "kind": kind,
                }
            )
        return output

    async def play_uri(self, uri: str) -> dict:
        if not isinstance(uri, str) or not re.fullmatch(
            r"spotify:(?:track|album|playlist):[A-Za-z0-9]{1,64}", uri
        ):
            raise ValueError("Ungültige Spotify-Titel-, Album- oder Playlist-ID.")
        data = (
            {"uris": [uri]}
            if uri.startswith("spotify:track:")
            else {"context_uri": uri}
        )
        await self.request("PUT", "me/player/play", data)
        self.active = True
        return {"uri": uri}

    async def enqueue(self, uri: str) -> None:
        if not isinstance(uri, str) or not re.fullmatch(
            r"spotify:track:[A-Za-z0-9]{1,64}", uri
        ):
            raise ValueError(
                "Für die Warteschlange ist eine Spotify-Titel-ID erforderlich."
            )
        await self.request("POST", "me/player/queue?" + urlencode({"uri": uri}))

    async def shuffle(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise ValueError("Shuffle-Freigabe muss boolesch sein.")
        await self.request(
            "PUT", "me/player/shuffle?" + urlencode({"state": str(enabled).lower()})
        )

    async def pause(self, paused: bool) -> None:
        await self.request("PUT", "me/player/pause" if paused else "me/player/play")

    async def volume(self, value: int) -> None:
        await self.request(
            "PUT", "me/player/volume?" + urlencode({"volume_percent": value})
        )
